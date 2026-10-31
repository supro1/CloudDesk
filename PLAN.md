# CloudDesk Support — Requirements Catalog

This catalog turns the product requirements in [`CLAUDE.md`](./CLAUDE.md) into
implementation and verification targets. `CLAUDE.md` is authoritative if details
conflict. This document describes the intended product; it is not evidence that a
feature has been implemented.

## Product goal

Build an agent-facing support-resolution platform for CloudDesk. The system
investigates incoming support tickets, gathers customer and knowledge context,
proposes a grounded resolution, and routes risky or consequential work through
human approval.

The v1 system must run locally in offline demo mode without an LLM API key. Real
emails, real refunds, a customer-facing chat widget, and multi-language support
are out of scope.

## Functional requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| F1 | Create tickets from email, chat, web, and API channels. | API tests cover valid creation, validation errors, and persistence. |
| F2 | Classify a ticket into exactly one of the ten supported categories and provide a one-line summary. | Supervisor tests and evaluation dataset cover all categories. |
| F3 | Assign low, medium, high, or critical severity with a reason; deterministic rules may raise, never lower, model severity. | Unit tests cover policy overrides and severity boundaries. |
| F4 | Load customer, subscription, workspace, ticket-history, and memory context. | Customer-agent tests cover available, missing, and empty context. |
| F5 | Retrieve cited knowledge evidence using semantic and keyword retrieval with reranking. | RAG tests verify modes, ranking, article citations, and expected retrievals. |
| F6 | Find similar previously resolved cases. | Knowledge-agent tests verify relevance and exclude unsuitable cases. |
| F7 | Produce probable causes and numbered troubleshooting steps. | Troubleshooting-agent tests validate the structured diagnosis. |
| F8 | Produce a resolution plan with summary, customer reply, internal notes, and proposed actions. | Resolution-agent tests validate schema, grounding, and output guardrails. |
| F9 | Require recorded human approval for consequential actions. | Workflow/API tests prove the action pauses, records a decision, and only executes after approval. |
| F10 | Escalate policy cases to a named team using deterministic policy rules. | Rules and workflow tests cover security, data loss, deletion, disputes, and outages. |
| F11 | Record a ticket summary and safe customer-memory update after each completed workflow. | Workflow and memory tests verify updates, redaction, and deduplication. |
| F12 | Let an authorized support agent approve/reject, escalate, reply, or request information from the ticket screen. | Frontend tests and API RBAC tests cover each action and role. |
| F13 | Make workflow nodes, tool calls, and LLM calls inspectable, with timing, token usage, and estimated cost. | Tracing/API tests cover event types and usage; no raw prompts or secrets are exposed. |
| F14 | Run the application offline in `DEMO_MODE` without an API key. | Offline test suite and demo run use the fake LLM, memory vector store, and test Redis. |

Supported categories are `login_issue`, `billing`, `api_failure`,
`workspace_permissions`, `storage_quota`, `integration`, `feature_request`,
`account`, `security`, and `other`. Add categories to the common schema before
using them elsewhere.

## Non-functional requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| N1 | JWT authentication compatible with Supabase-issued tokens. | Auth tests cover valid, expired, malformed, and role-bearing tokens. |
| N2 | Redis-backed fixed-window rate limiting. | Tests verify limits and the configured demo behavior. |
| N3 | Every response has an `X-Request-ID`, generated when absent and propagated when supplied. | Middleware/API tests cover both cases. |
| N4 | Ticket and external content is untrusted data, not instructions. | Injection tests prove malicious ticket text cannot alter tool policy or workflow. |
| N5 | Validate customer-facing output before it is shown or sent. | Guardrail tests block secrets, internal URLs, and other customers' data. |
| N6 | Audit every state-changing request. | Middleware/API tests verify actor, action, and target are recorded. |
| N7 | Never persist secrets or raw ticket bodies in customer-memory notes. | Memory tests cover secret scrubbing and prohibited content. |
| N8 | Keep the design deployable as containers to AWS, Azure, and GCP. | Deployment configuration and hygiene tests validate supported deployment targets. |

## Roles and authorization

| Role | Permissions |
|---|---|
| `viewer` | Read tickets, customers, knowledge, and audit data. |
| `agent` | Viewer permissions plus run workflows, reply, approve/reject, and escalate. |
| `admin` | Agent permissions plus knowledge reindexing and settings administration. |

Authorization is enforced by backend `require_role` checks. Frontend controls are
an additional usability layer and never replace server-side authorization.

## Safety and policy invariants

- Refunds, account changes, setting resets, deletions, and disputes never execute
  unattended; require an approval record where applicable.
- Policy escalation rules take precedence over LLM judgement.
- Prompt-injected ticket text (including CD-1013) remains untrusted data and must
  never cause exports or unauthorized tool calls.
- Replies must be grounded in retrieved knowledge and pass output validation.
- Memory stores only scrubbed, minimal notes about the same customer.
- Tool calls execute through `ToolRegistry`; unknown tools require approval.
- Never store secrets in source control, logs, customer replies, or memory.

## Product success metrics

Track, but do not hard-code, resolution without human edits, median
time-to-first-response, escalation precision, and refund approvals per week.
Refund approvals must never be driven to zero-touch automation.

## Verification gates

The offline test suite is the primary feature gate. Evaluation thresholds are:

| Metric | Minimum |
|---|---:|
| Classification accuracy | 0.80 |
| Retrieval hit-rate@3 | 0.75 |
| Escalation correctness | 0.90 |
| Citation rate | 0.90 |
| Grounding rate (steps present in reply) | 0.90 |

Each requirement must map to at least one automated test. The phase-by-phase
implementation and exit criteria are in [`PLAN_PHASE.md`](./PLAN_PHASE.md).
The currently visible execution checklist is [`TASKS.md`](./TASKS.md).

## Current implementation status

The repository is currently a Python starter, not the finished platform. The
intended architecture and requirements are specified, but application
implementation, local validation, CI execution, and cloud deployment must be
tracked separately. See [`MEMORY.md`](./MEMORY.md) for the current status record.
