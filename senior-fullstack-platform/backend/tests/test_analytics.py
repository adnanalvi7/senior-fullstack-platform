from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core.cache import cache, caches
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Organization, User, UserPropertyAccess
from apps.analytics.models import PendingRollup, PropertyAggregateRollup
from apps.analytics.services import AnalyticsService
from apps.analytics.tasks import sweep_pending_rollups
from apps.approvals.models import ApprovalEvent
from apps.properties.models import Property
from apps.projects.models import Project
from common.cache import redis_circuit_open, reset_redis_circuit


class AnalyticsTestBase(APITestCase):
    def setUp(self):
        cache.clear()
        reset_redis_circuit()
        self.addCleanup(reset_redis_circuit)
        self.org = Organization.objects.create(name="Analytics Org", slug="analytics-org")
        self.prop = Property.objects.create(org=self.org, name="Analytics Prop", code="AP-1")
        self.prop2 = Property.objects.create(org=self.org, name="Analytics Prop 2", code="AP-2")
        self.admin = User.objects.create_user(email="admin@analytics.com", password="password", org=self.org, role="org_admin")
        self.pm = User.objects.create_user(email="pm@analytics.com", password="password", org=self.org, role="property_manager")
        UserPropertyAccess.objects.create(user=self.pm, property=self.prop)
        UserPropertyAccess.objects.create(user=self.pm, property=self.prop2)

        def mk(prop, fp, budget, actual, status, category="HVAC"):
            return Project.objects.create(org=self.org, property=prop, title="p", category=category, fiscal_period=fp,
                                          budget_amount=Decimal(budget), actual_cost=Decimal(actual), status=status)
        self.p1 = mk(self.prop, "FY2025", "100000.00", "105000.00", "approved")
        self.p2 = mk(self.prop, "FY2025", "200000.00", "190000.00", "submitted", "Roofing")
        self.p3 = mk(self.prop, "FY2025", "50000.00", "52000.00", "draft")
        self.p4 = mk(self.prop2, "FY2024", "10000.01", "9999.99", "finance_review", "Plumbing")

    def dashboard(self, user=None, **params):
        self.client.force_authenticate(user=user or self.admin)
        res = self.client.get('/api/v1/analytics/dashboard/', params)
        self.assertEqual(res.status_code, 200, res.data)
        return res.data

    def ground_truth(self, prop_ids, fiscal_period='ALL'):
        qs = Project.objects.filter(property_id__in=prop_ids)
        if fiscal_period != 'ALL':
            qs = qs.filter(fiscal_period=fiscal_period)
        agg = qs.aggregate(b=Sum('budget_amount'), a=Sum('actual_cost'), n=Count('id'))
        return {
            'total_budget': float(agg['b'] or 0), 'total_actual': float(agg['a'] or 0),
            'project_count': agg['n'],
            'pending_approval_count': qs.filter(status__in=['submitted', 'manager_review', 'finance_review']).count(),
        }

    def assert_matches_truth(self, prop_ids, fiscal_period='ALL', user=None):
        kpis = self.dashboard(user, fiscal_period=fiscal_period)['kpis']
        truth = self.ground_truth(prop_ids, fiscal_period)
        for key, value in truth.items():
            self.assertAlmostEqual(kpis[key], value, places=2, msg=f"{key} ({fiscal_period})")


class TestAggregationCorrectness(AnalyticsTestBase):
    def test_precomputed_bucket_matches_ground_truth(self):
        rollup = AnalyticsService.compute_property_rollup(self.prop.id, "FY2025")
        self.assertEqual(rollup.budget_total, Decimal("350000.00"))
        self.assertEqual(rollup.actual_cost_total, Decimal("347000.00"))
        self.assertEqual(rollup.variance_amount, Decimal("-3000.00"))
        self.assertEqual(rollup.project_count, 3)
        self.assertEqual(rollup.pending_approval_count, 1)
        self.assertEqual(Decimal(rollup.category_spend['HVAC']), Decimal('157000.00'))
        self.assertEqual(Decimal(rollup.category_spend['Roofing']), Decimal('190000.00'))

    def test_dashboard_all_periods_multi_property_matches_ground_truth(self):
        all_props = [self.prop.id, self.prop2.id]
        for fp in ('ALL', 'FY2024', 'FY2025', 'FY2026'):
            self.assert_matches_truth(all_props, fp)
        data = self.dashboard()
        self.assertEqual(data['kpis']['variance_percentage'], round((347000 + 9999.99 - 360000.01) / 360000.01 * 100, 2))
        self.assertEqual({c['category']: c['actual_spend'] for c in data['category_spend']},
                         {'HVAC': 157000.0, 'Roofing': 190000.0, 'Plumbing': 9999.99})

    def test_all_periods_is_never_stored(self):
        self.dashboard()
        self.assertFalse(PropertyAggregateRollup.objects.filter(fiscal_period='ALL').exists())

    def test_unknown_fiscal_period_is_rejected_and_not_persisted(self):
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.get('/api/v1/analytics/dashboard/?fiscal_period=FY1999').status_code, 400)
        self.assertFalse(PropertyAggregateRollup.objects.exclude(fiscal_period__in=['FY2024', 'FY2025', 'FY2026']).exists())

    def test_cycle_time_is_project_weighted_not_mean_of_means(self):
        """1 project at 1000h on one property, 99 at 10h on another -> 19.9h (not 505h)."""
        t0 = timezone.now() - timedelta(days=100)
        for prop, hours, n in ((self.prop, 1000, 1), (self.prop2, 10, 99)):
            for _ in range(n):
                p = Project.objects.create(org=self.org, property=prop, title="c", category="HVAC", fiscal_period="FY2026",
                                           budget_amount=Decimal("1.00"), status="approved")
                ApprovalEvent.objects.create(project=p, org=self.org, property=prop, from_status="draft", to_status="submitted", created_at=t0)
                ApprovalEvent.objects.create(project=p, org=self.org, property=prop, from_status="finance_review", to_status="approved",
                                             created_at=t0 + timedelta(hours=hours))
        kpis = self.dashboard(fiscal_period='FY2026')['kpis']
        self.assertAlmostEqual(kpis['avg_cycle_time_hours'], 19.9, places=2)


class TestFreshnessAfterWrites(AnalyticsTestBase):
    """Every write path must leave every affected view (including 'ALL') equal to ground truth."""

    def write(self, method, url, data=None, user=None):
        self.client.force_authenticate(user=user or self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            res = getattr(self.client, method)(url, data or {})
        self.assertLess(res.status_code, 300, getattr(res, 'data', None))
        return res

    def assert_all_views_fresh(self):
        props = [self.prop.id, self.prop2.id]
        for fp in ('ALL', 'FY2024', 'FY2025', 'FY2026'):
            self.assert_matches_truth(props, fp)
        self.assertFalse(PendingRollup.objects.exists())

    def test_create_update_move_approve_delete(self):
        self.assert_all_views_fresh()  # primes the cache
        pid = self.write('post', '/api/v1/projects/', {
            'title': 'new', 'property': self.prop.id, 'category': 'HVAC', 'fiscal_period': 'FY2025',
            'budget_amount': '12345.67', 'actual_cost': '2000.00'}).data['id']
        self.assert_all_views_fresh()
        self.write('patch', f'/api/v1/projects/{pid}/', {'actual_cost': '9999.99'})
        self.assert_all_views_fresh()
        self.write('patch', f'/api/v1/projects/{pid}/', {'budget_amount': '55555.55', 'category': 'Roofing'})
        self.assert_all_views_fresh()
        self.write('patch', f'/api/v1/projects/{pid}/', {'fiscal_period': 'FY2024'})   # old period must shrink
        self.assert_all_views_fresh()
        self.write('patch', f'/api/v1/projects/{pid}/', {'property': self.prop2.id})   # old property must shrink
        self.assert_all_views_fresh()
        self.write('delete', f'/api/v1/projects/{pid}/')
        self.assert_all_views_fresh()
        self.write('post', f'/api/v1/projects/{self.p3.id}/approve/', {'action': 'submit'})
        self.assert_all_views_fresh()

    def test_property_scoped_view_refreshes(self):
        self.assert_matches_truth([self.prop.id, self.prop2.id], 'ALL', user=self.pm)
        self.write('post', f'/api/v1/projects/{self.p3.id}/approve/', {'action': 'submit'})
        self.assert_matches_truth([self.prop.id, self.prop2.id], 'ALL', user=self.pm)


class TestCacheAndWorkerResilience(AnalyticsTestBase):
    def test_invalidation_is_tenant_local_version_bump(self):
        other = Organization.objects.create(name="Other", slug="other")
        Property.objects.create(org=other, name="o", code="O")
        other_admin = User.objects.create_user(email="o@o.com", password="password", org=other, role="org_admin")
        self.dashboard(other_admin)
        other_key = f"analytics:org:{other.id}:version"
        before_other = cache.get(other_key)
        self.dashboard()
        before = cache.get(f"analytics:org:{self.org.id}:version")
        AnalyticsService.invalidate_org_caches(self.org.id)
        self.assertEqual(cache.get(f"analytics:org:{self.org.id}:version"), before + 1)
        self.assertEqual(cache.get(other_key), before_other)  # other tenants untouched

    def test_invalidation_never_clears_the_cache(self):
        with mock.patch.object(cache, 'clear') as clear:
            AnalyticsService.invalidate_org_caches(self.org.id)
            cache.delete(f"analytics:org:{self.org.id}:version")
            AnalyticsService.invalidate_org_caches(self.org.id)
        clear.assert_not_called()

    def test_dashboard_survives_cache_outage(self):
        truth = self.ground_truth([self.prop.id, self.prop2.id])
        backend = type(caches['default'])
        boom = mock.Mock(side_effect=ConnectionError("redis down"))
        with mock.patch.object(backend, 'get', boom), mock.patch.object(backend, 'set', boom),                 mock.patch.object(backend, 'get_or_set', boom):
            kpis = self.dashboard()['kpis']
            self.assertTrue(redis_circuit_open())  # first failure opens the breaker …
            calls = boom.call_count
            self.dashboard()                        # … so later requests skip Redis entirely
            self.assertEqual(boom.call_count, calls)
        self.assertAlmostEqual(kpis['total_budget'], truth['total_budget'], places=2)

    def test_lost_task_is_recovered_by_sweep(self):
        """Outbox row written with the change; if the task never runs, the beat sweep repairs it."""
        self.dashboard()
        self.client.force_authenticate(user=self.admin)
        with mock.patch('apps.analytics.tasks.refresh_rollup_bucket.delay', side_effect=ConnectionError("broker down")):
            with self.captureOnCommitCallbacks(execute=True):
                res = self.client.patch(f'/api/v1/projects/{self.p3.id}/', {'actual_cost': '1.00'})
        self.assertEqual(res.status_code, 200)  # the write itself never fails on broker trouble
        self.assertTrue(PendingRollup.objects.filter(property=self.prop, fiscal_period='FY2025').exists())
        reset_redis_circuit()  # broker/Redis back
        PendingRollup.objects.update(requested_at=timezone.now() - timedelta(minutes=5))
        self.assertEqual(sweep_pending_rollups(), 1)
        self.assertFalse(PendingRollup.objects.exists())
        self.assert_matches_truth([self.prop.id, self.prop2.id], 'ALL')

    def test_failed_invalidation_keeps_marker_for_retry(self):
        """Never clear the outbox if the cache could not be invalidated (would serve stale views)."""
        AnalyticsService.mark_buckets_dirty(self.org.id, [(self.prop.id, 'FY2025')])
        with mock.patch.object(cache, 'incr', side_effect=ConnectionError("redis down")):
            with self.assertRaises(ConnectionError):
                AnalyticsService.refresh_bucket(self.prop.id, 'FY2025')
        self.assertTrue(PendingRollup.objects.filter(property=self.prop, fiscal_period='FY2025').exists())

    def test_marker_rerequested_during_compute_is_kept(self):
        AnalyticsService.mark_buckets_dirty(self.org.id, [(self.prop.id, 'FY2025')])
        original = AnalyticsService.compute_property_rollup

        def compute_while_new_write_lands(pid, fp):
            result = original(pid, fp)
            PendingRollup.objects.filter(property_id=pid, fiscal_period=fp).update(requested_at=timezone.now() + timedelta(seconds=1))
            return result
        with mock.patch.object(AnalyticsService, 'compute_property_rollup', side_effect=compute_while_new_write_lands):
            AnalyticsService.refresh_bucket(self.prop.id, 'FY2025')
        self.assertTrue(PendingRollup.objects.filter(property=self.prop, fiscal_period='FY2025').exists())
