import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WorkflowSteps } from "@/components/tickets/workflow-steps";

describe("WorkflowSteps", () => {
  it("shows completed, active, and conditionally skipped steps", () => {
    const { rerender } = render(
      <WorkflowSteps
        completedNodes={["understand_ticket", "classify_severity"]}
        currentNode="customer_context"
        workflowStatus="running"
      />,
    );

    expect(screen.getByText("Understand ticket").closest("li")).toHaveClass("workflow-step-completed");
    expect(screen.getByText("Load customer context").closest("li")).toHaveAttribute("aria-current", "step");
    expect(screen.getByText("Human approval").closest("li")).toHaveClass("workflow-step-pending");

    rerender(
      <WorkflowSteps
        completedNodes={["understand_ticket", "execute_resolution"]}
        currentNode="memory_update"
        workflowStatus="completed"
      />,
    );
    expect(screen.getByText("Human approval").closest("li")).toHaveClass("workflow-step-skipped");
  });
});
