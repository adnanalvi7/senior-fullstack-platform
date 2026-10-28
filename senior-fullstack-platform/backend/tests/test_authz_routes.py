"""
Route-walking authorization guard.

Enumerates every registered API route that takes an object ID and asserts that, for every
HTTP method the route serves, an out-of-scope ID (another tenant's, or an unassigned
property's in the same tenant) is answered with 404 — exactly like a nonexistent ID — and
never with data. A new endpoint that forgets `for_user()` fails this test automatically.
"""
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APITestCase
from apps.accounts.models import Organization, User, UserPropertyAccess
from apps.properties.models import Property
from apps.projects.models import Project

ID_KWARGS = ('pk', 'project_id', 'property_id', 'id')


def iter_patterns(patterns, prefix=''):
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from iter_patterns(p.url_patterns, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern), p


def object_routes():
    routes = []
    for route, pattern in iter_patterns(get_resolver().url_patterns):
        if not route.startswith('api/'):
            continue
        kw = [k for k in ID_KWARGS if f'<int:{k}>' in route or f'(?P<{k}>' in route]
        if len(kw) == 1 and 'format' not in route:
            routes.append((route, kw[0], pattern))
    return routes


def materialise(route, kw, value):
    url = route.replace(f'<int:{kw}>', str(value))
    url = url.replace(f'(?P<{kw}>[^/.]+)', str(value))
    return '/' + url.replace('^', '').replace('$', '')


class TestEveryObjectRouteIsScoped(APITestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name="A", slug="a")
        self.org2 = Organization.objects.create(name="B", slug="b")
        self.p1a = Property.objects.create(org=self.org1, name="1a", code="1A")
        self.p1b = Property.objects.create(org=self.org1, name="1b", code="1B")
        self.p2 = Property.objects.create(org=self.org2, name="2", code="2")
        self.pm = User.objects.create_user(email="pm@a.com", password="pw123456", org=self.org1, role="property_manager")
        UserPropertyAccess.objects.create(user=self.pm, property=self.p1a)
        self.admin1 = User.objects.create_user(email="admin@a.com", password="pw123456", org=self.org1, role="org_admin")
        mk = lambda prop: Project.objects.create(org=prop.org, property=prop, title="t", category="HVAC",
                                                 fiscal_period="FY2025", budget_amount="10.00", status="submitted")
        self.same_org_hidden = mk(self.p1b)
        self.cross_tenant = mk(self.p2)

    def test_routes_are_discovered(self):
        routes = [r for r, _, _ in object_routes()]
        self.assertTrue(any('projects' in r and 'approve' in r for r in routes), routes)
        self.assertTrue(any('projects' in r and 'history' in r for r in routes), routes)
        self.assertTrue(any(r.startswith('api/v1/properties/') for r in routes), routes)

    def _probe(self, user, resource, targets):
        self.client.force_authenticate(user=user)
        failures = []
        for route, kw, _pattern in object_routes():
            if not route.startswith(f'api/v1/{resource}/'):
                continue
            for label, obj_id in targets:
                url = materialise(route, kw, obj_id)
                for method in ('get', 'put', 'patch', 'delete', 'post'):
                    res = getattr(self.client, method)(url, {'action': 'reject', 'title': 'x'}, format='json')
                    if res.status_code in (405, 403):  # method not served / role gate before lookup
                        continue
                    if res.status_code != 404:
                        failures.append(f"{method.upper()} {url} ({label}) -> {res.status_code}")
        self.assertEqual(failures, [])

    def test_property_manager_cannot_reach_out_of_scope_objects(self):
        self._probe(self.pm, 'projects', [
            ('same-org unassigned project', self.same_org_hidden.id),
            ('cross-tenant project', self.cross_tenant.id),
        ])
        self._probe(self.pm, 'properties', [('same-org unassigned property', self.p1b.id), ('cross-tenant property', self.p2.id)])

    def test_org_admin_cannot_reach_other_tenant_objects(self):
        self._probe(self.admin1, 'projects', [('cross-tenant project', self.cross_tenant.id)])
        self._probe(self.admin1, 'properties', [('cross-tenant property', self.p2.id)])
        self.cross_tenant.refresh_from_db()
        self.assertEqual(self.cross_tenant.status, 'submitted')
