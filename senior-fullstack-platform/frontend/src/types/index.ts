export type Role = 'org_admin' | 'property_manager' | 'approver' | 'viewer';

export type ProjectStatus =
  | 'draft'
  | 'submitted'
  | 'manager_review'
  | 'finance_review'
  | 'approved'
  | 'rejected';

export interface User {
  id: number;
  email: string;
  role: Role;
  org_id: number;
  org_name: string;
  property_ids: number[];
}

export interface Property {
  id: number;
  org_id: number;
  name: string;
  code: string;
  created_at: string;
}

export interface Budget {
  id: number;
  org_id: number;
  property_id: number;
  property_name: string;
  property_code: string;
  fiscal_period: string;
  allocated_amount: string;
}

export interface Project {
  id: number;
  org_id: number;
  property: number;
  property_name: string;
  property_code: string;
  title: string;
  category: string;
  fiscal_period: string;
  budget_amount: string;
  actual_cost: string;
  status: ProjectStatus;
  submitted_by: number | null;
  submitted_by_email: string | null;
  variance_amount: string;
  variance_percentage: number;
  created_at: string;
  updated_at: string;
}

export interface ApprovalEvent {
  id: number;
  project_id: number;
  org_id: number;
  property_id: number;
  from_status: string;
  to_status: string;
  actor_id: number | null;
  actor_email: string;
  notes: string;
  created_at: string;
}

export interface DashboardKPIs {
  total_budget: number;
  total_actual: number;
  total_variance: number;
  variance_percentage: number;
  project_count: number;
  pending_approval_count: number;
  avg_cycle_time_hours: number;
}

export interface CategorySpend {
  category: string;
  actual_spend: number;
}

export interface StatusDistribution {
  status: string;
  count: number;
}

export interface DashboardData {
  fiscal_period: string;
  property_count: number;
  /** Oldest rollup timestamp in the view: how fresh the numbers are. */
  as_of: string | null;
  kpis: DashboardKPIs;
  category_spend: CategorySpend[];
  status_distribution: StatusDistribution[];
}

export interface AuthResponse {
  access: string;
  refresh: string;
  user: User;
}

export interface PaginatedResponse<T> {
  count: number;
  total_pages: number;
  current_page: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/** Server -> client WebSocket messages (backend/apps/approvals/consumers.py). */
export interface ApprovalUpdateEvent {
  event_id: number;
  project_id: number;
  property_id: number;
  title: string;
  category: string;
  fiscal_period: string;
  old_status: ProjectStatus;
  new_status: ProjectStatus;
  actor_id: number | null;
  actor_email: string;
  notes: string;
  timestamp: string;
}

export interface AnalyticsUpdateEvent {
  property_id: number;
  fiscal_period: string;
}

export type ServerMessage =
  | { type: 'connected'; org_id: number; message: string }
  | { type: 'pong'; ts: number }
  | { type: 'approval_update'; data: ApprovalUpdateEvent }
  | { type: 'analytics_update'; data: AnalyticsUpdateEvent };

export interface NewProjectPayload {
  title: string;
  property: number;
  category: string;
  fiscal_period: string;
  budget_amount: string;
  actual_cost: string;
}
