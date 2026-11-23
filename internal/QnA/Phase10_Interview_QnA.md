# Phase 10 - Workflow Graph and Trace: Interview Questions and Answers

This Q&A follows Phase 10 in `TASKS.md`. `PLAN_PHASE.md` calls the same
product stage Phase 9. Approval interrupts and actual escalation/action
execution are Phase 11.

## Phase overview

### 1. What was the goal of Phase 10?

To connect the separate support specialists into an ordered workflow, save
its progress, expose run and polling APIs, and make safe operational events
inspectable.

### 2. How would you explain the phase to a non-technical interviewer?

I connected the support specialists into one organized case process. Each
specialist receives the work in order, saves their result to the shared
case record, and leaves a safe activity trail that a human support agent can
review.

### 3. What did Phase 10 add that Phase 9 did not have?

Phase 9 provided individual specialist classes and tests. Phase 10 added the
shared workflow state, LangGraph orchestration, checkpointing, run API,
workflow status API, event tracing, and end-to-end execution.

### 4. Is Phase 10 the same as the Phase 10 number in `PLAN_PHASE.md`?

No. The task tracker calls this phase Phase 10. The formal plan maps it to
Phase 9. This project intentionally pulled memory earlier, so task numbering
and formal plan numbering differ.

### 5. What is the overall order of the graph?

Understand the ticket, assess severity, load customer context, retrieve
knowledge, troubleshoot, plan a resolution, assess risk, save the ticket
summary, and update safe customer memory.

### 6. Does every node have one responsibility?

Yes. The supervisor classifies and assesses severity; investigation nodes
load context, retrieve evidence, and diagnose; later nodes plan the reply,
check risk, and write summary/memory data.

## State and checkpointing

### 7. What is `SupportState`?

It is the typed shared case record passed between graph nodes. It contains
ticket identifiers and the validated outputs produced by the specialists.

### 8. Why use reducers in workflow state?

Reducers combine updates from different graph nodes. Completed-node and
error lists append, while token totals are added together instead of
overwritten by the latest node.

### 9. What is a checkpoint?

A checkpoint is a saved snapshot of graph progress. It gives the workflow a
durable place to record its state and provides the foundation for future
pause/resume behavior.

### 10. Which checkpointer is used?

The configured SQLite file uses LangGraph's asynchronous SQLite saver.
When `CHECKPOINT_DB_PATH=:memory:`, the graph uses `InMemorySaver`, which is
convenient for isolated tests.

### 11. Why store run state in SQL and checkpoint state separately?

`workflow_runs` supports application status and API polling. The LangGraph
checkpointer stores graph-specific snapshots under the run's thread ID.
Each store serves a different purpose.

### 12. Does checkpointing automatically make the background worker durable?

No. The current task runs inside the API process. Checkpoints preserve graph
state, but a separate queue and worker would be needed for durable,
distributed scheduling.

## Nodes and specialist orchestration

### 13. How does the supervisor node treat customer text?

It passes text through the existing untrusted-content boundary. Deterministic
rules can override model classification and raise severity; ticket text
cannot directly become an instruction to call a tool.

### 14. What happens in the investigation portion?

The customer node gathers customer/subscription/history context through
registered read tools and safe memory. The knowledge node searches for cited
articles and similar cases. The troubleshooting node combines evidence,
mock service status, and safe playbook steps.

### 15. Does a specialist write SQL directly?

No. Tool-based lookups use `ToolRegistry` and repositories. Ticket summary
and memory updates are handled by graph nodes through repository/facade
interfaces, not embedded in specialist agent code.

### 16. How does the resolution node prevent a model from inventing tools?

The model returns a structured text draft. A separate deterministic
`plan_actions` function derives the allowed action list from explicit
application inputs. The workflow does not execute those actions in this
phase.

### 17. What does the risk check do?

It calls the policy-first escalation specialist and marks a workflow high
risk when an approval-required action exists, a policy escalation is
required, severity is critical, ticket text is flagged as injection, or
customer output validation failed.

### 18. Does a high-risk result stop the graph in Phase 10?

Not yet. Phase 10 records the risk result and continues to summary and
memory. Phase 11 adds conditional routing to approval or escalation paths.

### 19. Why does the graph write ticket summary and memory?

The summary helps agents scan the ticket, and scrubbed memory notes can
reduce repeated investigation for the same customer. The memory facade
filters secrets, raw ticket bodies, and duplicate notes.

### 20. Does the workflow send the drafted reply to the customer?

No. It returns a validated reply preview. The later workflow/action phase
will provide controlled execution, and sending real messages remains outside
the v1 mock-integration scope.

## Run and polling APIs

### 21. How does an agent start a run?

An agent calls `POST /api/v1/tickets/{ticket_id}/run`. The backend verifies
that the ticket exists and is not waiting for approval or already running,
creates a queued run, schedules background execution, and returns `202`
with a workflow ID.

### 22. Why return HTTP 202 instead of waiting for the entire graph?

The analysis can involve several model and tool calls. `202 Accepted` lets
the client know the run was accepted and lets it poll separately without
keeping the start request open.

### 23. How does the UI learn whether work is done?

It polls `GET /api/v1/tickets/{ticket_id}/workflow`. The response includes
status, current and completed node names, safe result summaries, and token
totals.

### 24. How does an agent inspect the detailed event trail?

It calls `GET /api/v1/tickets/{ticket_id}/events`. The endpoint returns the
latest run's events in chronological order.

### 25. Which roles can start versus inspect a workflow?

Agents and admins can start a workflow. Authenticated viewers can inspect
the status and events; role enforcement is server-side.

### 26. What happens if a ticket does not exist?

The run service returns a 404 for a missing ticket. Polling status/events
returns 404 if no workflow exists yet.

### 27. What happens if a run is already active?

The service rejects a duplicate start with 409. It also rejects starting
while the ticket is waiting on approval.

## Tracing and privacy

### 28. What events are traced?

Node start/completion, tool calls, structured model calls, workflow
completion, and sanitized errors. The model event includes schema name,
latency, usage, and cost availability; tool events include tool name,
outcome, timing, and a safe allow-listed result summary.

### 29. How are token totals accumulated?

`call_structured` reports input and output token counts to the current node's
observation. The node returns those metrics, and the `SupportState` reducer
sums them across nodes.

### 30. How is cost represented?

The fake provider reports an estimated cost of zero. For providers where
this code has no estimate, events say the cost is unavailable rather than
claiming a known price.

### 31. What information is intentionally omitted from events?

Raw prompts, private reasoning, ticket message bodies, tool arguments, raw
tool results, secrets, and other customers' data are omitted. Safe summaries
may include counts, statuses, article references, or other explicitly
allow-listed operational fields.

### 32. Can telemetry failure prevent the ticket workflow from running?

No. Event persistence is best-effort and logged if it fails. A telemetry
failure must not turn a successful support node into a failed node.

### 33. Is the whole workflow state exposed by the status endpoint?

No. The API returns a curated summary. The full graph state can contain
customer-provided text and other internal fields, so it remains internal.

### 34. How are workflow failures represented?

The service marks the run as failed, records a sanitized error type, and
sets a generic error message on the run. It does not copy prompts or raw
exception content into the public event trail.

## Testing and trade-offs

### 35. How is the workflow tested without external services?

Tests use the fake structured-output provider, temporary SQLite, an
in-memory checkpoint where appropriate, and existing mock integrations.

### 36. What does the checkpoint test prove?

It proves that a graph state saved to the SQLite checkpointer can be read
back after closing and reopening the checkpointer. It does not prove
high-availability or distributed-worker behavior.

### 37. What does the end-to-end API test prove?

It starts a ticket workflow through the authenticated route, observes the
completed node list, verifies that the status and event routes work, and
checks that LLM/tool events do not expose prompts or arguments.

### 38. Why keep tracing at the structured LLM and tool-registry boundaries?

Those are the shared points through which model calls and tools execute.
Instrumenting them once means every graph node gets consistent usage and
tool metadata without logging each node's raw inputs.

### 39. What is the biggest current operational limitation?

Background tasks run in the API process. A production system may move them
to a durable worker queue, but that infrastructure is not part of this
phase.

### 40. What remains for Phase 11?

The human approval interrupt, approval decision/resume API, named-team
escalation records, and safe execution through the shared registry path.

### 41. What are the main trade-offs?

The linear graph is easy to understand and test but does not yet branch for
approval or escalation. SQLite checkpoints are useful locally but are not
a shared production checkpoint service. Cost estimates are only available
when the selected provider supplies or supports one.

### 42. How would you summarize the largest design decision?

“I used typed graph state and clear node boundaries, and instrumented the
existing model/tool call boundaries so progress is inspectable without
persisting sensitive inputs.”

### 43. How would you summarize Phase 10 in one sentence?

“Phase 10 turns independent support specialists into a checkpointed,
observable workflow with authenticated start and polling APIs.”

## Repository references

- [Phase 10 codebase explanation](../explain_codebase/phase10_explained.md)
- [Phase 10 system design evolution](../design_evolution/Phase10_Project_System_Design_Evolution.md)
- [Phase 10 infrastructure and wiring](../Infra_design_evolution/Phase10_Infra_design_evolution.md)
- [Workflow state and graph](../../agents/state.py)
- [Checkpointer](../../agents/checkpointer.py)
- [Workflow service and tracer](../../backend/app/services/)
- [Workflow API](../../backend/app/api/workflow.py)
- [Workflow tests](../../tests/workflow/)
- [API contract](../../docs/API_CONTRACT.md)
- [Task tracker](../../TASKS.md)
