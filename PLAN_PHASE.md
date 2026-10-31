# CloudDesk Support — Phase Plan

This is the 13-phase implementation plan required by [`CLAUDE.md`](./CLAUDE.md).
It defines intended work and acceptance checks, not completed work. If this plan
conflicts with `CLAUDE.md`, update this plan to match the source of truth before
changing implementation.

## Phase 1 — Runtime skeleton

- **Goal:** Establish configuration, structured logging, health checks, request
  IDs, and a repeatable offline test harness.
- **Files:** `backend/app/main.py`; `backend/app/core/`; `backend/app/middleware/`;
  `.env.example`; `Makefile`; `tests/conftest.py`; `tests/api/`.
- **Requirements:** N2, N3, N8; foundation for F14.
- **Tests:** Settings, health readiness/liveness, request-ID propagation, offline
  fixture setup.
- **Demo checkpoint:** `make demo` command and configuration entry point exist;
  document unavailable downstream demo components rather than claiming success.
- **Exit criteria:** App starts with fake providers and no API key; health probes
  respond; request IDs are returned and logged; targeted tests pass.

## Phase 2 — Persistence and demo data

- **Goal:** Add portable SQLAlchemy models, repository boundaries, PostgreSQL
  schema/RLS, migrations, and deterministic demo bootstrap.
- **Files:** `backend/app/models/`; `backend/app/repositories/`;
  `backend/app/services/seed_service.py`; `database/`; `sample_data/`;
  `tests/unit/`; `tests/api/`.
- **Requirements:** F1, F4, F11; N6.
- **Tests:** Model/repository CRUD, SQLite table creation, PostgreSQL schema
  parity with the SQLAlchemy entities, RLS coverage, seed idempotency, and
  database constraints.
- **Demo checkpoint:** Demo data can be loaded into a clean local SQLite
  database.
- **Exit criteria:** SQLite and PostgreSQL use the same domain models; all SQL
  access is in repositories; seed runs only when appropriate and is repeatable.

## Phase 3 — Identity and request guards

- **Goal:** Implement JWT verification, role enforcement, demo authentication,
  rate limiting, and audit middleware.
- **Files:** `backend/app/core/security.py`; `backend/app/core/redis.py`;
  `backend/app/middleware/`; `backend/app/api/auth.py`; auth schemas and tests.
- **Requirements:** N1, N2, N6; role behavior for F12.
- **Tests:** Auth token cases, viewer/agent/admin permissions, rate-limit
  boundaries, audit records, and middleware ordering.
- **Demo checkpoint:** Demo users can authenticate offline and receive
  role-appropriate access.
- **Exit criteria:** Every protected route checks the server-side role; all
  non-GET state-changing requests are auditable.

## Phase 4 — Support API

- **Goal:** Deliver ticket/customer CRUD and establish the typed API contract
  before frontend integration.
- **Files:** `docs/API_CONTRACT.md`; `backend/app/api/tickets.py`;
  `backend/app/api/customers.py`; `backend/app/schemas/`; repositories and API
  tests.
- **Requirements:** F1, F4, and API support for F12.
- **Tests:** Ticket creation, listing/detail, validation, customer reads,
  not-found behavior, and role checks.
- **Demo checkpoint:** Seeded tickets and customer context are accessible using
  the documented API.
- **Exit criteria:** API behavior matches the contract; endpoint changes update
  the contract, backend schemas, and frontend types together.

## Phase 5 — Knowledge pipeline

- **Goal:** Ingest, chunk, index, and retrieve cited support knowledge with
  offline embeddings and hybrid retrieval.
- **Files:** `rag/`; `sample_data/knowledge_base/`; knowledge schemas and API;
  `tests/rag/`.
- **Requirements:** F5, F6.
- **Tests:** Article loading/chunking, vector-store protocol, retrieval modes,
  ranking, cache behavior, filters, and expected article hits.
- **Demo checkpoint:** Knowledge articles can be indexed and searched offline.
- **Exit criteria:** Retrieval returns article-linked evidence in the documented
  shape; reindexing is admin-only; evaluation hit-rate@3 meets its threshold.

## Phase 6 — Tools and mock integrations

- **Goal:** Add the policy-enforcing tool registry, support read tools,
  approval-gated write tools, and mock adapters.
- **Files:** `backend/app/tools/`; `integrations/`; `tests/unit/`;
  `tests/agents/`.
- **Requirements:** F4, F9, F10; N8.
- **Tests:** Registry allow-list, unknown-tool approval, timeout/failure results,
  mock integration behavior, and approval policy.
- **Demo checkpoint:** Tools use mock services only and cannot bypass the
  registry.
- **Exit criteria:** Every tool call uses `ToolRegistry.execute`; consequential
  actions cannot run without recorded approval.

## Phase 7 — Rules and guardrails

- **Goal:** Implement deterministic category/severity/escalation rules,
  untrusted-content handling, customer-output validation, and secret scrubbing.
- **Files:** `agents/rules.py`; `agents/prompts.py`;
  `backend/app/core/guardrails.py`; memory secret-scrub helpers;
  `tests/unit/`; security-focused API/workflow tests.
- **Requirements:** F2, F3, F10; N4, N5, N7.
- **Tests:** Category and severity overrides, escalation policy, injection
  containment, output validation, and secret scrubbing.
- **Demo checkpoint:** CD-1013 remains data; policy tickets deterministically
  route to escalation.
- **Exit criteria:** Rules override model disagreement where required; severity
  rules never lower severity; guardrail failure raises workflow risk.

## Phase 8 — Specialist agents

- **Goal:** Implement structured-output supervisor, customer, knowledge,
  troubleshooting, resolution, and escalation agents.
- **Files:** `agents/specialists/`; `backend/app/schemas/workflow.py`;
  `tests/agents/`; evaluation case data.
- **Requirements:** F2–F8, F10, and F14.
- **Tests:** One focused offline behavior test per specialist; schemas reject
  malformed outputs; policy decisions remain deterministic.
- **Demo checkpoint:** Each specialist can run with fake LLM and mock tools.
- **Exit criteria:** LLM calls use `call_structured`; output models are
  validated; planned actions are deterministic and grounded.

## Phase 9 — Workflow graph and tracing

- **Goal:** Wire node state, reducers, checkpointer, workflow graph, persistence,
  and per-node/tool/LLM tracing.
- **Files:** `agents/state.py`; `agents/graph.py`; `agents/checkpointer.py`;
  `agents/nodes/`; `backend/app/services/workflow_service.py`;
  workflow-event schemas/repositories/API; `tests/workflow/`.
- **Requirements:** F11, F13, F14.
- **Tests:** Graph shape/routing, reducer behavior, checkpoint persistence,
  workflow polling, event recording, usage/cost estimates, and offline runs.
- **Demo checkpoint:** A low-risk ticket can traverse the graph offline and
  produce an inspectable trace.
- **Exit criteria:** Each node persists state and reports completion; tracing
  does not break workflow execution; raw prompts and secrets are never exposed.

## Phase 10 — Approval and escalation

- **Goal:** Add approval interrupts/resume, recorded decisions, named-team
  escalation, and safe resolution execution.
- **Files:** `agents/nodes/human_approval.py`; approval/escalation services and
  APIs; action repositories; `tests/api/`; `tests/workflow/`.
- **Requirements:** F9, F10; N6 and money/account safety invariants.
- **Tests:** Refund pause/approve, rejection/escalation, security auto-escalation,
  resume conflicts, duplicate approval requests, and unauthorized access.
- **Demo checkpoint:** `make demo` supports CD-1002 approval and CD-1005
  security escalation using mocks.
- **Exit criteria:** Consequential tools execute only after durable approval;
  policy escalations identify the responsible team; interrupts are idempotent.

## Phase 11 — Memory

- **Goal:** Implement short-term Redis/fakeredis memory and safe long-term
  customer-memory recall/update.
- **Files:** `memory/`; customer-memory model/repository; customer-context and
  memory-update nodes; `tests/unit/`; `tests/workflow/`.
- **Requirements:** F4, F11, F14; N7.
- **Tests:** TTL/cache behavior, recall limits, duplicate suppression, secret
  scrubbing, prohibited-content filtering, and per-customer isolation.
- **Demo checkpoint:** A completed run can recall and record safe memory offline.
- **Exit criteria:** Only approved note types are stored; secrets, raw ticket
  text, and other customers' data are excluded.

## Phase 12 — Agent console

- **Goal:** Build the authenticated Next.js console and ticket workflow screen
  with typed backend integration.
- **Files:** `frontend/app/`; `frontend/components/`; `frontend/lib/`;
  `frontend/__tests__/`; frontend Dockerfile.
- **Requirements:** F12; presentation for F5, F7, F8, and F13; N1.
- **Tests:** API client, role-aware controls, polling, workflow steps, evidence,
  diagnosis, reply editing, approval/rejection, and error states.
- **Demo checkpoint:** The frontend and offline backend work together locally;
  a viewer cannot invoke agent actions.
- **Exit criteria:** Backend access goes through the typed API client; frontend
  types match `API_CONTRACT.md`; pending-only approval UX is enforced.

## Phase 13 — Evaluation and delivery

- **Goal:** Gate product quality and prepare container, CI, and cloud deployment
  configurations without claiming unexecuted deployments.
- **Files:** `tests/evaluation/`; `tests/deployment/`; `datasets/`;
  Docker/Compose files; `.github/workflows/`; `deployment/`; documentation.
- **Requirements:** All F1–F14 and N1–N8; evaluation thresholds.
- **Tests:** Full offline suite, evaluation thresholds, container hygiene,
  Terraform validation, secret-file checks, and smoke tests where available.
- **Demo checkpoint:** `make demo` runs on the completed local stack; CI and
  cloud execution status are reported separately.
- **Exit criteria:** All evaluation thresholds pass; deployment configuration
  validates; cloud apply and CI are reported only after actually run.

## Cross-phase rules

1. Keep boundaries from `CLAUDE.md` section 4.2; API, service, repository,
   agent, tool, RAG, and memory responsibilities must remain distinct.
2. Read the API contract, the relevant requirement, and existing tests before
   changing behavior.
3. Add a test mapping for every acceptance criterion introduced.
4. Preserve offline operation and run the narrowest relevant tests before the
   full suite.
5. Keep migrations additive and approval gates auditable.
6. Report implemented, locally validated, CI-validated, and deployed states
   separately.

## Status

All phases are planned, not complete. The current repository status is recorded
in [`MEMORY.md`](./MEMORY.md); task-level checkboxes remain in [`TASKS.md`](./TASKS.md).
