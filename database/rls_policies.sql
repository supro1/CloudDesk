-- Supabase RLS policy set. The API uses the service-role key server-side;
-- browser clients receive read-only access filtered by their support profile.

CREATE OR REPLACE FUNCTION public.current_support_role()
RETURNS text
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $function$
    SELECT p.role
    FROM public.profiles AS p
    WHERE p.id = (SELECT auth.uid())::text
      AND p.is_active
    LIMIT 1
$function$;

REVOKE ALL ON FUNCTION public.current_support_role() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.current_support_role() TO authenticated;

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ticket_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.support_articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workflow_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workflow_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resolution_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.approval_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.escalations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.customer_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY profiles_read_self_or_admin ON public.profiles
    FOR SELECT TO authenticated
    USING (
        (
            id = (SELECT auth.uid())::text
            AND public.current_support_role() IS NOT NULL
        )
        OR public.current_support_role() = 'admin'
    );
CREATE POLICY customers_read_support_roles ON public.customers
    FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
CREATE POLICY subscriptions_read_support_roles ON public.subscriptions
    FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
CREATE POLICY workspaces_read_support_roles ON public.workspaces
    FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
CREATE POLICY products_read_support_roles ON public.products
    FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
CREATE POLICY tickets_read_support_roles ON public.tickets
    FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
CREATE POLICY ticket_messages_read_visible_messages ON public.ticket_messages
    FOR SELECT TO authenticated
    USING (
        public.current_support_role() IN ('agent', 'admin')
        OR (
            public.current_support_role() = 'viewer'
            AND is_internal = false
        )
    );
CREATE POLICY support_articles_read_support_roles ON public.support_articles
    FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
CREATE POLICY incidents_read_support_roles ON public.incidents
    FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
CREATE POLICY workflow_runs_read_support_roles ON public.workflow_runs
    FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('agent', 'admin'));
CREATE POLICY workflow_events_read_support_roles ON public.workflow_events
    FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('agent', 'admin'));
CREATE POLICY resolution_actions_read_support_roles ON public.resolution_actions
    FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('agent', 'admin'));
CREATE POLICY approval_requests_read_support_roles ON public.approval_requests
    FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('agent', 'admin'));
CREATE POLICY escalations_read_support_roles ON public.escalations
    FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('agent', 'admin'));
CREATE POLICY customer_memory_read_support_roles ON public.customer_memory
    FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('agent', 'admin'));
CREATE POLICY audit_logs_read_support_roles ON public.audit_logs
    FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));

REVOKE ALL ON TABLE
    public.profiles,
    public.customers,
    public.subscriptions,
    public.workspaces,
    public.products,
    public.tickets,
    public.ticket_messages,
    public.support_articles,
    public.incidents,
    public.workflow_runs,
    public.workflow_events,
    public.resolution_actions,
    public.approval_requests,
    public.escalations,
    public.customer_memory,
    public.audit_logs
FROM PUBLIC, anon, authenticated;

GRANT SELECT ON TABLE
    public.profiles,
    public.customers,
    public.subscriptions,
    public.workspaces,
    public.products,
    public.tickets,
    public.ticket_messages,
    public.support_articles,
    public.incidents,
    public.workflow_runs,
    public.workflow_events,
    public.resolution_actions,
    public.approval_requests,
    public.escalations,
    public.customer_memory,
    public.audit_logs
TO authenticated;

GRANT ALL ON TABLE
    public.profiles,
    public.customers,
    public.subscriptions,
    public.workspaces,
    public.products,
    public.tickets,
    public.ticket_messages,
    public.support_articles,
    public.incidents,
    public.workflow_runs,
    public.workflow_events,
    public.resolution_actions,
    public.approval_requests,
    public.escalations,
    public.customer_memory,
    public.audit_logs
TO service_role;
