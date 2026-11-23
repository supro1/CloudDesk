import {
  getWorkflowStepStatus,
  WORKFLOW_STEPS,
} from "@/lib/workflow-steps";

type WorkflowStepsProps = {
  completedNodes: readonly string[];
  currentNode: string | null;
  workflowStatus: string;
};

export function WorkflowSteps({
  completedNodes,
  currentNode,
  workflowStatus,
}: WorkflowStepsProps) {
  return (
    <ol className="workflow-steps" aria-label="Ticket workflow steps">
      {WORKFLOW_STEPS.map((step, index) => {
        const status = getWorkflowStepStatus(
          step.id,
          completedNodes,
          currentNode,
          workflowStatus,
        );
        return (
          <li
            className={`workflow-step workflow-step-${status}`}
            key={step.id}
            aria-current={status === "active" ? "step" : undefined}
          >
            <span className="workflow-step-number" aria-hidden="true">
              {status === "completed" ? "✓" : index + 1}
            </span>
            <span className="workflow-step-label">{step.label}</span>
            <span className="workflow-step-status">{status}</span>
          </li>
        );
      })}
    </ol>
  );
}
