-- Initial PostgreSQL schema. Keep in sync with ../schema.sql.

CREATE TABLE public.profiles (
    id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    email varchar(320) NOT NULL,
    display_name varchar(200) NOT NULL,
    role varchar(32) NOT NULL DEFAULT 'viewer',
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ix_profiles_email ON public.profiles (email);

CREATE TABLE public.customers (
    id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name varchar(200) NOT NULL,
    email varchar(320) NOT NULL,
    company_name varchar(200),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_customers_email ON public.customers (email);

CREATE TABLE public.subscriptions (
    id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    customer_id varchar(36) NOT NULL REFERENCES public.customers (id),
    plan_name varchar(80) NOT NULL,
    status varchar(32) NOT NULL DEFAULT 'active',
    seat_count integer NOT NULL DEFAULT 1,
    seats_used integer NOT NULL DEFAULT 0,
    storage_limit_bytes bigint NOT NULL DEFAULT 0,
    storage_used_bytes bigint NOT NULL DEFAULT 0,
    current_period_start timestamptz,
    current_period_end timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_subscriptions_seat_count CHECK (seat_count >= 0),
    CONSTRAINT ck_subscriptions_seats_used CHECK (seats_used >= 0),
    CONSTRAINT ck_subscriptions_storage_limit CHECK (storage_limit_bytes >= 0),
    CONSTRAINT ck_subscriptions_storage_used CHECK (storage_used_bytes >= 0)
);
CREATE INDEX ix_subscriptions_customer_id ON public.subscriptions (customer_id);

CREATE TABLE public.workspaces (
    id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    customer_id varchar(36) NOT NULL REFERENCES public.customers (id),
    name varchar(200) NOT NULL,
    slug varchar(120) NOT NULL,
    settings json NOT NULL DEFAULT '{}'::json,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_workspaces_customer_slug UNIQUE (customer_id, slug)
);
CREATE INDEX ix_workspaces_customer_id ON public.workspaces (customer_id);

CREATE TABLE public.products (
    id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name varchar(200) NOT NULL,
    slug varchar(120) NOT NULL UNIQUE,
    description text NOT NULL DEFAULT '',
    details json NOT NULL DEFAULT '{}'::json,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.tickets (
    id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    ticket_number varchar(32) NOT NULL UNIQUE,
    customer_id varchar(36) NOT NULL REFERENCES public.customers (id),
    subject varchar(300) NOT NULL,
    channel varchar(32) NOT NULL,
    status varchar(40) NOT NULL DEFAULT 'new',
    category varchar(32),
    severity varchar(32),
    severity_reason text,
    summary text,
    external_id varchar(200),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ticket_category CHECK (
        category IS NULL OR category IN (
            'login_issue',
            'billing',
            'api_failure',
            'workspace_permissions',
            'storage_quota',
            'integration',
            'feature_request',
            'account',
            'security',
            'other'
        )
    ),
    CONSTRAINT uq_tickets_channel_external_id UNIQUE (channel, external_id)
);
CREATE INDEX ix_tickets_customer_id ON public.tickets (customer_id);
CREATE INDEX ix_tickets_status ON public.tickets (status);
CREATE INDEX ix_tickets_status_created_at ON public.tickets (status, created_at);

CREATE TABLE public.ticket_messages (
    id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    ticket_id varchar(36) NOT NULL REFERENCES public.tickets (id),
    sender_type varchar(32) NOT NULL,
    sender_name varchar(200),
    body text NOT NULL,
    is_internal boolean NOT NULL DEFAULT false,
    external_id varchar(200),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_ticket_messages_ticket_id ON public.ticket_messages (ticket_id);
CREATE INDEX ix_ticket_messages_ticket_created_at
    ON public.ticket_messages (ticket_id, created_at);

CREATE TABLE public.support_articles (
    id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    slug varchar(160) NOT NULL UNIQUE,
    title varchar(300) NOT NULL,
    category varchar(32),
    tags json NOT NULL DEFAULT '[]'::json,
    summary text NOT NULL DEFAULT '',
    content text NOT NULL,
    source_path varchar(500),
    is_published boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ticket_category CHECK (
        category IS NULL OR category IN (
            'login_issue',
            'billing',
            'api_failure',
            'workspace_permissions',
            'storage_quota',
            'integration',
            'feature_request',
            'account',
            'security',
            'other'
        )
    )
);

CREATE TABLE public.incidents (
    id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    title varchar(300) NOT NULL,
    description text NOT NULL DEFAULT '',
    status varchar(32) NOT NULL DEFAULT 'active',
    severity varchar(32) NOT NULL,
    affected_services json NOT NULL DEFAULT '[]'::json,
    started_at timestamptz,
    resolved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.workflow_runs (
    id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    ticket_id varchar(36) NOT NULL REFERENCES public.tickets (id),
    status varchar(32) NOT NULL DEFAULT 'queued',
    state json NOT NULL DEFAULT '{}'::json,
    thread_id varchar(36) UNIQUE,
    started_at timestamptz,
    finished_at timestamptz,
    token_usage json NOT NULL DEFAULT '{}'::json,
    estimated_cost numeric(12, 6) NOT NULL DEFAULT 0,
    error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_workflow_runs_ticket_id ON public.workflow_runs (ticket_id);
CREATE INDEX ix_workflow_runs_ticket_created_at
    ON public.workflow_runs (ticket_id, created_at);

CREATE TABLE public.workflow_events (
    id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    workflow_run_id varchar(36) NOT NULL REFERENCES public.workflow_runs (id),
    event_type varchar(40) NOT NULL,
    node_name varchar(80),
    tool_name varchar(120),
    payload json NOT NULL DEFAULT '{}'::json,
    duration_ms integer,
    input_tokens integer,
    output_tokens integer,
    estimated_cost numeric(12, 6) NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_workflow_events_workflow_run_id
    ON public.workflow_events (workflow_run_id);
CREATE INDEX ix_workflow_events_run_created_at
    ON public.workflow_events (workflow_run_id, created_at);

CREATE TABLE public.resolution_actions (
    id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    workflow_run_id varchar(36) NOT NULL REFERENCES public.workflow_runs (id),
    action_type varchar(100) NOT NULL,
    arguments json NOT NULL DEFAULT '{}'::json,
    status varchar(32) NOT NULL DEFAULT 'planned',
    approval_required boolean NOT NULL DEFAULT false,
    result json,
    executed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_resolution_actions_workflow_run_id
    ON public.resolution_actions (workflow_run_id);

CREATE TABLE public.approval_requests (
    id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    ticket_id varchar(36) NOT NULL REFERENCES public.tickets (id),
    workflow_run_id varchar(36) NOT NULL REFERENCES public.workflow_runs (id),
    action varchar(100) NOT NULL,
    summary text NOT NULL,
    status varchar(32) NOT NULL DEFAULT 'pending',
    requested_at timestamptz NOT NULL DEFAULT now(),
    decided_at timestamptz,
    decided_by_id varchar(36) REFERENCES public.profiles (id),
    reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_approval_requests_ticket_id ON public.approval_requests (ticket_id);
CREATE INDEX ix_approval_requests_workflow_run_id
    ON public.approval_requests (workflow_run_id);

CREATE TABLE public.escalations (
    id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    ticket_id varchar(36) NOT NULL REFERENCES public.tickets (id),
    workflow_run_id varchar(36) REFERENCES public.workflow_runs (id),
    team varchar(120) NOT NULL,
    reason text NOT NULL,
    status varchar(32) NOT NULL DEFAULT 'open',
    resolved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_escalations_ticket_id ON public.escalations (ticket_id);
CREATE INDEX ix_escalations_workflow_run_id ON public.escalations (workflow_run_id);

CREATE TABLE public.customer_memory (
    id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    customer_id varchar(36) NOT NULL REFERENCES public.customers (id),
    source_ticket_id varchar(36) REFERENCES public.tickets (id),
    kind varchar(40) NOT NULL,
    content text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_customer_memory_customer_id ON public.customer_memory (customer_id);
CREATE INDEX ix_customer_memory_source_ticket_id
    ON public.customer_memory (source_ticket_id);
CREATE INDEX ix_customer_memory_customer_created_at
    ON public.customer_memory (customer_id, created_at);

CREATE TABLE public.audit_logs (
    id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    actor_id varchar(36) REFERENCES public.profiles (id),
    request_id varchar(100),
    action varchar(120) NOT NULL,
    method varchar(12),
    path varchar(500),
    target_type varchar(80),
    target_id varchar(36),
    status_code integer,
    details json NOT NULL DEFAULT '{}'::json,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_logs_actor_id ON public.audit_logs (actor_id);
CREATE INDEX ix_audit_logs_request_id ON public.audit_logs (request_id);

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $function$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$function$;

CREATE TRIGGER trg_profiles_updated_at BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_customers_updated_at BEFORE UPDATE ON public.customers
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_subscriptions_updated_at BEFORE UPDATE ON public.subscriptions
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_workspaces_updated_at BEFORE UPDATE ON public.workspaces
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_products_updated_at BEFORE UPDATE ON public.products
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_tickets_updated_at BEFORE UPDATE ON public.tickets
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_ticket_messages_updated_at BEFORE UPDATE ON public.ticket_messages
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_support_articles_updated_at BEFORE UPDATE ON public.support_articles
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_incidents_updated_at BEFORE UPDATE ON public.incidents
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_workflow_runs_updated_at BEFORE UPDATE ON public.workflow_runs
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_workflow_events_updated_at BEFORE UPDATE ON public.workflow_events
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_resolution_actions_updated_at BEFORE UPDATE ON public.resolution_actions
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_approval_requests_updated_at BEFORE UPDATE ON public.approval_requests
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_escalations_updated_at BEFORE UPDATE ON public.escalations
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_customer_memory_updated_at BEFORE UPDATE ON public.customer_memory
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_audit_logs_updated_at BEFORE UPDATE ON public.audit_logs
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
