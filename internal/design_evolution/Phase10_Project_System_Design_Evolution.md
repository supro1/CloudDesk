# Phase 10 - Project System Design Evolution

## Scope and phase numbering

This document follows **Phase 10 in `TASKS.md`**: Workflow graph and trace.
`PLAN_PHASE.md` numbers this product stage Phase 9. Phase 10 connects the
Phase 9 specialist agents, adds run/status/events routes, persists workflow
progress, and records sanitized operational telemetry.

Approval interrupts, durable approval decisions, escalation writes, and
execution of planned actions remain Phase 11 work.

## Starting point: useful specialists, no coordinated run

At the start of this phase, each specialist could be invoked independently.
The API could create and read tickets, and the database already had workflow
run and event tables. But no graph coordinated the specialists, created a
run, checkpointed progress, or exposed trace events.

```mermaid
flowchart LR
    Agent["Support agent"] --> TicketAPI["Ticket CRUD API"]
    TicketAPI --> TicketDB["Tickets and messages"]
    Specialist["Independent specialist agents"] --> Tools["ToolRegistry"]
    Tools --> Repositories["Repositories and integrations"]
    Tools --> Knowledge["Knowledge search"]
    Missing["No connected graph, run API, checkpoint, or event writer"]
    Runs["WorkflowRun and WorkflowEvent database tables already exist"]
```

## P10-1: define the shared state and checkpoint lifecycle

`SupportState` is a typed shared record. The graph stores node outputs in
named fields. Reducers append completed-node/error entries and sum token
usage instead of replacing earlier results. The checkpointer uses
`InMemorySaver` for `:memory:` configurations and `AsyncSqliteSaver` for a
configured local SQLite file.

```mermaid
flowchart TB
    Initial["Ticket IDs, subject, customer message"] --> State["SupportState"]
    State --> NodeA["Node output"]
    NodeA --> Reducers["Append completed nodes / sum token usage"]
    Reducers --> State
    State --> Saver{"Configured checkpoint store"}
    Saver -->|:memory:| MemorySaver["InMemorySaver for tests"]
    Saver -->|file path| SqliteSaver["AsyncSqliteSaver"]
    SqliteSaver --> DbFile["Ignored local checkpoint database"]
```

The checkpoint contains graph state so execution can be continued by later
workflow features. The status route deliberately returns a curated summary,
not the entire checkpoint or customer message.

## P10-2 and P10-3: connect the supervisor and investigation specialists

The supervisor's understanding and severity work becomes the first pair of
nodes. Then customer context, cited knowledge retrieval, and troubleshooting
run in order. Each node returns only its part of the shared state.

```mermaid
flowchart LR
    Start["Ticket input"] --> Understand["understand_ticket"]
    Understand --> Severity["classify_severity"]
    Severity --> Customer["customer_context"]
    Customer --> Knowledge["knowledge_retrieval"]
    Knowledge --> Troubleshoot["troubleshooting"]
    Customer --> Registry["Existing ToolRegistry"]
    Knowledge --> Registry
    Troubleshoot --> Registry
    Registry --> Existing["Existing repositories, RAG, mock integrations"]
    Understand -. typed result .-> State["Shared SupportState"]
    Severity -. typed result .-> State
    Customer -. typed result .-> State
    Knowledge -. citations and prior cases .-> State
    Troubleshoot -. diagnosis .-> State
```

Tools are still invoked through `ToolRegistry`; specialists do not make SQL
queries. The same service dependencies used in the existing application are
injected into the graph at construction time.

## P10-4: add resolution, risk, summary, and memory nodes

The resolution node produces a grounded reply preview and deterministic
planned actions. The risk node applies the existing policy-first escalation
assessment and marks high-risk conditions. The last nodes save a concise
ticket summary and safe, de-duplicated customer-memory notes.

```mermaid
flowchart TB
    State["Classification, customer context, evidence, diagnosis"] --> Resolution["resolution_planning"]
    Resolution --> Plan["Grounded reply preview + deterministic action plan"]
    Plan --> Risk["risk_check"]
    Text["Ticket text + subscription plan"] --> Policy["Escalation rules first"]
    Policy --> Risk
    Risk --> Summary["ticket_summary writes ticket fields"]
    Summary --> Memory["memory_update uses scrubbed memory facade"]
    Plan -. no execution .-> Deferred["Phase 11: approval and execution"]
    Risk -. no escalation write .-> Deferred
```

This phase makes an escalation decision visible in state but does not record
an escalation. It can identify a risk, but it does not pause for approval or
execute a tool action.

## P10-5: expose a run and polling flow

`POST /api/v1/tickets/{ticket_id}/run` checks the ticket and for an existing
active run, creates a queued `WorkflowRun`, and returns `202 Accepted`. The
FastAPI background task starts the graph in-process. The service persists
the state after every graph update, then records completion or a sanitized
failure status.

```mermaid
sequenceDiagram
    participant A as Agent client
    participant API as FastAPI workflow route
    participant S as WorkflowService
    participant DB as SQL workflow_runs
    participant G as Compiled support graph
    participant CP as LangGraph checkpointer
    A->>API: POST /tickets/{id}/run
    API->>S: create_run(ticket_id)
    S->>DB: Save queued run and initial state
    API-->>A: 202 {workflow_id, status}
    API->>S: BackgroundTasks.start_workflow
    S->>DB: Set running
    loop After each graph state update
        S->>G: astream(state)
        G->>CP: Save checkpoint by thread_id
        S->>DB: Persist current state and token totals
    end
    S->>DB: Set completed or failed and finished_at
    A->>API: GET /tickets/{id}/workflow
    API->>DB: Read latest run
    API-->>A: Curated progress summary
```

The current worker runs inside the API process. A separate durable task
queue/worker is a production scaling option, not part of this phase.

## P10-6: trace safe events

The `WorkflowTracer` writes start/completion events for nodes and captures
tool and structured-model activity from the existing registry and
`call_structured` boundary. Each event stores only safe operational
metadata: event type, schema/tool name, timing, outcome, token counts, and
cost availability. Tool events may contain allow-listed result summaries;
they never store prompt text, arguments, or raw results.

```mermaid
flowchart LR
    Node["Graph node"] --> NodeTrace["node_started / node_completed"]
    Node --> Agent["Specialist"]
    Agent --> LLM["call_structured"]
    LLM --> LLMTelemetry["schema, tokens, latency, available cost"]
    Agent --> Registry["ToolRegistry.execute"]
    Registry -->     ToolTelemetry["tool name, outcome, safe result summary, latency"]
    NodeTrace --> Tracer["WorkflowTracer"]
    LLMTelemetry --> Tracer
    ToolTelemetry --> Tracer
    Tracer --> EventTable["workflow_events"]
    EventTable --> EventsAPI["GET /tickets/{id}/events"]
    Unsafe["Prompts, raw content, args, raw results, secrets"] -. excluded .-> EventTable
```

Telemetry writes are best-effort: a database event-write failure is logged
without changing whether the support node succeeds. Workflow errors
themselves remain visible through failed status and sanitized error events.

## End-of-Phase-10 design

```mermaid
flowchart LR
    Client["Agent client"] --> Run["Run API (agent role)"]
    Run --> Service["WorkflowService"]
    Service --> Graph["LangGraph"]
    Graph --> Supervisor["Understand + severity"]
    Supervisor --> Investigation["Customer + knowledge + diagnosis"]
    Investigation --> Resolution["Plan reply and actions"]
    Resolution --> Risk["Policy-first risk assessment"]
    Risk --> TicketSummary["Persist ticket summary"]
    TicketSummary --> Memory["Store safe customer notes"]
    Graph --> Checkpoint["SQLite / in-memory saver"]
    Service --> RunsDB["workflow_runs: status + evolving state"]
    Graph -. nodes/tools/LLM .-> Tracer["WorkflowTracer"]
    Tracer --> EventsDB["workflow_events: sanitized trace"]
    Client --> Poll["Status and events APIs (viewer role)"]
    Poll --> RunsDB
    Poll --> EventsDB
```

## Design choices and trade-offs

| Concern | Phase 10 starting point | Phase 10 end state |
|---|---|---|
| Specialist execution | Independent classes and tests. | Ordered graph nodes with typed shared state. |
| State handoff | No persistent run state. | Reducers preserve completed nodes and accumulate tokens. |
| Restart support | No graph checkpoint. | SQLite saver for persistent local checkpoints; memory saver for tests. |
| Run API | Ticket CRUD only. | Agent-only asynchronous `202` start plus viewer status polling. |
| Trace detail | Event tables existed without graph integration. | Node, tool, and LLM events recorded and queryable. |
| Privacy | Agent outputs existed individually. | API status and event responses are curated and omit prompts/arguments/raw bodies. |
| Actions | Resolution agent created plans. | Actions remain plans; no write execution or approval pause occurs. |

## Boundaries and next steps

- Phase 11 adds the human approval interrupt, decision API, named-team
  escalation writes, and shared execution path.
- The graph currently follows a sequential route so all analysis and memory
  updates complete. Phase 11 can add conditional routing at `risk_check`.
- The LangGraph SQLite checkpointer stores workflow checkpoints separately
  from SQL run/event records.
- SQLite persistence and fake-model behavior are tested locally. No cloud
  deployment or live provider execution is claimed.

## Related files

- [Phase 10 codebase explanation](../explain_codebase/phase10_explained.md)
- [Phase 10 infrastructure and wiring](../Infra_design_evolution/Phase10_Infra_design_evolution.md)
- [Phase 10 interview Q&A](../QnA/Phase10_Interview_QnA.md)
- [Workflow state and reducers](../../agents/state.py)
- [Graph construction](../../agents/graph.py)
- [Checkpointer lifecycle](../../agents/checkpointer.py)
- [Workflow service](../../backend/app/services/workflow_service.py)
- [Workflow tracer](../../backend/app/services/workflow_tracer.py)
- [Workflow API](../../backend/app/api/workflow.py)
- [API contract](../../docs/API_CONTRACT.md)
- [Workflow tests](../../tests/workflow/)
- [Task tracker](../../TASKS.md)
