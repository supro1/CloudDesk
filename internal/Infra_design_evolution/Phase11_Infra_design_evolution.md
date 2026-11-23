# Phase 11 - Infrastructure and Wiring Design Evolution

## Scope: new application routes, not new containers

This document follows Phase 11 in `TASKS.md` (Approval and escalation).
The phase adds application-level routing inside the existing FastAPI process.
It does not add a Docker service, network, port, external queue, or cloud
resource. Container and Compose work remains a later phase.

The main operational change is a controlled pause in the workflow. The
checkpoint database holds LangGraph continuation state; the configured SQL
database holds the business records that agents and APIs need to read.

## Starting point: existing application wiring

Before Phase 11, the backend could start a workflow and stream progress. The
tool registry, SQL approval/escalation tables, and LangGraph checkpointer
already existed, but the workflow did not connect those pieces to an actual
pause/resume or escalation branch.

```mermaid
flowchart LR
    Client["Agent client"] --> API["FastAPI :8000"]
    API --> Service["WorkflowService"]
    Service --> Graph["Sequential LangGraph"]
    Graph --> Registry["Existing ToolRegistry"]
    Registry --> SQL["SQLite or PostgreSQL"]
    Registry --> Mocks["In-process mock integrations"]
    Service --> Checkpoint["SQLite file or in-memory test saver"]
    Existing["Approval and escalation SQL tables exist"]
    Missing["No approval route, workflow pause, or escalation tool call"]
```

There are no external inbound connections to the agents. All graph nodes,
tool functions, SQL repositories, and local mock integrations run in the
backend process.

## P11-1: connect the interrupt to checkpoint and SQL

The graph determines that an action requires approval and calls LangGraph's
interrupt function. The workflow service sees the interrupt in the streamed
state. It writes the pending request and ticket/run statuses to the configured
SQL database, while LangGraph saves its continuation snapshot under the
workflow's `thread_id`.

These stores are complementary:

- SQL records are the user-visible approval request and workflow status.
- The checkpointer preserves where the graph must continue.

```mermaid
flowchart TB
    Backend["FastAPI backend process"] --> Graph["LangGraph human_approval node"]
    Graph --> Interrupt["interrupt(action, short summary)"]
    Interrupt --> Service["WorkflowService detects interrupt"]
    Service --> SQL["Configured SQL database"]
    SQL --> Approval["approval_requests: pending"]
    SQL --> Ticket["tickets: waiting_on_approval"]
    SQL --> Run["workflow_runs: paused + safe state"]
    Graph --> Saver["LangGraph checkpointer"]
    Saver --> CheckpointFile["Async SQLite checkpoint file"]
    Test["Offline test setting"] --> MemorySaver["InMemorySaver instead"]
```

The checkpointer file is local state and is already covered by the repository's
ignore rules. The event tracer records `approval_requested` without storing
tool arguments or raw ticket text.

## P11-2: route the agent's decision back to the same process

The approval API is served by the existing FastAPI listener. Authentication
and role checks run before the service is called. The service records the
decision in SQL, then invokes the compiled graph with a resume command and
the existing checkpoint thread ID.

```mermaid
sequenceDiagram
    participant Browser as Agent browser or demo CLI
    participant API as Existing FastAPI :8000
    participant Auth as JWT / require_role(agent)
    participant Service as WorkflowService
    participant SQL as SQL database
    participant Graph as Paused graph
    participant Saver as Checkpointer
    Browser->>API: POST /approvals/{id}/approve or /reject
    API->>Auth: Verify JWT and agent role
    Auth-->>API: Authorized user ID
    API->>Service: Decide approval
    Service->>SQL: Conditional pending-to-decided update
    Service->>SQL: Update ticket state
    Service->>Graph: Command(resume=decision)
    Graph->>Saver: Restore by thread_id
    Saver-->>Graph: Paused node continuation
    Graph-->>Service: More pause, completion, or failure
    Service-->>API: New state
    API-->>Browser: Approval result and workflow status
```

The endpoint is not a new process or exposed port. The role check prevents a
viewer from deciding even if they can read an approval. A conditional SQL
update prevents duplicate decisions under concurrent requests.

## P11-3: route records through existing registered tools

Policy rules determine the destination team within the graph. The escalation
node uses the existing registry to create a database record and set the
ticket status. The new escalation read API returns paginated records through
the same FastAPI listener.

```mermaid
flowchart LR
    Ticket["Ticket and subscription context"] --> Risk["Policy-first risk node"]
    Risk --> Branch{"Route"}
    Branch -->|security| Security["security team"]
    Branch -->|lost data| Recovery["data_recovery team"]
    Branch -->|payment dispute| Billing["billing team"]
    Branch -->|deletion| Privacy["privacy_compliance team"]
    Branch -->|reviewer rejects| SafeTeam["Action-specific safe team"]
    Security --> EscalationNode["escalation node"]
    Recovery --> EscalationNode
    Billing --> EscalationNode
    Privacy --> EscalationNode
    SafeTeam --> EscalationNode
    EscalationNode --> Registry["ToolRegistry"]
    Registry --> EscalationTool["create_escalation"]
    Registry --> TicketTool["update_ticket(status=escalated)"]
    EscalationTool --> SQL["escalations table"]
    TicketTool --> SQL
    SQL --> ReadAPI["GET /api/v1/escalations"]
```

The team names are stored as application data. No mail server, chat system,
or external incident platform is contacted.

## P11-4: reuse the tool execution boundary

The executor does not create direct database or integration connections of
its own. It calls the already-configured `ToolRegistry`, which checks policy
and invokes an allow-listed tool. That tool uses the existing repository or
mock adapter. A separate SQL action record captures each result.

```mermaid
flowchart TB
    Graph["execute_resolution node"] --> Registry["ToolRegistry.execute"]
    Registry --> Policy["ToolPolicy approval check"]
    Policy -->|Approved or safe| Function["Registered async tool"]
    Policy -->|Approval absent| Blocked["ToolResult: blocked"]
    Function --> Repo["Existing SQL repositories"]
    Function --> Mock["Mock billing or workspace adapter"]
    Function --> Result["ToolResult success/failure"]
    Blocked --> Record["resolution_actions row"]
    Result --> Record
    Record --> WorkflowSQL["Configured SQL database"]
    Graph --> Tracer["WorkflowTracer"]
    Registry --> Tracer
    Tracer --> EventSQL["workflow_events row"]
```

The business action and the action audit row use separate service/repository
transactions. A durable approval record exists before an approval-required
tool is called. The current mock integrations do not perform irreversible
external operations.

## P11-5: local demo routing

`make demo` starts the app in the same process through FastAPI's test client,
uses demo authentication, and calls the same HTTP routes as a browser. It
needs a local demo secret and database configuration but does not need
Docker, Redis, a remote vector store, or an API key when the fake LLM is used.

```mermaid
flowchart LR
    Shell["make demo TICKET=CD-1002"] --> Python["scripts.demo"]
    Python --> Client["FastAPI TestClient in process"]
    Client --> Auth["/auth/login"]
    Client --> Run["/tickets/{id}/run"]
    Run --> Workflow["WorkflowService"]
    Workflow --> DB["Configured local SQL"]
    Workflow --> Saver["Configured checkpointer"]
    Workflow --> Mock["Mock billing or escalation tools"]
    Python --> Prompt["Terminal decision prompt for CD-1002"]
    Shell2["make demo TICKET=CD-1005"] --> Python
```

The script does not open a second HTTP listener. It exercises application
routes without requiring an already-running server.

## End-of-Phase-11 component wiring

```mermaid
flowchart TB
    Agent["Agent browser or local demo script"] -->|"Existing FastAPI listener"| API["FastAPI :8000"]
    API --> Auth["JWT authentication and RBAC"]
    Auth --> WorkflowAPI["Workflow run/status/events APIs"]
    Auth --> ApprovalAPI["Approval list/approve/reject APIs"]
    Auth --> EscalationAPI["Escalation list/detail APIs"]
    WorkflowAPI --> Service["WorkflowService"]
    ApprovalAPI --> Service
    Service --> Graph["LangGraph"]
    Graph --> Checkpoint["Checkpointer: SQLite file or in-memory tests"]
    Service --> SQL["Configured SQL database"]
    Graph --> Registry["ToolRegistry + ToolPolicy"]
    Registry --> Repositories["Existing SQL repositories"]
    Registry --> Integrations["Existing in-process mocks"]
    Graph --> Tracer["WorkflowTracer"]
    Tracer --> SQL
    Redis["Existing Redis/fakeredis for rate limits"] -. unchanged .-> API
    Qdrant["Existing optional knowledge store"] -. unchanged .-> Graph
    NoNewInfra["No new container, network, port, queue, or cloud resource"]
```

## Component routing reference

| Component | Connection and role | Network exposure in this phase |
|---|---|---|
| Approval API | FastAPI route; authenticates an agent and delegates the decision. | Existing API listener only. |
| Workflow service | Stores decisions and resumes a graph using its thread ID. | In-process Python call. |
| LangGraph interrupt | Saves continuation state and yields an approval request. | No listener; checkpoint connection only. |
| SQL database | Holds approval, ticket, workflow, action, escalation, and event records. | Existing configured DB connection. |
| Checkpointer | Holds graph snapshots separately from SQL business records. | Local SQLite file or test memory saver. |
| ToolRegistry | Enforces registered-tool allow-list and policy at execution. | In-process Python call. |
| Mock integrations | Simulate refund and workspace operations. | No external network call. |
| Escalation API | Reads team assignment and status. | Existing API listener only. |
| Docker/Compose | Unchanged; no new services or network edges. | No new container topology. |

## Honest infrastructure status

- Phase 11 routes and workflow behavior are exercised with temporary SQLite,
  an in-memory checkpointer, and mock integrations.
- The demo script uses the same application routes and remains local.
- In-process `BackgroundTasks` are not a durable distributed worker system.
- No real refund, email, cloud resource, container stack, or live model call
  is claimed.
- No `.gitignore` change is required: `data/`, SQLite/database files,
  Python caches, and local environment files are already ignored.

## Related files

- [Phase 11 system design evolution](../design_evolution/Phase11_Project_System_Design_Evolution.md)
- [Phase 11 codebase explanation](../explain_codebase/phase11_explained.md)
- [Phase 11 interview Q&A](../QnA/Phase11_Interview_QnA.md)
- [Application lifespan and wiring](../../backend/app/main.py)
- [Workflow graph](../../agents/graph.py)
- [Workflow service](../../backend/app/services/workflow_service.py)
- [Approval and escalation routes](../../backend/app/api/)
- [Checkpointer](../../agents/checkpointer.py)
- [Tool registry](../../backend/app/tools/registry.py)
- [Task tracker](../../TASKS.md)
