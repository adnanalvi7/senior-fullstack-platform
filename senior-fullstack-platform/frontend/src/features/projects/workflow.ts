import { Project, ProjectStatus, Role, User } from '../../types';

/**
 * Client mirror of ApprovalWorkflowService.TRANSITIONS (backend/apps/approvals/services.py).
 * Used only to decide which buttons to show; the server remains the authority and
 * re-validates every action (role, scope, state, segregation of duties).
 */
export type WorkflowAction = 'submit' | 'manager_approve' | 'finance_approve' | 'final_approve' | 'reject';

interface TransitionRule {
  from: ProjectStatus[];
  to: ProjectStatus;
  roles: Role[];
  /** Sign-off levels: the submitter may not perform them (org_admin is exempt). */
  approvalLevel: boolean;
}

export const TRANSITIONS: Record<WorkflowAction, TransitionRule> = {
  submit: { from: ['draft'], to: 'submitted', roles: ['property_manager', 'org_admin'], approvalLevel: false },
  manager_approve: {
    from: ['submitted'],
    to: 'manager_review',
    roles: ['property_manager', 'approver', 'org_admin'],
    approvalLevel: true,
  },
  finance_approve: { from: ['manager_review'], to: 'finance_review', roles: ['approver', 'org_admin'], approvalLevel: true },
  final_approve: { from: ['finance_review'], to: 'approved', roles: ['approver', 'org_admin'], approvalLevel: true },
  reject: {
    from: ['submitted', 'manager_review', 'finance_review'],
    to: 'rejected',
    roles: ['property_manager', 'approver', 'org_admin'],
    approvalLevel: false,
  },
};

export const availableActions = (project: Project, user: User | null): WorkflowAction[] => {
  if (!user) return [];
  return (Object.keys(TRANSITIONS) as WorkflowAction[]).filter((action) => {
    const rule = TRANSITIONS[action];
    if (!rule.from.includes(project.status) || !rule.roles.includes(user.role)) return false;
    if (rule.approvalLevel && user.role !== 'org_admin' && project.submitted_by === user.id) return false;
    return true;
  });
};

export const isWorkflowAction = (value: string): value is WorkflowAction => value in TRANSITIONS;
