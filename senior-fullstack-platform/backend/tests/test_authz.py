import re
from django.core.cache import cache
from rest_framework.test import APITestCase
from apps.accounts.models import Organization, User, UserPropertyAccess
from apps.properties.models import Property
from apps.projects.models import Project

class TestMultiTenantAuthorization(APITestCase):
    """
    Mandatory security test suite proving:
    1. Tenant A cannot see Tenant B's data (list, detail, analytics).
    2. Property Manager cannot see other properties even within their own organization.
    3. Guessing IDs does NOT reveal unauthorized resources (returns 404).
    4. Cross-tenant property assignment on create/update is rejected.
    """

    def setUp(self):
        cache.clear()

        # Tenant 1
        self.org1 = Organization.objects.create(name="Tenant One", slug="tenant-1")
        self.prop1_a = Property.objects.create(org=self.org1, name="Prop 1A", code="P1-A")
        self.prop1_b = Property.objects.create(org=self.org1, name="Prop 1B", code="P1-B")

        self.admin_org1 = User.objects.create_user(
            email="admin@tenant1.com", password="password", org=self.org1, role="org_admin"
        )
        self.pm_prop1_a = User.objects.create_user(
            email="pm@tenant1.com", password="password", org=self.org1, role="property_manager"
        )
        UserPropertyAccess.objects.create(user=self.pm_prop1_a, property=self.prop1_a)

        self.proj_1a = Project.objects.create(
            org=self.org1, property=self.prop1_a, title="Project 1A Roof",
            category="Roofing", fiscal_period="FY2025", budget_amount="50000.00", actual_cost="45000.00",
            status="draft", submitted_by=self.pm_prop1_a
        )
        self.proj_1b = Project.objects.create(
            org=self.org1, property=self.prop1_b, title="Project 1B HVAC",
            category="HVAC", fiscal_period="FY2025", budget_amount="80000.00", actual_cost="85000.00",
            status="submitted", submitted_by=self.admin_org1
        )

        # Tenant 2
        self.org2 = Organization.objects.create(name="Tenant Two", slug="tenant-2")
        self.prop2 = Property.objects.create(org=self.org2, name="Prop 2", code="P2-A")
        self.admin_org2 = User.objects.create_user(
            email="admin@tenant2.com", password="password", org=self.org2, role="org_admin"
        )
        self.proj_2 = Project.objects.create(
            org=self.org2, property=self.prop2, title="Project 2 Electrical",
            category="Electrical", fiscal_period="FY2025", budget_amount="60000.00", actual_cost="60000.00",
            status="draft", submitted_by=self.admin_org2
        )

    def test_tenant_a_cannot_list_tenant_b_projects(self):
        self.client.force_authenticate(user=self.admin_org1)
        res = self.client.get('/api/v1/projects/')
        self.assertEqual(res.status_code, 200)
        ids = [p['id'] for p in res.data['results']]
        self.assertIn(self.proj_1a.id, ids)
        self.assertIn(self.proj_1b.id, ids)
        self.assertNotIn(self.proj_2.id, ids)

    def test_property_manager_scoped_to_assigned_properties_only(self):
        # PM has access only to prop1_a, NOT prop1_b
        self.client.force_authenticate(user=self.pm_prop1_a)
        res = self.client.get('/api/v1/projects/')
        self.assertEqual(res.status_code, 200)
        ids = [p['id'] for p in res.data['results']]
        self.assertIn(self.proj_1a.id, ids)
        self.assertNotIn(self.proj_1b.id, ids)
        self.assertNotIn(self.proj_2.id, ids)

    def test_guessing_resource_id_returns_404_not_found(self):
        # Admin Org 1 tries to access Project from Org 2
        self.client.force_authenticate(user=self.admin_org1)
        res = self.client.get(f'/api/v1/projects/{self.proj_2.id}/')
        self.assertEqual(res.status_code, 404)

        # PM tries to access Project in same org but unassigned property
        self.client.force_authenticate(user=self.pm_prop1_a)
        res = self.client.get(f'/api/v1/projects/{self.proj_1b.id}/')
        self.assertEqual(res.status_code, 404)

    def test_cannot_create_project_in_another_tenant_property(self):
        self.client.force_authenticate(user=self.admin_org1)
        payload = {
            "title": "Malicious Cross-Tenant Project",
            "property": self.prop2.id,  # Belongs to Org 2!
            "category": "HVAC",
            "fiscal_period": "FY2025",
            "budget_amount": "10000.00",
            "actual_cost": "0.00"
        }
        res = self.client.post('/api/v1/projects/', payload)
        self.assertEqual(res.status_code, 400)
        self.assertFalse(Project.objects.filter(title="Malicious Cross-Tenant Project").exists())

    def test_foreign_property_is_indistinguishable_from_nonexistent(self):
        """No existence oracle: another tenant's property ID errors exactly like a missing one."""
        self.client.force_authenticate(user=self.pm_prop1_a)
        base = {"title": "x", "category": "HVAC", "fiscal_period": "FY2025", "budget_amount": "10.00"}
        other_org = self.client.post('/api/v1/projects/', {**base, "property": self.prop2.id})
        same_org_unassigned = self.client.post('/api/v1/projects/', {**base, "property": self.prop1_b.id})
        nonexistent = self.client.post('/api/v1/projects/', {**base, "property": 987654})
        self.assertEqual(other_org.status_code, 400)
        strip = lambda r: re.sub(r'"\d+"', '"N"', r.data['error'])
        self.assertEqual(strip(other_org), strip(nonexistent))
        self.assertEqual(strip(same_org_unassigned), strip(nonexistent))

    def test_status_cannot_be_mass_assigned(self):
        """The approval state machine cannot be bypassed through generic CRUD."""
        self.client.force_authenticate(user=self.pm_prop1_a)
        res = self.client.post('/api/v1/projects/', {
            "title": "Self approved", "property": self.prop1_a.id, "category": "HVAC",
            "fiscal_period": "FY2025", "budget_amount": "10.00", "status": "approved",
        })
        self.assertEqual(res.status_code, 400)
        self.assertFalse(Project.objects.filter(title="Self approved").exists())

        res = self.client.patch(f'/api/v1/projects/{self.proj_1a.id}/', {"status": "approved"})
        self.assertEqual(res.status_code, 400)
        self.proj_1a.refresh_from_db()
        self.assertEqual(self.proj_1a.status, 'draft')
        self.assertFalse(self.proj_1a.approval_events.exists())

    def test_org_and_submitter_cannot_be_mass_assigned(self):
        self.client.force_authenticate(user=self.pm_prop1_a)
        res = self.client.post('/api/v1/projects/', {
            "title": "x", "property": self.prop1_a.id, "category": "HVAC", "fiscal_period": "FY2025",
            "budget_amount": "10.00", "org": self.org2.id, "org_id": self.org2.id, "submitted_by": self.admin_org2.id,
        })
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['org_id'], self.org1.id)
        self.assertEqual(res.data['submitted_by'], self.pm_prop1_a.id)

    def test_create_without_optional_actual_cost(self):
        self.client.force_authenticate(user=self.pm_prop1_a)
        res = self.client.post('/api/v1/projects/', {
            "title": "No actuals yet", "property": self.prop1_a.id, "category": "HVAC",
            "fiscal_period": "FY2025", "budget_amount": "10.00",
        })
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['actual_cost'], '0.00')

    def test_closed_vocabularies_are_validated(self):
        self.client.force_authenticate(user=self.pm_prop1_a)
        base = {"title": "x", "property": self.prop1_a.id, "category": "HVAC", "fiscal_period": "FY2025", "budget_amount": "10.00"}
        self.assertEqual(self.client.post('/api/v1/projects/', {**base, "category": "Nope"}).status_code, 400)
        self.assertEqual(self.client.post('/api/v1/projects/', {**base, "fiscal_period": "FY1999"}).status_code, 400)

    def test_malformed_filters_are_400_not_500(self):
        self.client.force_authenticate(user=self.pm_prop1_a)
        self.assertEqual(self.client.get('/api/v1/projects/?property_id=abc').status_code, 400)
        self.assertEqual(self.client.get('/api/v1/properties/budgets/?property_id=abc').status_code, 400)
        self.assertEqual(self.client.get('/api/v1/analytics/dashboard/?fiscal_period=' + 'X' * 40).status_code, 400)
        self.assertEqual(self.client.get('/api/v1/analytics/dashboard/?fiscal_period=FY1999').status_code, 400)

    def test_entitlement_revocation_applies_to_existing_session(self):
        self.client.force_authenticate(user=self.pm_prop1_a)
        self.assertEqual(self.client.get(f'/api/v1/projects/{self.proj_1a.id}/').status_code, 200)
        UserPropertyAccess.objects.filter(user=self.pm_prop1_a).delete()
        self.assertEqual(self.client.get(f'/api/v1/projects/{self.proj_1a.id}/').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/analytics/dashboard/').data['kpis']['project_count'], 0)

    def test_analytics_isolated_by_tenant_and_property_entitlement(self):
        # PM Org 1 analytics should ONLY include prop1_a ($50,000 budget), NOT prop1_b ($80,000)
        self.client.force_authenticate(user=self.pm_prop1_a)
        res = self.client.get('/api/v1/analytics/dashboard/?fiscal_period=FY2025')
        self.assertEqual(res.status_code, 200)
        kpis = res.data['kpis']
        self.assertEqual(kpis['total_budget'], 50000.0)
        self.assertEqual(kpis['total_actual'], 45000.0)
        self.assertEqual(kpis['project_count'], 1)
