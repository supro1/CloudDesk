# CloudDesk Support — Project Memory

This file records durable project decisions and current status. `CLAUDE.md` is
the product source of truth; update this file when confirmed facts or delivery
status change. Do not treat plans as implementation evidence.

## Locked facts

- **Product:** CloudDesk Autonomous Customer Support & Resolution Platform,
  used by support staff rather than customers.
- **Safety:** Human approval is required for consequential money/account actions.
  Policy rules take precedence over LLM judgement.
- **Offline mode:** v1 must run with `DEMO_MODE`, a fake LLM, in-memory vector
  store, and fake/test Redis; real integrations are out of scope.
- **Architecture:** Next.js 15 → FastAPI → data stores, with LangGraph workflow,
  specialist agents, RAG, policy-checked tools, and customer memory.
- **Roles:** `viewer < agent < admin`; enforce authorization on the backend.
- **Data boundaries:** Never place secrets, raw ticket bodies, or another
  customer's data in memory notes, logs, or customer-facing replies.
- **API truth:** `docs/API_CONTRACT.md` is the route/type contract once implemented.
- **Planning truth:** `PLAN_PHASE.md` defines the 13 required phases.
- **Deployment truth:** No real cloud deployment is implied by local files or a
  successful local test.

## Current repository status

Last checked after completing tracker Phase 10 (Workflow graph and trace),
which maps to `PLAN_PHASE.md` Phase 9. Tracker Phase 8 (Memory) maps to
`PLAN_PHASE.md` Phase 11:

- The working tree contains the starter package under `src/project_1/` and
  backend core settings and JSON logging modules, health routes, and request-ID
  handling.
- P2-1 through P2-4 are implemented: SQLAlchemy entities, PostgreSQL schema
  and migrations, repositories, and an atomic demo bootstrap with committed
  sample fixtures.
- P3-1 and P3-2 are implemented: HS256 JWT verification and role enforcement,
  plus demo login and current-profile routes that issue eight-hour,
  Supabase-compatible tokens for the seeded demo profiles.
- P5-1 and P5-2 are implemented: knowledge article loading/chunking,
  deterministic fake embeddings, and in-memory and Qdrant vector stores.
- P5-2 local validation: all 95 pytest tests pass; the project Ruff target and
  Ruff on the changed RAG modules pass. Qdrant adapter behavior was tested with
  a fake client; no live Qdrant service was used.
- P6-1 through P6-4 are implemented: tool registry and policy, repository-backed
  read tools, approval-gated refund and workspace-reset tools, and mock-only
  billing/workspace/status integrations. The registry is initialized with the
  application; no public tool-execution route or real integration is present.
- Phase 6 local validation: all 134 pytest tests pass, Ruff passes for
  `backend`, `tests`, and `integrations`, and Pylance reports no diagnostics in
  the new tool and integration modules. Approval persistence and the human
  decision/resume workflow remain in the later approval phase.
- P7-1 through P7-4 are implemented: deterministic category/severity/escalation
  helpers, injection scanning and escaped untrusted-text wrapping, customer
  output validation, and reusable secret scrubbing. The workflow now uses
  classification/severity and output validation; later approval and
  escalation execution remains separate.
- P8-1 through P8-3 are implemented: expiring Redis/fakeredis memory,
  customer-scoped SQL note recall and de-duplication, and checked resolution
  recording with secret scrubbing and prohibited-text filtering. The workflow
  now recalls and updates safe customer notes.
- Phase 8 focused validation: all 6 tests in `tests/unit/test_memory.py` pass,
  the full offline suite passes with 166 tests, and Ruff passes on the changed
  Python modules.
- P9-1 through P9-8 are implemented: typed workflow schemas, a configurable
  structured-output helper with an offline fake provider, six specialist
  agents, and 13 evaluation cases covering all ten categories. The
  specialists are wired into the workflow graph.
- Phase 9 focused validation: all 20 tests in `tests/agents/` pass; the full
  offline suite passes with 186 tests; targeted Ruff checks pass, and the
  checked Pylance diagnostics report no issues in the selected changed files.
- P10-1 through P10-6 are implemented: shared graph state and reducers,
  SQLite/in-memory checkpointing, specialist nodes, run/status/events APIs,
  workflow persistence, and privacy-conscious node/tool/LLM tracing.
- Phase 10 local validation: the full offline suite passes with 191 tests;
  targeted Ruff checks pass; selected Pylance diagnostics report no errors;
  and `uv lock --check` passes. The full-repository Ruff command still reports
  unrelated pre-existing findings outside the Phase 10 files.
- The `.gitignore` excludes Python caches, pytest cache, local databases, and
  build outputs. Phase 10's checkpoint path is covered by the existing
  `data/` and `*.db` rules, so no additional ignore rule is required.
- `README.md` is only a placeholder at this point.
- CI has not been run. Frontend and deployment builds have not been run.
- Cloud credentials have not been used; nothing has been applied to a real
  cloud account.

Update this section after inspecting current files and running the relevant
validation. Do not copy planned features into the implemented/validated state.

## Current delivery status

| Area | Status |
|---|---|
| Product requirements and target architecture | Specified in `CLAUDE.md`; Phase 8, 9, and 10 explanation, design-evolution, infrastructure, and interview documents are present. |
| Application implementation | P7-1 through P7-4, P8-1 through P8-3, P9-1 through P9-8, and P10-1 through P10-6 are implemented and tested. Approval workflow, frontend, and delivery remain incomplete. |
| Local validation | Full offline suite: 191 passed. Phase 10 targeted Ruff checks pass, selected changed-file Pylance diagnostics report no errors, and `uv lock --check` passes. |
| CI | Not run/confirmed. |
| Cloud credentials and deployment | Not used; nothing deployed. |

## Open decisions and known mismatches

- `TASKS.md` has 14 tracker phases while `CLAUDE.md`/`PLAN_PHASE.md` use 13
  product phases. The tracker mapping table identifies these numbering
  differences; tracker Phase 10 maps to `PLAN_PHASE.md` Phase 9.
- `CLAUDE.md` references a course Git/GitHub workflow document not present in
  this repository. Confirm branch policy from the actual source before relying
  on it.
- The target architecture references external course materials and a separate
  deployment-agent project that are not in this repository. Do not assume those
  dependencies exist locally.
- Exact route payloads should be kept in sync with backend schemas and frontend
  types when implementation begins.

## Working agreements

- Read `CLAUDE.md`, the relevant requirement, API contract, and existing tests
  before changing behavior.
- Keep policy deterministic and test it independently of model output.
- Use `call_structured` for LLM calls and `ToolRegistry` for tool execution.
- Treat all ticket/email/file/web content as untrusted input.
- Keep migrations additive; do not commit local databases, secrets, or
  Terraform state.
- Run offline tests and report the exact validation performed.
