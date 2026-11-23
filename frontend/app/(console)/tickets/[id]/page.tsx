"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { TicketActions } from "@/components/tickets/ticket-actions";
import { WorkflowPanel } from "@/components/tickets/workflow-panel";
import { Notice } from "@/components/ui/notice";
import { StatusPill } from "@/components/ui/status-pill";
import {
  ApiError,
  approveTicketAction,
  escalateTicket,
  getTicket,
  getTicketWorkflow,
  rejectTicketAction,
  requestTicketInformation,
  sendTicketReply,
  startTicketWorkflow,
} from "@/lib/api";
import { formatDate } from "@/lib/format";
import { useAuth } from "@/lib/auth";
import { useApiData } from "@/lib/use-api-data";
import type { WorkflowStatus } from "@/lib/types";

const POLL_INTERVAL_MS = 2000;
const POLLING_STATUSES = new Set(["queued", "running"]);

function errorMessage(error: unknown): string {
  if (error instanceof ApiError && error.requestId) {
    return `${error.message} (Request ID: ${error.requestId})`;
  }
  return error instanceof Error ? error.message : "The action failed unexpectedly.";
}

export default function TicketDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const loadTicket = useCallback(() => getTicket(id), [id]);
  const { data: ticket, error, loading, retry } = useApiData(loadTicket);
  const [workflow, setWorkflow] = useState<WorkflowStatus>();
  const [workflowLoading, setWorkflowLoading] = useState(false);
  const [workflowError, setWorkflowError] = useState<string>();
  const [startedWorkflow, setStartedWorkflow] = useState<{ ticketId: string; workflowId: string }>();
  const [workflowRetry, setWorkflowRetry] = useState(0);
  const [actionBusy, setActionBusy] = useState(false);
  const [feedback, setFeedback] = useState<{ success: boolean; message: string }>();
  const canAct = user?.role === "agent" || user?.role === "admin";
  const activeWorkflowId = ticket?.workflow?.id
    ?? (startedWorkflow?.ticketId === id ? startedWorkflow.workflowId : undefined);
  const approvalId = ticket?.approval?.id;
  const approvalStatus = ticket?.approval?.status;
  const currentWorkflowStatus = workflow?.status ?? ticket?.workflow?.status;
  const workflowActive = Boolean(
    activeWorkflowId
    && currentWorkflowStatus
    && ["queued", "running", "paused"].includes(currentWorkflowStatus),
  );

  useEffect(() => {
    if (!activeWorkflowId) {
      setWorkflow(undefined);
      setWorkflowLoading(false);
      setWorkflowError(undefined);
      return;
    }

    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      setWorkflowLoading(true);
      try {
        const result = await getTicketWorkflow(id);
        if (!active) return;
        setWorkflow(result);
        setWorkflowError(undefined);
        setWorkflowLoading(false);
        if (POLLING_STATUSES.has(result.status)) {
          timer = setTimeout(poll, POLL_INTERVAL_MS);
        }
      } catch (reason: unknown) {
        if (!active) return;
        setWorkflowError(errorMessage(reason));
        setWorkflowLoading(false);
      }
    };

    void poll();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [activeWorkflowId, approvalId, approvalStatus, id, workflowRetry]);

  const runAction = async (
    action: () => Promise<unknown>,
    successMessage: string,
  ): Promise<boolean> => {
    setActionBusy(true);
    setFeedback(undefined);
    try {
      await action();
      setFeedback({ success: true, message: successMessage });
      retry();
      setWorkflowRetry((value) => value + 1);
      return true;
    } catch (reason: unknown) {
      setFeedback({ success: false, message: errorMessage(reason) });
      return false;
    } finally {
      setActionBusy(false);
    }
  };

  const startWorkflow = async () => runAction(async () => {
    const started = await startTicketWorkflow(id);
    setStartedWorkflow({ ticketId: id, workflowId: started.workflow_id });
    return started;
  }, "Workflow started. Progress will refresh automatically.");

  const handleApprove = (reason: string) => {
    if (!approvalId) return Promise.resolve(false);
    return runAction(() => approveTicketAction(approvalId, reason), "Approval recorded.");
  };

  const handleReject = (reason: string) => {
    if (!approvalId) return Promise.resolve(false);
    return runAction(() => rejectTicketAction(approvalId, reason), "Rejection recorded and sent to the safe escalation path.");
  };

  const handleReply = (body: string) =>
    runAction(() => sendTicketReply(id, body), "Reply recorded in the demo ticket.");

  const handleRequestInformation = (body: string) =>
    runAction(() => requestTicketInformation(id, body), "Information request recorded for the customer.");

  const handleEscalate = (team: string, reason: string) =>
    runAction(() => escalateTicket(id, { team, reason }), `Ticket escalated to ${team}.`);

  if (loading && !ticket) return <div className="loading-state">Loading ticket…</div>;
  if (!ticket && error) return <Notice error={error} onRetry={retry} />;
  if (!ticket) return <div className="empty-state">Ticket not found.</div>;

  return (
    <>
      <div className="ticket-back-link"><Link href="/tickets">← Back to tickets</Link></div>
      {error && <Notice error={error} onRetry={retry} />}
      <header className="ticket-heading">
        <div>
          <div className="eyebrow">{ticket.ticket_number} · {ticket.channel}</div>
          <h1>{ticket.subject}</h1>
          <p className="page-description">
            Created {formatDate(ticket.created_at)} · Updated {formatDate(ticket.updated_at)}
          </p>
        </div>
        <div className="ticket-heading-pills">
          <StatusPill value={ticket.status} />
          <StatusPill value={ticket.category} />
          <StatusPill value={ticket.severity} />
        </div>
      </header>

      <div className="ticket-layout">
        <section className="panel ticket-messages" aria-label="Ticket conversation">
          <div className="section-heading">
            <div>
              <h2>Conversation</h2>
              <p className="helper-text">{ticket.messages.length} messages</p>
            </div>
          </div>
          {ticket.messages.length === 0 ? (
            <p className="muted">No messages have been recorded.</p>
          ) : (
            <ol className="message-list">
              {ticket.messages.map((message) => (
                <li className={message.is_internal ? "message message-internal" : "message"} key={message.id}>
                  <div className="message-meta">
                    <strong>{message.sender_name ?? message.sender_type}</strong>
                    <span>{formatDate(message.created_at)}</span>
                    {message.is_internal && <span className="pill">Internal note</span>}
                  </div>
                  <p>{message.body}</p>
                </li>
              ))}
            </ol>
          )}
        </section>

        <aside className="panel customer-card" aria-label="Customer information">
          <h2>Customer</h2>
          <div className="customer-name">{ticket.customer.name}</div>
          <a className="customer-email" href={`mailto:${ticket.customer.email}`}>{ticket.customer.email}</a>
          {ticket.customer.company_name && <p>{ticket.customer.company_name}</p>}
          <dl className="ticket-facts">
            <div><dt>Channel</dt><dd>{ticket.channel}</dd></div>
            <div><dt>Ticket status</dt><dd><StatusPill value={ticket.status} /></dd></div>
            <div><dt>Severity reason</dt><dd>{ticket.severity_reason ?? "Not assessed yet"}</dd></div>
            {ticket.summary && <div><dt>Summary</dt><dd>{ticket.summary}</dd></div>}
          </dl>
        </aside>

        <div className="ticket-workflow-column">
          <div className="workflow-run-control">
            <div>
              <h2>Support workflow</h2>
              <p className="helper-text">Investigate, propose, and track a safe resolution.</p>
            </div>
            <button
              className="button button-primary"
              disabled={!canAct || actionBusy || workflowActive || Boolean(activeWorkflowId && workflowLoading)}
              onClick={() => void startWorkflow()}
              type="button"
            >
              {currentWorkflowStatus === "paused"
                ? "Awaiting approval"
                : workflowActive || workflowLoading
                  ? "Running…"
                  : "Run workflow"}
            </button>
          </div>
          <WorkflowPanel
            workflow={workflow}
            loading={workflowLoading}
            error={workflowError}
            onRetry={() => setWorkflowRetry((value) => value + 1)}
          />
          <TicketActions
            approval={ticket.approval}
            canAct={canAct}
            busy={actionBusy}
            onApprove={handleApprove}
            onReject={handleReject}
            onReply={handleReply}
            onRequestInformation={handleRequestInformation}
            onEscalate={handleEscalate}
          />
          {feedback && (
            <p className={`action-feedback ${feedback.success ? "action-feedback-success" : "action-feedback-error"}`} role={feedback.success ? "status" : "alert"}>
              {feedback.message}
            </p>
          )}
        </div>
      </div>
    </>
  );
}
