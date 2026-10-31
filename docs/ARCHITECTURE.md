# CloudDesk Support — Architecture

This document describes the target architecture in [`CLAUDE.md`](../CLAUDE.md).
It is a design reference, not a claim that the components are implemented.

## System context

```text
Support agent
    │ HTTPS
    ▼
Next.js 15 console (:3000)
    │ REST /api/v1 · Bearer JWT · X-Request-ID
    ▼
FastAPI backend (:8000)
    ├── API routers → services → repositories → SQL database
    ├── LangGraph workflow → specialist agents → policy-checked tool registry
    ├── RAG → hybrid retriever → vector store + keyword index
    ├── Memory facade → Redis/fakeredis + customer_memory
    └── mock integrations · structured logs · workflow events
          │
          ├── PostgreSQL / SQLite
          ├── Redis / fakeredis
          ├── Qdrant / in-memory vector store
          └── LLM provider / fake provider
```

In local demo mode, SQLite, fake Redis, an in-memory vector store, mock
integrations, and the fake LLM allow an offline run. Production deployments may
use PostgreSQL, Redis, Qdrant, and an external LLM provider. The frontend only
uses the public/anon client configuration; server-side service-role credentials
must never be exposed to the browser.

## Component responsibilities

| Component | Responsibility | Boundary |
|---|---|---|
| `frontend/` | App Router UI, typed API client, role-aware controls, workflow polling. | All backend calls go through `frontend/lib/api.ts`; no service-role key. |
| `backend/app/api/` | HTTP validation, authentication/authorization, background tasks, status codes. | No business rules or direct SQL. |
| `backend/app/services/` | Orchestrate repositories, workflows, and application operations. | No HTTP framework behavior. |
| `backend/app/repositories/` | SQLAlchemy persistence and queries. | No LLM calls. |
| `backend/app/core/` | Configuration, LLM factory, security, database, logging, Redis, guardrails, observability. | Must not import agents. |
| `backend/app/tools/` | Async tools, policy, and registry. | Every execution goes through `ToolRegistry`. |
| `agents/` | Workflow state, graph nodes, specialists, prompts, and deterministic rules. | No direct SQL. |
| `rag/` | Article ingestion, chunking, vector-store interface, hybrid retrieval. | Does not know about tickets. |
| `memory/` | Short- and long-term memory facades. | Never stores secrets or raw ticket bodies. |
| `integrations/` | Protocols, mock adapters, and MCP integration. | Core does not import integrations. |
| `database/` | PostgreSQL schema, RLS policies, seed script, additive migrations. | Keep SQLAlchemy models and DDL aligned. |

## Ticket workflow

```text
understand_ticket
  → classify_severity
  → customer_context
  → knowledge_retrieval
  → troubleshooting
  → resolution_planning
  → risk_check
      ├─ policy escalation → escalation
      ├─ approval required → human_approval
      │    ├─ approved → execute_resolution
      │    └─ rejected → escalation
      └─ low risk → execute_resolution
  → ticket_summary
  → memory_update
  → END
```

Every node returns a partial state update. `errors` and `completed_nodes` append;
token usage merges. The graph streams updates, and the workflow service persists
state after each node. A checkpointer restores paused runs by `thread_id`.

### Approval/resume lifecycle

1. The authenticated agent requests a run. The API creates a `workflow_runs`
   record and responds with `202 Accepted` and a workflow ID.
2. A background task runs the graph, streaming node state and telemetry.
3. For approval-required actions, the graph pauses at `human_approval`. The
   service records an approval request and puts the ticket in
   `waiting_on_approval`.
4. An authorized agent approves or rejects the request. The decision is
   persisted and audited.
5. Approval resumes the graph and executes the planned action through the same
   registry/policy path. Rejection follows the defined escalation path.
6. The graph writes the final ticket summary and safe memory update. A separate
   agent action sends a validated reply through the mock integration.

Code before a LangGraph interrupt may execute again on resume; it must stay
small and idempotent and must not perform an irreversible side effect.

## Data and trust boundaries

- SQLAlchemy models use portable JSON and string UUIDs so SQLite demo and
  PostgreSQL deployments share the application model.
- PostgreSQL data tables use RLS; the backend service-role credential stays
  server-side.
- Ticket content, retrieved documents, emails, and other external content are
  untrusted. Delimit them and instruct models to treat them only as data.
- The knowledge base is the source for customer-facing policy claims. Replies
  cite evidence and pass output validation.
- Customer memory is per-customer, de-duplicated, and scrubbed. Never store
  payment-card data, API keys, passwords, raw ticket bodies, or another
  customer's data.
- Never expose raw prompts, hidden chain-of-thought, secrets, or other
  customers' data through logs, workflow events, or APIs.

## Cross-cutting behavior

- **Authentication and authorization:** JWT; `viewer < agent < admin`; backend
  `require_role` is authoritative.
- **Rate limiting:** Redis fixed window, with fakeredis in tests/demo.
- **Request correlation:** accept or create `X-Request-ID` and include it in
  response headers and structured logs.
- **Audit:** record every state-changing request with its actor and target.
- **Observability:** workflow events record node lifecycle, tool calls, LLM
  usage, approval events, errors, and completion. Telemetry failure must not
  break a workflow.
- **Secrets:** `.env` and cloud secret stores only; commit placeholders in
  `.env.example`, never actual credentials.

## Deployment shape

The target Compose topology is frontend → backend → Redis and Qdrant, with
health-checked dependencies and named data volumes. Containers run as
non-root users and expose health checks. Cloud mappings and CI/deployment gates
are specified in `CLAUDE.md`; cloud provisioning remains unvalidated until
credentials and a reviewed plan are used.
