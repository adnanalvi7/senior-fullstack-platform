import logging
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError
from common.exceptions import ConflictException
from apps.projects.models import Project
from apps.approvals.models import ApprovalEvent
from apps.analytics.services import AnalyticsService

logger = logging.getLogger(__name__)

# Backwards-compatible import location.
__all__ = ['ApprovalWorkflowService', 'ConflictException']


class ApprovalWorkflowService:
    """
    Authoritative state machine governing project approval workflows.
    Enforces tenant/property scope, role entitlement, valid transitions, segregation of duties
    and concurrent update safety (row lock + state validation after the lock).
    """

    TRANSITIONS = {
        'submit': {
            'allowed_from': ['draft'],
            'to_status': 'submitted',
            'allowed_roles': ['property_manager', 'org_admin'],
        },
        'manager_approve': {
            'allowed_from': ['submitted'],
            'to_status': 'manager_review',
            'allowed_roles': ['property_manager', 'approver', 'org_admin'],
        },
        'finance_approve': {
            'allowed_from': ['manager_review'],
            'to_status': 'finance_review',
            'allowed_roles': ['approver', 'org_admin'],
        },
        'final_approve': {
            'allowed_from': ['finance_review'],
            'to_status': 'approved',
            'allowed_roles': ['approver', 'org_admin'],
        },
        'reject': {
            'allowed_from': ['submitted', 'manager_review', 'finance_review'],
            'to_status': 'rejected',
            'allowed_roles': ['property_manager', 'approver', 'org_admin'],
        },
    }

    # Sign-off levels subject to segregation of duties.
    APPROVAL_ACTIONS = ('manager_approve', 'finance_approve', 'final_approve')
    APPROVAL_LEVEL_STATUSES = ('manager_review', 'finance_review', 'approved')

    @classmethod
    def execute_transition(cls, project_id: int, user, action: str, notes: str = ""):
        if action not in cls.TRANSITIONS:
            raise ValidationError(f"Invalid approval action '{action}'. Valid actions: {list(cls.TRANSITIONS.keys())}")

        transition_rule = cls.TRANSITIONS[action]

        with transaction.atomic():
            # Same RLS scope as every other endpoint (out of scope == nonexistent == 404),
            # with an exclusive row lock against concurrent approvals and edits.
            try:
                project = Project.objects.for_user(user).select_for_update().get(id=project_id)
            except Project.DoesNotExist:
                raise NotFound("Project not found.") from None

            if user.role not in transition_rule['allowed_roles']:
                raise PermissionDenied(f"Role '{user.role}' is not authorized to execute action '{action}'.")

            # State validation happens after the lock, against the committed state.
            old_status = project.status
            if old_status not in transition_rule['allowed_from']:
                raise ConflictException(
                    f"Cannot execute '{action}' on project with status '{old_status}'. "
                    f"Expected status in {transition_rule['allowed_from']}."
                )

            if action in cls.APPROVAL_ACTIONS:
                cls._enforce_segregation_of_duties(project, user)

            project.status = transition_rule['to_status']
            if action == 'submit' and not project.submitted_by_id:
                project.submitted_by = user
            project.save(update_fields=['status', 'submitted_by', 'updated_at'])

            event = ApprovalEvent.objects.create(
                project=project,
                org_id=project.org_id,
                property_id=project.property_id,
                from_status=old_status,
                to_status=project.status,
                actor=user,
                notes=notes,
                created_at=timezone.now(),
            )

            # Outbox row is part of this transaction; the task is enqueued on commit.
            AnalyticsService.mark_buckets_dirty(project.org_id, [(project.property_id, project.fiscal_period)])
            transaction.on_commit(lambda: cls._broadcast(project, event, user))

            return project, event

    @classmethod
    def _enforce_segregation_of_duties(cls, project, user):
        """
        Policy (see DESIGN.md §5): the submitter may not sign off any approval level, and no
        one may sign off more than one level of the same project. org_admin is the documented
        break-glass role and is exempt (its actions are still audited).
        """
        if user.role == 'org_admin':
            return
        if project.submitted_by_id == user.id:
            raise PermissionDenied("Segregation of duties: the submitter cannot approve their own request.")
        already_signed = ApprovalEvent.objects.filter(
            project_id=project.id, actor_id=user.id, to_status__in=cls.APPROVAL_LEVEL_STATUSES,
        ).exists()
        if already_signed:
            raise PermissionDenied("Segregation of duties: you have already signed off a level of this project.")

    @classmethod
    def _broadcast(cls, project, event, user):
        """Executed only after the transaction commits: rolled-back transitions never publish."""
        try:
            from apps.approvals.consumers import broadcast_approval_event
            broadcast_approval_event(project, event, user)
        except Exception as e:
            logger.error(f"Failed to broadcast real-time event for project {project.id}: {e}")
