import { StatusPill } from "@/components/ui/status-pill";
import { WorkflowSteps } from "@/components/tickets/workflow-steps";
import type { WorkflowStatus } from "@/lib/types";

type WorkflowPanelProps = {
  workflow?: WorkflowStatus;
  loading: boolean;
  error?: string;
  onRetry: () => void;
};

export function WorkflowPanel({ workflow, loading, error, onRetry }: WorkflowPanelProps) {
  if (!workflow && loading) {
    return <section className="panel workflow-panel" aria-label="Ticket workflow">Loading workflow…</section>;
  }
  if (!workflow && error) {
    return (
      <section className="panel workflow-panel" aria-label="Ticket workflow">
        <p role="alert">{error}</p>
        <button className="button" onClick={onRetry} type="button">Retry workflow</button>
      </section>
    );
  }
  if (!workflow) {
    return (
      <section className="panel workflow-panel" aria-label="Ticket workflow">
        <p className="muted">No workflow has been run for this ticket yet.</p>
      </section>
    );
  }

  return (
    <section className="panel workflow-panel" aria-label="Ticket workflow">
      <div className="section-heading">
        <div>
          <h2>Workflow progress</h2>
          <p className="helper-text">
            The steps show how the support system investigates and prepares a resolution.
          </p>
        </div>
        <StatusPill value={workflow.status} />
      </div>
      <WorkflowSteps
        completedNodes={workflow.completed_nodes}
        currentNode={workflow.current_node}
        workflowStatus={workflow.status}
      />
      {workflow.error && <p className="action-feedback action-feedback-error" role="alert">{workflow.error}</p>}
      {error && (
        <div className="workflow-refresh-error" role="alert">
          <span>{error}</span>
          <button className="button" onClick={onRetry} type="button">Retry</button>
        </div>
      )}
      {workflow.severity && (
        <div className="workflow-metadata">
          <span><strong>Category:</strong> {workflow.category?.replaceAll("_", " ") ?? "Unclassified"}</span>
          <span><strong>Severity:</strong> {workflow.severity}</span>
          {workflow.severity_reason && <p>{workflow.severity_reason}</p>}
          {workflow.summary && <p>{workflow.summary}</p>}
        </div>
      )}
      {workflow.diagnosis && (
        <div className="workflow-detail">
          <h3>Likely causes</h3>
          <ul>{workflow.diagnosis.probable_causes.map((cause) => <li key={cause}>{cause}</li>)}</ul>
          <h3>Suggested steps</h3>
          <ol>
            {workflow.diagnosis.steps.map((step) => (
              <li key={step.number}>{step.instruction}</li>
            ))}
          </ol>
        </div>
      )}
      {workflow.evidence.length > 0 && (
        <div className="workflow-detail">
          <h3>Knowledge used</h3>
          <ul className="evidence-list">
            {workflow.evidence.map((item) => (
              <li key={item.id}>
                <strong>{item.title}</strong>
                <span className="evidence-source">{item.source} · relevance {Math.round(item.score * 100)}%</span>
                <p>{item.snippet}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
      {workflow.resolution && (
        <div className="workflow-detail">
          <h3>Resolution plan</h3>
          <p>{workflow.resolution.summary}</p>
          {workflow.resolution.output_valid ? (
            <div className="reply-preview">
              <strong>Checked customer reply draft</strong>
              <p>{workflow.resolution.customer_reply}</p>
            </div>
          ) : (
            <p className="muted">The suggested reply was withheld because it did not pass safety checks.</p>
          )}
        </div>
      )}
    </section>
  );
}
