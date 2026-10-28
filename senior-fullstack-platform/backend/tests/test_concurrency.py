"""
Real parallel execution against PostgreSQL (row locks are a no-op on SQLite, so these are
skipped there). Each thread uses its own DB connection via the Django test client.
"""
import threading
import unittest

from django.db import connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from apps.accounts.models import Organization, User, UserPropertyAccess
from apps.approvals.models import ApprovalEvent
from apps.properties.models import Property
from apps.projects.models import Project


@unittest.skipUnless(connection.vendor == 'postgresql', "row-level locking requires PostgreSQL")
class TestConcurrentWorkflow(TransactionTestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="C", slug="c")
        self.prop = Property.objects.create(org=self.org, name="P", code="P")
        self.users = []
        for i in range(6):
            u = User.objects.create_user(email=f"a{i}@c.com", password="password", org=self.org, role="approver")
            UserPropertyAccess.objects.create(user=u, property=self.prop)
            self.users.append(u)
        self.pm = User.objects.create_user(email="pm@c.com", password="password", org=self.org, role="property_manager")
        UserPropertyAccess.objects.create(user=self.pm, property=self.prop)

    def project(self, status):
        return Project.objects.create(org=self.org, property=self.prop, title="t", category="HVAC",
                                      fiscal_period="FY2025", budget_amount="100.00", status=status)

    def run_parallel(self, calls):
        barrier = threading.Barrier(len(calls))
        results = [None] * len(calls)

        def worker(i, user, method, url, body):
            client = APIClient()
            client.force_authenticate(user=user)
            barrier.wait()
            results[i] = getattr(client, method)(url, body, format='json').status_code
            connection.close()

        threads = [threading.Thread(target=worker, args=(i, *c)) for i, c in enumerate(calls)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return results

    def test_simultaneous_approvals_have_exactly_one_winner(self):
        p = self.project('submitted')
        codes = self.run_parallel([(u, 'post', f'/api/v1/projects/{p.id}/approve/', {'action': 'manager_approve'}) for u in self.users])
        self.assertEqual(sorted(codes), [200] + [409] * (len(self.users) - 1))
        self.assertEqual(ApprovalEvent.objects.filter(project=p).count(), 1)

    def test_approve_vs_reject_race_is_consistent(self):
        p = self.project('finance_review')
        codes = self.run_parallel([
            (self.users[0], 'post', f'/api/v1/projects/{p.id}/approve/', {'action': 'final_approve'}),
            (self.users[1], 'post', f'/api/v1/projects/{p.id}/approve/', {'action': 'reject'}),
        ])
        self.assertEqual(sorted(codes), [200, 409])
        p.refresh_from_db()
        events = list(ApprovalEvent.objects.filter(project=p))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].to_status, p.status)

    def test_edit_racing_approval_never_reverts_status(self):
        for _ in range(10):
            p = self.project('submitted')
            self.run_parallel([
                (self.pm, 'patch', f'/api/v1/projects/{p.id}/', {'actual_cost': '5.00'}),
                (self.users[0], 'post', f'/api/v1/projects/{p.id}/approve/', {'action': 'manager_approve'}),
            ])
            p.refresh_from_db()
            last = ApprovalEvent.objects.filter(project=p).order_by('-id').first()
            self.assertIsNotNone(last)
            self.assertEqual(p.status, last.to_status)
