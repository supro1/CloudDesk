import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TicketActions } from "@/components/tickets/ticket-actions";

const noAction = vi.fn(async () => true);

afterEach(cleanup);

describe("TicketActions", () => {
  it("keeps all mutations disabled for viewers", () => {
    render(
      <TicketActions
        approval={{
          id: "approval-1",
          ticket_id: "ticket-1",
          workflow_id: "workflow-1",
          action: "create_refund_request",
          summary: "Review a refund request.",
          status: "pending",
          requested_at: "2026-01-01T00:00:00Z",
          decided_at: null,
          decided_by: null,
        }}
        canAct={false}
        busy={false}
        onApprove={noAction}
        onReject={noAction}
        onReply={noAction}
        onRequestInformation={noAction}
        onEscalate={vi.fn(async () => true)}
      />,
    );

    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send reply" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Request information" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Escalate" })).toBeDisabled();
    expect(screen.getByText(/read-only/i)).toBeInTheDocument();
  });

  it("sends a reply through the supplied action and clears it after success", async () => {
    const onReply = vi.fn(async () => true);
    render(
      <TicketActions
        canAct
        busy={false}
        onApprove={noAction}
        onReject={noAction}
        onReply={onReply}
        onRequestInformation={noAction}
        onEscalate={vi.fn(async () => true)}
      />,
    );

    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "We can help." } });
    fireEvent.click(screen.getByRole("button", { name: "Send reply" }));

    await waitFor(() => expect(onReply).toHaveBeenCalledWith("We can help."));
    await waitFor(() => expect(screen.getByLabelText("Message")).toHaveValue(""));
  });
});
