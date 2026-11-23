export const WORKFLOW_STEPS = [
  { id: "understand_ticket", label: "Understand ticket" },
  { id: "classify_severity", label: "Classify and assess severity" },
  { id: "customer_context", label: "Load customer context" },
  { id: "knowledge_retrieval", label: "Find knowledge" },
  { id: "troubleshooting", label: "Investigate the issue" },
  { id: "resolution_planning", label: "Plan a resolution" },
  { id: "risk_check", label: "Check risk and policy" },
  { id: "human_approval", label: "Human approval" },
  { id: "execute_resolution", label: "Carry out approved actions" },
  { id: "escalation", label: "Escalate when needed" },
  { id: "ticket_summary", label: "Summarize the ticket" },
  { id: "memory_update", label: "Remember the outcome" },
] as const;

export type WorkflowStepStatus = "completed" | "active" | "pending" | "skipped";

const CONDITIONAL_STEPS = new Set(["human_approval", "execute_resolution", "escalation"]);

export function getWorkflowStepStatus(
  stepId: string,
  completedNodes: readonly string[],
  currentNode: string | null,
  workflowStatus: string,
): WorkflowStepStatus {
  if (completedNodes.includes(stepId)) return "completed";
  if (currentNode === stepId) return "active";
  if (workflowStatus === "completed" && CONDITIONAL_STEPS.has(stepId)) return "skipped";
  return "pending";
}
