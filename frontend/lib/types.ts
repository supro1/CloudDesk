export type UserRole = "viewer" | "agent" | "admin";
export type TicketCategory =
  | "login_issue"
  | "billing"
  | "api_failure"
  | "workspace_permissions"
  | "storage_quota"
  | "integration"
  | "feature_request"
  | "account"
  | "security"
  | "other";
export type TicketSeverity = "low" | "medium" | "high" | "critical";
export type TicketChannel = "email" | "chat" | "web" | "api";
export type TicketStatus =
  | "new"
  | "in_progress"
  | "waiting_on_customer"
  | "waiting_on_approval"
  | "escalated"
  | "resolved"
  | "closed";

export interface AuthenticatedProfile {
  id: string;
  email: string;
  role: UserRole;
  display_name: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: AuthenticatedProfile;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Ticket {
  id: string;
  ticket_number: string;
  customer_id: string;
  subject: string;
  channel: TicketChannel;
  status: TicketStatus;
  category: TicketCategory | null;
  severity: TicketSeverity | null;
  severity_reason: string | null;
  summary: string | null;
  external_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface TicketMessage {
  id: string;
  ticket_id: string;
  sender_type: string;
  sender_name: string | null;
  body: string;
  is_internal: boolean;
  created_at: string;
}

export interface TicketCustomerSummary {
  id: string;
  name: string;
  email: string;
  company_name: string | null;
}

export interface TicketWorkflowSummary {
  id: string;
  status: string;
}

export interface TicketApprovalSummary {
  id: string;
  ticket_id: string;
  workflow_id: string;
  action: string;
  summary: string;
  status: string;
  requested_at: string;
  decided_at: string | null;
  decided_by: string | null;
}

export interface TicketDetail extends Ticket {
  messages: TicketMessage[];
  customer: TicketCustomerSummary;
  workflow?: TicketWorkflowSummary | null;
  approval?: TicketApprovalSummary | null;
}

export interface WorkflowDiagnosisStep {
  number: number;
  instruction: string;
}

export interface WorkflowEvidence {
  id: string;
  title: string;
  source: string;
  snippet: string;
  score: number;
  url: string;
  article_id: string;
}

export interface WorkflowStatus {
  workflow_id: string;
  status: string;
  current_node: string | null;
  completed_nodes: string[];
  category: TicketCategory | null;
  severity: TicketSeverity | null;
  severity_reason: string | null;
  summary: string | null;
  risk_level: "low" | "high" | null;
  evidence: WorkflowEvidence[];
  diagnosis: {
    probable_causes: string[];
    steps: WorkflowDiagnosisStep[];
    service_status: Record<string, unknown> | null;
  } | null;
  resolution: {
    summary: string;
    customer_reply: string;
    output_valid: boolean;
    output_issues: string[];
  } | null;
  token_usage: Record<string, number>;
  error: string | null;
}

export interface WorkflowStartResponse {
  workflow_id: string;
  status: "queued";
}

export interface ApprovalDecisionResponse {
  approval: TicketApprovalSummary;
  workflow_status: string;
}

export interface Customer {
  id: string;
  name: string;
  email: string;
  company_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeArticle {
  id: string;
  slug: string;
  title: string;
  category: TicketCategory | null;
  tags: string[];
  summary: string;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface Escalation {
  id: string;
  ticket_id: string;
  workflow_run_id: string | null;
  team: string;
  reason: string;
  status: string;
  resolved_at: string | null;
  created_at: string;
}

export type TicketFilters = Partial<Pick<Ticket, "status" | "category" | "severity" | "channel" | "customer_id">>;
export type CustomerFilters = { email?: string; company_name?: string };
export type EscalationFilters = { status?: string; team?: string; ticket_id?: string };
export type Pagination = { limit?: number; offset?: number };
