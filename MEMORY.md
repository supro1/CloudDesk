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

Last checked while creating this file:

- The working tree contains the starter package under `src/project_1/` and
  initial backend core settings and JSON logging modules under
  `backend/app/core/`.
- The platform backend, frontend, database, RAG, workflow, and deployment
  implementation described in `CLAUDE.md` is otherwise not yet present.
- `README.md` is only a placeholder at this point.
- P1-1 settings and JSON logging, P1-2 health/request-ID handling, and P1-3
  offline pytest setup are implemented. The current 16-test suite passed locally
  with pytest; broader platform tests, builds, and CI have not been run.
- Cloud credentials have not been used; nothing has been applied to a real
  cloud account.

Update this section after inspecting current files and running the relevant
validation. Do not copy planned features into the implemented/validated state.

## Current delivery status

| Area | Status |
|---|---|
| Product requirements and target architecture | Specified in `CLAUDE.md`; documentation support files are being established. |
| Application implementation | P1-1 settings/logging, P1-2 health/request-ID handling, and P1-3 offline pytest harness implemented; platform runtime remains incomplete. |
| Local validation | 16 tests passed using pytest; dependency lockfile is current. |
| CI | Not run/confirmed. |
| Cloud credentials and deployment | Not used; nothing deployed. |

## Open decisions and known mismatches

- `TASKS.md` is a pre-existing, more granular execution tracker with 14 numbered
  phases. `CLAUDE.md` is authoritative and specifies 13 phases; reconcile
  tracker numbering and mappings before using it as a status authority.
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
