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
