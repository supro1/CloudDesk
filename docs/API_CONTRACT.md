# CloudDesk Support — API Contract

This is the intended REST contract for the product described in
[`CLAUDE.md`](../CLAUDE.md). It documents target behavior; it does not assert
that these routes currently exist. Keep this file, backend Pydantic schemas,
and `frontend/lib/types.ts` synchronized when implementing or changing routes.

## Conventions

- Base path: `/api/v1`, except health probes.
- Authentication: `Authorization: Bearer <JWT>` for protected routes.
- Every response includes `X-Request-ID`; requests may supply one to correlate
  logs and events.
- JSON request and response bodies use `snake_case`.
- Errors use `{"detail": "<message>"}`.
- Authenticated routes enforce the role table below server-side. The UI's
  disabled controls are not an authorization boundary.
- Pagination uses `limit` and `offset` where a list endpoint supports them.
- Timestamps are ISO 8601 UTC strings. IDs are UUID strings unless otherwise
  noted.

### Roles

| Role | Read | Run workflow/reply/escalate | Approve/reject | Admin operations |
|---|---:|---:|---:|---:|
| `viewer` | Yes | No | No | No |
| `agent` | Yes | Yes | Yes | No |
| `admin` | Yes | Yes | Yes | Yes |

### Shared enums

- `category`: `login_issue`, `billing`, `api_failure`,
  `workspace_permissions`, `storage_quota`, `integration`,
  `feature_request`, `account`, `security`, `other`.
- `severity`: `low`, `medium`, `high`, `critical`.
- `channel`: `email`, `chat`, `web`, `api`.
- `ticket_status`: `new`, `in_progress`, `waiting_on_customer`,
  `waiting_on_approval`, `escalated`, `resolved`, `closed`.
- `approval_status`: `pending`, `approved`, `rejected`.

## Health

These routes are unprefixed and require no user JWT.

| Method and path | Purpose | Response |
|---|---|---|
| `GET /health` | General health response. | `200` with service status. |
| `GET /health/live` | Liveness probe; no dependency I/O. | `200` when process is alive. |
| `GET /health/ready` | Readiness check for database, Redis, vector store, and LLM provider. | `200` when ready; non-2xx when a required dependency is unavailable. |

## Authentication

| Method and path | Role | Purpose |
|---|---|---|
| `POST /api/v1/auth/login` | Public/demo | Authenticate a demo user and return a JWT and profile. |
| `GET /api/v1/auth/me` | Any authenticated role | Return the current profile and role. |

Login response shape:

```json
{
  "access_token": "<JWT>",
  "token_type": "bearer",
  "expires_in": 28800,
  "user": {
    "id": "<uuid>",
    "email": "sam.agent@clouddesk.demo",
    "role": "agent",
    "display_name": "Sam Agent"
  }
}
```

Demo identities are `admin@clouddesk.demo`, `sam.agent@clouddesk.demo`, and
`vic.viewer@clouddesk.demo`. Demo tokens expire in eight hours. Production
authentication must validate JWTs using the configured signing secret; do not
infer authorization from client-supplied role fields.

## Dashboard

| Method and path | Role | Purpose |
|---|---|---|
| `GET /api/v1/dashboard/summary` | Any authenticated role | Return ticket counts/status summary and operational metrics available to the caller. |

## Tickets

Ticket object:

```json
{
  "id": "<uuid>",
  "ticket_number": "CD-1001",
  "subject": "SSO login fails for whole team",
  "customer_id": "<uuid>",
  "channel": "email",
  "status": "new",
  "category": "login_issue",
  "severity": "high",
  "severity_reason": "The whole team is unable to sign in.",
  "summary": null,
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z"
}
```

| Method and path | Role | Purpose |
|---|---|---|
| `POST /api/v1/tickets` | `agent`+ | Create a ticket from a supported channel. |
| `GET /api/v1/tickets` | Any authenticated role | List tickets; supports pagination and status/category/severity filters. |
| `GET /api/v1/tickets/{ticket_id}` | Any authenticated role | Return ticket, messages, customer summary, and current workflow/approval summary as authorized. |
| `PATCH /api/v1/tickets/{ticket_id}` | `agent`+ | Update supported agent-editable ticket fields. |
| `POST /api/v1/tickets/{ticket_id}/run` | `agent`+ | Start workflow; returns `202` and a workflow ID. |
| `GET /api/v1/tickets/{ticket_id}/workflow` | Any authenticated role | Return latest workflow status and current state summary. |
| `GET /api/v1/tickets/{ticket_id}/events` | Any authenticated role | Return inspectable workflow events without prompts/secrets. |
| `POST /api/v1/tickets/{ticket_id}/reply` | `agent`+ | Validate and record/send a customer reply through the mock integration. |
| `POST /api/v1/tickets/{ticket_id}/request-info` | `agent`+ | Record a request for more customer information. |
| `POST /api/v1/tickets/{ticket_id}/escalate` | `agent`+ | Escalate the ticket with a reason and named team. |

Ticket creation body:

```json
{
  "subject": "Uploads fail",
  "body": "Customer-provided message",
  "customer_id": "<uuid>",
  "channel": "web",
  "external_id": null
}
```

Ticket list response:

```json
{
  "items": [],
  "total": 0,
  "limit": 50,
  "offset": 0
}
```

Workflow start response:

```json
{
  "workflow_id": "<uuid>",
  "status": "queued"
}
```

The run endpoint responds with `409 Conflict` if the ticket is already
`waiting_on_approval`. Resuming a run that is not paused also returns `409`.
Validation errors return `422`, missing resources return `404`, and insufficient
role returns `403`.

## Approvals

Approval object:

```json
{
  "id": "<uuid>",
  "ticket_id": "<uuid>",
  "workflow_id": "<uuid>",
  "action": "create_refund_request",
  "summary": "Request a billing adjustment for unused seats.",
  "status": "pending",
  "requested_at": "2026-01-01T00:00:00Z",
  "decided_at": null,
  "decided_by": null
}
```

| Method and path | Role | Purpose |
|---|---|---|
| `GET /api/v1/approvals` | `agent`+ | List approval requests visible to the agent. |
| `POST /api/v1/approvals/{approval_id}/approve` | `agent`+ | Record approval and resume the paused workflow. |
| `POST /api/v1/approvals/{approval_id}/reject` | `agent`+ | Record rejection and route through the configured safe path. |

Approve/reject requests may include a `reason`. A decision is durable and
auditable; clients cannot directly execute the action by sending an `approved`
flag to a tool endpoint.

## Customers

| Method and path | Role | Purpose |
|---|---|---|
| `GET /api/v1/customers` | Any authenticated role | List customers with pagination and supported filters. |
| `GET /api/v1/customers/{customer_id}` | Any authenticated role | Return customer, subscription/workspace summary, and permitted ticket history. |

Customer responses must not include secrets or data belonging to other
customers. Memory notes are subject to the same isolation and scrubbing rules.

## Knowledge

| Method and path | Role | Purpose |
|---|---|---|
| `GET /api/v1/knowledge` | Any authenticated role | List available knowledge articles. |
| `GET /api/v1/knowledge/{article_id}` | Any authenticated role | Return an article's permitted content and metadata. |
| `POST /api/v1/knowledge/search` | Any authenticated role | Search using `query`, optional `category`, `mode`, and `top_k`. |
| `POST /api/v1/knowledge/reindex` | `admin` | Recreate/reindex the configured knowledge collection. |

Evidence objects:

```json
{
  "id": "<chunk-id>",
  "title": "Account recovery",
  "source": "kb://account-recovery#reset-mfa",
  "snippet": "Relevant cited excerpt.",
  "score": 0.87,
  "url": "/knowledge/<article-id>",
  "article_id": "<article-id>"
}
```

Search modes are `hybrid`, `semantic`, and `keyword`; the default is `hybrid`.
Knowledge is the only source for customer-facing policy claims, and responses
must retain article citations.

## Escalations

| Method and path | Role | Purpose |
|---|---|---|
| `GET /api/v1/escalations` | Any authenticated role | List escalations with supported filters and pagination. |
| `GET /api/v1/escalations/{escalation_id}` | Any authenticated role | Return escalation reason, assigned team, status, and linked ticket. |

Policy cases must be routed to a named team according to deterministic
escalation rules. Policy takes precedence over model-generated judgement.

## Agents and workflow metadata

| Method and path | Role | Purpose |
|---|---|---|
| `GET /api/v1/agents` | Any authenticated role | Return workflow node and edge metadata used by the console. |

Workflow events may include `node_started`, `node_completed`, `tool_called`,
`llm_called`, `approval_requested`, `approval_resolved`, `error`, and
`workflow_completed`. Events expose timing, status, token usage, and estimated
cost where available. Never expose raw prompts, hidden chain-of-thought, secrets,
or other customers' data.

## Audit and settings

| Method and path | Role | Purpose |
|---|---|---|
| `GET /api/v1/audit` | Any authenticated role | List audit records permitted to the caller. |
| `GET /api/v1/settings` | `admin` | Read supported application settings; redact secret values. |
| `PATCH /api/v1/settings` | `admin` | Update explicitly supported non-secret settings. |

All state-changing requests produce an audit record. Never return credentials
from settings endpoints.

## MCP tools

| Method and path | Role | Purpose |
|---|---|---|
| `GET /api/v1/mcp/tools` | Any authenticated role | List available MCP tool metadata. |

Tool execution remains behind the same registry and policy used by the workflow.
This contract does not authorize exposing a tool that bypasses RBAC, approval,
or audit controls.

## Error behavior

| Status | Meaning |
|---:|---|
| `400` | Invalid state transition or malformed operation. |
| `401` | Missing, invalid, or expired authentication. |
| `403` | Authenticated user lacks the required role. |
| `404` | Ticket, customer, approval, escalation, or article does not exist. |
| `409` | Conflicting workflow/approval state; includes the documented already-waiting or not-paused cases. |
| `422` | Request validation failed. |
| `429` | Rate limit exceeded. |
| `5xx` | Unexpected server/dependency failure; do not return success-shaped fallback data. |

Error responses use `{"detail": "..."}` and include the response `X-Request-ID`.
Do not include secrets, raw prompts, or another customer's data in error details.
