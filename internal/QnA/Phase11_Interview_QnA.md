# Phase 11 - Approval and Escalation: Interview Questions and Answers

This Q&A follows Phase 11 in `TASKS.md`. `PLAN_PHASE.md` maps the same stage
to its Phase 10 approval-and-escalation phase.

## Goals and system behavior

### 1. What was the goal of Phase 11?

To pause a support workflow before consequential actions, let an authorized
human approve or reject the request, resume from the saved checkpoint, route
policy cases to named teams, and execute permitted actions through the shared
tool registry.

### 2. How would you explain the phase to a non-technical interviewer?

The system can investigate and recommend a solution, but it does not make
important account or billing changes on its own. It saves its place, asks a
support agent to decide, records that decision, and only continues along the
approved or safe escalation route.

### 3. What did Phase 10 provide that Phase 11 uses?

Phase 10 provided the LangGraph workflow, shared state, run service,
checkpointer, and safe workflow tracing. Phase 11 uses those pieces to add
branching, interruptions, approval decisions, and actions.

### 4. Which functional requirements does this phase address?

It primarily addresses F9 (human approval for consequential actions), F10
(named-team escalation), and the workflow part of F13 (observable approval
and action events). The workflow remains offline-capable for F14.

### 5. Is a refund actually issued?

No. The billing integration is a mock. An approved request is recorded as a
simulated refund request, and the mock explicitly reports that no money was
moved.

## Interrupt and checkpoint

### 6. What is a human approval interrupt?

It is a deliberate pause in the graph where the workflow yields a short
description of the action and waits for an external decision. The graph does
not continue to the action until it receives an approval decision.

### 7. Why is the checkpointer needed?

The checkpointer saves the graph's continuation state. After the agent
approves, LangGraph can continue from the paused node rather than repeating
all the earlier ticket investigation.

### 8. Where is the pause recorded?

The LangGraph checkpointer stores graph continuation state. SQL stores the
application records: the workflow status becomes `paused`, the ticket status
becomes `waiting_on_approval`, and `approval_requests` gets a pending row.

### 9. Why keep both a SQL run state and a graph checkpoint?

SQL supports business queries and API responses. The LangGraph checkpoint is
optimized for restoring execution. They have separate responsibilities.

### 10. Why must code before `interrupt()` be idempotent?

LangGraph can rerun the node's code before the interrupt when it resumes.
That code should only prepare the interrupt payload, not create refunds,
escalations, or other side effects. This implementation persists the pending
approval after the workflow service observes the pause.

### 11. What happens when there are multiple approval-required actions?

The graph interrupts for one action at a time. It records the decision, then
continues to the next action's interruption if necessary. Each approval row
describes one action.

### 12. What happens if a ticket run is attempted while approval is pending?

The ticket status and active workflow checks reject a second run with
`409 Conflict`. The pending run must be decided first.

## Approval API and security

### 13. Which roles can approve or reject?

An `agent` or `admin` can decide. A `viewer` can read ticket and workflow
information but receives `403 Forbidden` when trying to approve or reject.

### 14. How does the API decide which user made the decision?

It takes the authenticated JWT subject from the server-validated request,
not from a user ID supplied in the JSON body. That subject is stored as
`decided_by_id`.

### 15. What is stored for a decision?

The approval row stores its final status, decision timestamp, authenticated
actor, and optional reviewer note. The audit middleware also records the
state-changing HTTP request, and the workflow tracer records a sanitized
approval-resolved event.

### 16. How do you prevent duplicate decisions?

The repository conditionally changes the row only when its current status is
`pending`. If another request has already decided it, the update affects no
row and the API returns `409`.

### 17. Does the API accept an `approved` flag to execute a tool?

No. The approval route decides a persisted approval and resumes the
checkpointed workflow. Tools still run only through `ToolRegistry`, which
checks the policy at execution time.

### 18. What responses do missing or invalid approval transitions return?

An unknown approval returns `404`. An already decided request or a workflow
that is not paused returns `409`. A viewer receives `403`; malformed request
bodies receive normal FastAPI validation errors.

### 19. Why can a decision response still report `paused`?

If one action is approved but the same workflow has another approval-required
action, the graph pauses again for that next action. The response includes
the new workflow status so the client knows another decision is needed.

## Escalation routing and policy

### 20. How does the system choose an escalation team?

Deterministic rules in `agents/rules.py` match policy cases and name a team.
For example, suspected breaches go to Security, data loss to Data Recovery,
payment disputes to Billing, and deletion requests to Privacy/Compliance.

### 21. Can the language model override a mandatory escalation rule?

No. A matched rule wins. The model may provide judgment in uncertain cases,
but it cannot cancel a deterministic policy match.

### 22. What happens when a human rejects an action?

The declined action is not executed. The graph creates a safe escalation
decision; refund requests route to Billing and workspace resets to Workspace
Admin. It records the escalation and marks the ticket as escalated.

### 23. How are escalation records created?

The escalation graph node calls the existing `create_escalation` tool
through `ToolRegistry`, then updates the ticket through the registered
`update_ticket` tool. The escalation record includes the assigned team,
reason, ticket, and workflow run.

### 24. Are escalation records exposed to the support agent?

Yes. The authenticated read API lists escalations with pagination and
optional status, team, and ticket filters, and returns a detail record by ID.

### 25. Why route the security sample directly instead of asking for approval?

A suspected security incident requires prompt specialist review. The
deterministic policy route sends it to the Security team; it does not need
approval to create that safe escalation record.

## Shared tool execution

### 26. What is the shared tool path?

The graph calls `ToolRegistry.execute`. The registry checks that a tool is
registered, evaluates `ToolPolicy`, applies timeout/error handling, and then
invokes the asynchronous tool. That tool uses repositories or a mock
integration.

### 27. Why check approval both during routing and execution?

Routing decides whether to pause before any action runs. The registry
rechecks policy at the point of execution as defense in depth. A planning
mistake cannot bypass the actual tool policy.

### 28. How does the executor know a human approved an action?

The interrupt node records the approved action index in graph state after
receiving the resume decision. The executor passes `approved=True` only for
those indices. No client-supplied tool flag is trusted.

### 29. How are action outcomes recorded?

The executor records a `resolution_actions` row with action type, arguments,
approval requirement, status, result or error, and completion time when
successful. Tool telemetry records a separate sanitized event.

### 30. What happens if a tool fails?

The registry returns a failure-shaped `ToolResult`. The executor records
`failed` or `blocked` status and appends an error to workflow state. It does
not represent the action as successful. The workflow status includes a
generic notice telling the agent to inspect its events.

### 31. Is the planned tool list generated by the language model?

No. The model drafts structured customer text. The deterministic
`plan_actions` function creates allow-listed actions from trusted application
inputs. Customer text can describe a request but cannot invent tool names.

### 32. How is the CD-1002 refund amount handled?

The fixture explicitly includes a claimed amount so the demo has a concrete
request to review. The parser accepts only one explicit currency amount in a
billing refund/credit request. The claim is not proof of entitlement, and
approval is still required. The mock records the request without moving
funds.

## Observability and privacy

### 33. What is logged when approval is requested?

The workflow records an `approval_requested` event with the approval ID,
action name, and a short summary. It does not put tool arguments or raw
customer message text into the event.

### 34. What is logged when a decision is made?

The SQL approval row stores the actor, timestamp, reason, and result. The
event trail records the action and approve/reject decision without copying
the optional note into the public event payload.

### 35. Are approval tool arguments returned by the workflow API?

No. Ticket workflow and event endpoints are curated. Tool arguments are
stored internally with the resolution action, but not exposed through the
workflow status or event response.

### 36. What if telemetry storage fails?

`WorkflowTracer` treats telemetry as best effort, logs a warning, and does
not intentionally interrupt the support graph. Business records and
workflow state remain separate from telemetry.

## Demo, tests, and operational limits

### 37. How do I run the CD-1002 example?

Run `make demo` after setting up the local environment. It uses the seeded
demo agent, starts the ticket workflow, displays the pending request, and
asks for an approve/reject decision.

### 38. How do I run the CD-1005 example?

Run `make demo TICKET=CD-1005`. The workflow applies the security policy,
creates a Security-team escalation, and prints the recorded destination.

### 39. Does the demo need an API key or Docker?

No external model API key or Docker service is needed when using the fake
provider and local configuration. The demo does require demo mode and a
configured JWT secret.

### 40. How is the approval flow tested offline?

The API tests use temporary SQLite, an in-memory checkpointer, a fake
language model, and mock integrations. They verify pause, persisted
approval, viewer rejection, approval/resume, mock action execution,
rejection-to-Billing escalation, and direct security routing.

### 41. What does the demo not prove?

It does not prove live model quality, live billing, email delivery, cloud
deployment, or worker resilience. The external services in this project are
mocks.

### 42. Is the workflow a durable distributed worker?

No. FastAPI's in-process background task runs the graph. Checkpoints help
resume a paused workflow, but a production-scale worker queue is a separate
infrastructure change.

### 43. What was the main design trade-off?

The phase favors a simple, inspectable in-process flow with database
approval records and the existing checkpoint store. It is easy to run
offline, but it is not yet a horizontally scaled job system.

### 44. What is one improvement for production?

Move graph execution to a durable worker queue, use a shared checkpoint
store, add operational recovery for a decision recorded just before a worker
failure, and replace the mock integrations with explicitly controlled
production adapters.

### 45. How would you summarize Phase 11 in one sentence?

“Phase 11 makes the support workflow safe to act: it pauses for human
approval, resumes from saved progress, routes policy cases to named teams,
and executes only through a shared policy-enforcing tool registry.”

## Repository references

- [Phase 11 codebase explanation](../explain_codebase/phase11_explained.md)
- [Phase 11 system design evolution](../design_evolution/Phase11_Project_System_Design_Evolution.md)
- [Phase 11 infrastructure and wiring](../Infra_design_evolution/Phase11_Infra_design_evolution.md)
- [Workflow graph and state](../../agents/graph.py)
- [Approval node](../../agents/nodes/approval.py)
- [Escalation node](../../agents/nodes/escalation.py)
- [Workflow service](../../backend/app/services/workflow_service.py)
- [Approval API](../../backend/app/api/approvals.py)
- [Escalation API](../../backend/app/api/escalations.py)
- [Tool policy and registry](../../backend/app/tools/)
- [Workflow/API tests](../../tests/api/test_tickets.py)
- [Demo script](../../scripts/demo.py)
- [Task tracker](../../TASKS.md)
