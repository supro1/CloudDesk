"use client";

import { useState, type FormEvent } from "react";
import type { TicketApprovalSummary } from "@/lib/types";

type TicketActionsProps = {
  approval?: TicketApprovalSummary | null;
  canAct: boolean;
  busy: boolean;
  onApprove: (reason: string) => Promise<boolean>;
  onReject: (reason: string) => Promise<boolean>;
  onReply: (body: string) => Promise<boolean>;
  onRequestInformation: (body: string) => Promise<boolean>;
  onEscalate: (team: string, reason: string) => Promise<boolean>;
};

export function TicketActions({
  approval,
  canAct,
  busy,
  onApprove,
  onReject,
  onReply,
  onRequestInformation,
  onEscalate,
}: TicketActionsProps) {
  const [approvalReason, setApprovalReason] = useState("");
  const [reply, setReply] = useState("");
  const [team, setTeam] = useState("");
  const [escalationReason, setEscalationReason] = useState("");

  const submitReply = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const sent = await onReply(reply);
    if (sent) setReply("");
  };

  const submitInformationRequest = async () => {
    const sent = await onRequestInformation(reply);
    if (sent) setReply("");
  };

  const submitEscalation = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const escalated = await onEscalate(team, escalationReason);
    if (escalated) {
      setTeam("");
      setEscalationReason("");
    }
  };

  return (
    <section className="panel ticket-actions" aria-label="Ticket actions">
      <h2>Agent actions</h2>
      {approval?.status === "pending" && (
        <div className="action-group">
          <h3>Approval needed</h3>
          <p>{approval.summary}</p>
          <label className="field-label" htmlFor="approval-reason">Decision note (optional)</label>
          <textarea
            className="text-input action-textarea"
            disabled={!canAct || busy}
            id="approval-reason"
            onChange={(event) => setApprovalReason(event.target.value)}
            value={approvalReason}
          />
          <div className="action-buttons">
            <button
              className="button button-primary"
              disabled={!canAct || busy}
              onClick={() => void onApprove(approvalReason)}
              type="button"
            >
              Approve
            </button>
            <button
              className="button"
              disabled={!canAct || busy}
              onClick={() => void onReject(approvalReason)}
              type="button"
            >
              Reject
            </button>
          </div>
        </div>
      )}
      <form className="action-group" onSubmit={(event) => void submitReply(event)}>
        <h3>Reply to customer</h3>
        <label className="field-label" htmlFor="customer-reply">Message</label>
        <textarea
          className="text-input action-textarea"
          disabled={!canAct || busy}
          id="customer-reply"
          maxLength={4000}
          onChange={(event) => setReply(event.target.value)}
          required
          value={reply}
        />
        <div className="action-buttons">
          <button className="button button-primary" disabled={!canAct || busy || !reply.trim()} type="submit">
            Send reply
          </button>
          <button
            className="button"
            disabled={!canAct || busy || !reply.trim()}
            onClick={() => void submitInformationRequest()}
            type="button"
          >
            Request information
          </button>
        </div>
      </form>
      <form className="action-group" onSubmit={(event) => void submitEscalation(event)}>
        <h3>Escalate ticket</h3>
        <label className="field-label" htmlFor="escalation-team">Assigned team</label>
        <input
          className="text-input"
          disabled={!canAct || busy}
          id="escalation-team"
          maxLength={120}
          onChange={(event) => setTeam(event.target.value)}
          required
          value={team}
        />
        <label className="field-label" htmlFor="escalation-reason">Reason</label>
        <textarea
          className="text-input action-textarea"
          disabled={!canAct || busy}
          id="escalation-reason"
          maxLength={1000}
          onChange={(event) => setEscalationReason(event.target.value)}
          required
          value={escalationReason}
        />
        <button
          className="button"
          disabled={!canAct || busy || !team.trim() || !escalationReason.trim()}
          type="submit"
        >
          Escalate
        </button>
      </form>
      {!canAct && <p className="helper-text">Viewer access is read-only. Ask an agent to make changes.</p>}
      {busy && <p className="helper-text" role="status">Saving your action…</p>}
    </section>
  );
}
