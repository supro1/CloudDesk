# Phase 11 - Project System Design Evolution

## Scope and phase numbering

This document follows Phase 11 in `TASKS.md`: Approval and escalation.
`PLAN_PHASE.md` maps this to its Phase 10 approval-and-escalation stage.
Phase 11 reuses the workflow graph, approval/escalation tables, policy rules,
and registered tools that already exist. It adds pause/resume behavior,
conditional routing, and execution of approved plans.

## Starting point: decisions existed, but did not change the route

At the start of this phase, the application could produce a resolution plan
and assess risk. The database already had approval and escalation records,
and `ToolRegistry` already knew which tools needed approval. However, the
graph was still one straight line: it did not stop for approval, write an
escalation, or execute the planned actions.

```mermaid
flowchart LR
    Ticket["Ticket"] --> Graph["Analysis and risk graph"]
    Graph --> Plan["Resolution plan"]
    Plan --> End["Summary and memory"]
    ExistingPolicy["Tool approval policy"] -. not connected to graph routing .-> Plan
    ExistingTables["Approval and escalation tables"] -. not written by workflow .-> Graph
    ExistingTools["Registered write tools"] -. plan not executed .-> Plan
```

## P11-1: interrupt and store the pending approval

The risk node asks the same policy used by `ToolRegistry` whether each
planned action needs approval. If any action does, the graph routes to
`human_approval`. That node uses LangGraph's interrupt mechanism, yielding
the action and a short explanation instead of proceeding.

The workflow service reads the interrupt, stores an `ApprovalRequest`, marks
the run `paused`, and marks the ticket `waiting_on_approval`. The LangGraph
checkpointer holds the node position under the run's thread ID. Interrupt
resume data is intentionally small: it carries the decision and optional
reason, not tool arguments.

```mermaid
flowchart TB
    Risk["risk_check"] --> Gate{"Any action needs approval?"}
    Gate -->|No| Execute["execute_resolution"]
    Gate -->|Yes| Interrupt["human_approval calls interrupt"]
    Interrupt --> Pause["WorkflowService detects interrupt"]
    Pause --> RunDB["workflow_runs.status = paused"]
    Pause --> TicketDB["tickets.status = waiting_on_approval"]
    Pause --> ApprovalDB["approval_requests.status = pending"]
    Interrupt --> Saver["LangGraph checkpoint by thread_id"]
    TicketDB --> Agent["Agent reviews request"]
    ApprovalDB --> Agent
```

The interrupt node does no business writes before calling `interrupt`.
LangGraph can rerun code before an interrupt when resumed, so the node's
pre-interrupt work is limited to building the review prompt.

## P11-2: make the decision durable and resume the graph

The approval endpoints require the `agent` role. The list route is paginated.
Approve/reject writes a decision, actor, timestamp, and optional reason before
resuming the graph with a `Command(resume=...)`. The repository uses a
conditional update from `pending`, which prevents two concurrent requests
from deciding the same approval.

```mermaid
sequenceDiagram
    participant Agent as Support agent
    participant API as FastAPI approvals route
    participant Service as WorkflowService
    participant SQL as SQL approval/run/ticket rows
    participant Graph as Paused LangGraph
    participant Checkpoint as Checkpointer
    Agent->>API: POST /approvals/{id}/approve or /reject
    API->>Service: decide_approval(actor, decision, reason)
    Service->>SQL: Conditional pending -> approved/rejected
    Service->>SQL: Set ticket in progress
    Service->>Graph: astream(Command(resume=decision))
    Graph->>Checkpoint: Restore thread and continue node
    Graph-->>Service: Next interrupt or completed result
    Service->>SQL: Save next pause or final run status
    API-->>Agent: Updated approval and workflow status
```

If a graph contains more than one approval-required action, it asks about one
action at a time. The current approval is decided before the next pending
approval is created. Already decided requests and workflows that are no
longer paused return `409 Conflict`.

## P11-3: add policy-first escalation routing

The risk decision branches to escalation before approval or action execution
when a mandatory policy rule matches. Examples include suspected security
incidents, data loss, payment disputes, legal matters, and account deletion.
The existing rules supply the named team; model judgment cannot cancel a
matched policy.

A rejected approval also produces an escalation decision. A refund request
routes to Billing; a workspace reset routes to Workspace Admin. The
escalation node records the case through the registered `create_escalation`
tool and updates the ticket status through `update_ticket`.

```mermaid
flowchart LR
    Risk["risk_check"] --> Policy{"Mandatory policy match?"}
    Policy -->|Security| Security["team = security"]
    Policy -->|Data loss| Recovery["team = data_recovery"]
    Policy -->|Dispute| Billing["team = billing"]
    Policy -->|Deletion| Privacy["team = privacy_compliance"]
    Policy -->|No match| Approval{"Approval action?"}
    Approval -->|Rejected by reviewer| Billing
    Security --> EscNode["escalation node"]
    Recovery --> EscNode
    Billing --> EscNode
    Privacy --> EscNode
    EscNode --> Registry["ToolRegistry.create_escalation"]
    EscNode --> Update["ToolRegistry.update_ticket: escalated"]
    Registry --> EscRow["escalations table"]
```

The new read endpoints expose a paginated list with optional `status`,
`team`, and `ticket_id` filters and a detail view. They require an
authenticated viewer or higher.

## P11-4: execute plans through the shared tool path

After risk checks and any required approvals, `execute_resolution` walks the
deterministically planned actions. It calls `ToolRegistry.execute` for every
action; it does not call tool functions directly. The registry performs its
policy check again at execution time. Approved action indices are passed as
approval context only after the graph has resumed from a recorded decision.

Each action receives a durable `ResolutionAction` record with its status and
result. A failed or still-blocked tool is recorded as such; it is not shown
as a success. The graph then continues to ticket summary and memory nodes.

```mermaid
flowchart TB
    Plan["ResolutionPlan: allow-listed actions"] --> Gate["Risk check and human approval"]
    Gate --> Executor["execute_resolution"]
    Executor --> Registry["ToolRegistry.execute(name, args, approved)"]
    Registry --> Policy{"ToolPolicy rechecks"}
    Policy -->|Allowed| Tool["Registered async tool"]
    Policy -->|Approval still missing| Blocked["Blocked result"]
    Tool --> Mocks["Mock billing/workspace integrations"]
    Tool --> Repos["Repository-backed ticket changes"]
    Tool --> Result["ToolResult success or failure"]
    Blocked --> ActionRow["resolution_actions status/result"]
    Result --> ActionRow
    ActionRow --> Summary["ticket_summary"]
    Summary --> Memory["memory_update"]
```

The fixture's claimed refund amount is only a request value. Its mock billing
adapter records a simulated request and explicitly moves no funds.

## P11-5: exercise the safety paths with demo tickets

`scripts/demo.py` uses the in-process FastAPI test client and the same routes
as the application. It runs one selected demo ticket. CD-1002 pauses and
prompts for approve/reject; CD-1005 routes directly to the Security team.
The `make demo` target defaults to CD-1002 and accepts `TICKET=CD-1005`.

```mermaid
flowchart LR
    Make["make demo TICKET=..."] --> Script["scripts.demo"]
    Script --> Login["Demo agent login"]
    Login --> Run["POST ticket workflow"]
    Run --> Select{"Ticket"}
    Select -->|CD-1002| Pause["Pending refund approval"]
    Pause --> Human["Interactive approve/reject"]
    Human --> Registry["Approved mock action or Billing escalation"]
    Select -->|CD-1005| Rule["Security policy match"]
    Rule --> Security["Escalation record: security"]
    Registry --> Print["Print workflow outcome"]
    Security --> Print
```

## End-of-Phase-11 design

```mermaid
flowchart LR
    Agent["Agent API client"] --> RunAPI["Workflow run API"]
    RunAPI --> Service["WorkflowService"]
    Service --> Graph["LangGraph analysis and decision flow"]
    Graph --> Risk{"Policy-first risk route"}
    Risk -->|Approval required| Pause["Interrupt and checkpoint"]
    Pause --> ApprovalSQL["approval_requests + paused workflow"]
    Agent -->|Approve/reject| ApprovalAPI["Approval API"]
    ApprovalAPI --> Resume["Record decision and resume checkpoint"]
    Resume --> Graph
    Risk -->|Mandatory escalation| Escalation["Named-team escalation"]
    Resume -->|Approved| Execute["Shared resolution executor"]
    Execute --> Registry["ToolRegistry and ToolPolicy"]
    Escalation --> Registry
    Registry --> Stores["SQL records and mock integrations"]
    Execute --> Finish["Ticket summary and safe memory"]
    Escalation --> Finish
    Finish --> Events["workflow_events"]
    Agent --> ReadAPI["Workflow, approvals, events, escalations APIs"]
    ReadAPI --> ApprovalSQL
    ReadAPI --> Events
```

## Design choices and trade-offs

| Concern | Phase 11 starting point | Phase 11 end state |
|---|---|---|
| Consequential action | A plan and a tool policy existed, but graph execution did not pause. | Conditional graph route pauses and creates a durable approval request. |
| Decision handling | No approve/reject service path. | Agent-only endpoints record actor, time, reason, and decision. |
| Resume | A checkpointer existed but no approval API used it. | `Command(resume=...)` continues the saved graph thread. |
| Escalation | Rules could identify cases but did not create an escalation row. | Rules route to named teams and update ticket status. |
| Tool writes | Tools were registered but plans were not executed by the graph. | All planned actions execute through `ToolRegistry` and `ToolPolicy`. |
| Auditability | Planned actions existed without action outcome records. | Approval, escalation, workflow event, and resolution-action records exist. |
| External effects | Integrations are mocks. | Approved refund is a simulated request; no money is moved. |
| Demo | Make target started the backend only. | Make target demonstrates approval or security escalation offline. |

## Boundaries and next steps

- The current workflow runner remains an in-process background task.
- No real email, refund, or workspace change is performed by mock integrations.
- Approval is per planned action and decisions are not exposed as direct tool
  execution endpoints.
- The action executor stores arguments in the internal action table; API
  workflow/event responses remain curated.
- Phase 12/13 can present these routes and states in the ticket console.
- No cloud deployment, distributed worker, or live LLM integration is
  claimed by this phase.

## Related files

- [Phase 11 codebase explanation](../explain_codebase/phase11_explained.md)
- [Phase 11 infrastructure and wiring](../Infra_design_evolution/Phase11_Infra_design_evolution.md)
- [Phase 11 interview Q&A](../QnA/Phase11_Interview_QnA.md)
- [Workflow graph](../../agents/graph.py)
- [Approval and escalation nodes](../../agents/nodes/)
- [Workflow service](../../backend/app/services/workflow_service.py)
- [Approval and escalation APIs](../../backend/app/api/)
- [Tool registry and policy](../../backend/app/tools/)
- [API contract](../../docs/API_CONTRACT.md)
- [Tests](../../tests/api/test_tickets.py)
- [Task tracker](../../TASKS.md)
