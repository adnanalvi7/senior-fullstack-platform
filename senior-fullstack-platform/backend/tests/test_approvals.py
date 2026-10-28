from rest_framework.test import APITestCase
from apps.accounts.models import Organization, User, UserPropertyAccess
from apps.properties.models import Property
from apps.projects.models import Project
from apps.approvals.models import ApprovalEvent

class TestApprovalStateMachine(APITestCase):
    """
    Approval workflow state machine rules, segregation of duties, finalized-state protection
    and audit history. (Parallel-execution safety is covered in test_concurrency.py.)
    """

    def setUp(self):
        self.org = Organization.objects.create(name="Workflow Org", slug="workflow-org")
        self.prop = Property.objects.create(org=self.org, name="Workflow Prop", code="WP-1")

        def user(email, role):
            u = User.objects.create_user(email=email, password="password", org=self.org, role=role)
            if role != 'org_admin':
                UserPropertyAccess.objects.create(user=u, property=self.prop)
            return u

        self.admin = user("admin@wf.com", "org_admin")
        self.pm = user("pm@wf.com", "property_manager")
        self.pm2 = user("pm2@wf.com", "property_manager")
        self.approver = user("approver@wf.com", "approver")
        self.approver2 = user("approver2@wf.com", "approver")
        self.viewer = user("viewer@wf.com", "viewer")

        self.project = Project.objects.create(
            org=self.org, property=self.prop, title="State Machine Project",
            category="HVAC", fiscal_period="FY2025", budget_amount="120000.00", actual_cost="110000.00",
            status="draft", submitted_by=self.pm
        )

    def act(self, user, action, **extra):
        self.client.force_authenticate(user=user)
        return self.client.post(f'/api/v1/projects/{self.project.id}/approve/', {'action': action, **extra})

    def advance_to(self, status):
        path = [('submitted', self.pm, 'submit'), ('manager_review', self.pm2, 'manager_approve'),
                ('finance_review', self.approver, 'finance_approve'), ('approved', self.approver2, 'final_approve')]
        for target, actor, action in path:
            self.assertEqual(self.act(actor, action).status_code, 200)
            if target == status:
                return

    def test_complete_forward_approval_lifecycle(self):
        self.advance_to('approved')
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, 'approved')
        history = self.client.get(f'/api/v1/projects/{self.project.id}/history/')
        self.assertEqual(history.status_code, 200)
        self.assertEqual([e['to_status'] for e in history.data], ['submitted', 'manager_review', 'finance_review', 'approved'])
        self.assertEqual(len({e['actor_id'] for e in history.data}), 4)

    def test_skipping_levels_is_rejected(self):
        res = self.act(self.approver, 'final_approve')
        self.assertEqual(res.status_code, 409)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, 'draft')

    def test_viewer_role_cannot_execute_approvals(self):
        self.assertEqual(self.act(self.viewer, 'submit').status_code, 403)

    def test_approver_cannot_submit(self):
        self.assertEqual(self.act(self.approver, 'submit').status_code, 403)

    def test_rejection_transition(self):
        self.advance_to('submitted')
        res = self.act(self.approver, 'reject', notes='Over budget tolerance')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['project']['status'], 'rejected')
        self.assertEqual(res.data['event']['notes'], 'Over budget tolerance')

    def test_terminal_states_accept_no_transitions(self):
        self.advance_to('approved')
        for action in ('reject', 'final_approve', 'submit'):
            self.assertIn(self.act(self.admin, action).status_code, (409,))

    # ---- segregation of duties -------------------------------------------------
    def test_submitter_cannot_approve_own_request_at_any_level(self):
        self.advance_to('submitted')
        res = self.act(self.pm, 'manager_approve')
        self.assertEqual(res.status_code, 403)
        self.assertIn('Segregation of duties', res.data['error'])

    def test_same_actor_cannot_sign_two_levels(self):
        self.advance_to('finance_review')  # self.approver signed finance
        res = self.act(self.approver, 'final_approve')
        self.assertEqual(res.status_code, 403)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, 'finance_review')

    def test_org_admin_is_documented_break_glass(self):
        self.advance_to('submitted')
        for action in ('manager_approve', 'finance_approve', 'final_approve'):
            self.assertEqual(self.act(self.admin, action).status_code, 200)

    # ---- finalized-state protection & audit retention --------------------------
    def test_submitted_project_scope_is_frozen_but_actuals_accrue(self):
        self.advance_to('approved')
        self.client.force_authenticate(user=self.pm)
        res = self.client.patch(f'/api/v1/projects/{self.project.id}/', {'budget_amount': '999999.00'})
        self.assertEqual(res.status_code, 409)
        res = self.client.patch(f'/api/v1/projects/{self.project.id}/', {'actual_cost': '115000.00'})
        self.assertEqual(res.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(str(self.project.budget_amount), '120000.00')
        self.assertEqual(str(self.project.actual_cost), '115000.00')

    def test_non_draft_projects_cannot_be_deleted_and_audit_survives(self):
        self.advance_to('approved')
        self.client.force_authenticate(user=self.pm)
        res = self.client.delete(f'/api/v1/projects/{self.project.id}/')
        self.assertEqual(res.status_code, 409)
        self.assertEqual(ApprovalEvent.objects.filter(project_id=self.project.id).count(), 4)

    def test_draft_can_be_edited_and_deleted(self):
        self.client.force_authenticate(user=self.pm)
        self.assertEqual(self.client.patch(f'/api/v1/projects/{self.project.id}/', {'title': 'Renamed'}).status_code, 200)
        self.assertEqual(self.client.delete(f'/api/v1/projects/{self.project.id}/').status_code, 204)
