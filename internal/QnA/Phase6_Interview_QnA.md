# Phase 6 — Interview Questions and Answers

This Q&A covers CloudDesk's tool registry, support read tools, approval-gated
operations, and mock integrations. Answers describe the implemented Phase 6
scope and distinguish it from later workflow, deployment, or live-provider
work.

## Product and phase overview

### 1. What was the goal of Phase 6?

To give a later support workflow a small, controlled set of tools for reading
account context, searching support material, checking simulated service
status, and performing specific support actions safely.

### 2. How would you explain Phase 6 to a non-technical person?

I added a controlled tool panel for the support system. Some buttons only
look up information. Buttons that could affect money or account settings are
blocked unless an approval signal is provided. The outside-system connections
are practice versions, so they cannot affect real customer accounts.

### 3. What analogy would you use?

It is a service desk with a supervisor-controlled button panel: staff can
look up records, while sensitive actions need the supervisor's approval.
Billing and workspace actions use a training simulator rather than a live
system.

### 4. What are the Phase 6 tasks?

P6-1 creates the registry and policy. P6-2 adds read-only support tools.
P6-3 adds write tools and approval gates. P6-4 provides mock integration
interfaces and adapters.

### 5. Is Phase 6 an autonomous support agent?

No. It provides tools that a later workflow can use. It does not classify
tickets, choose a resolution, generate a response, or run a LangGraph flow.

### 6. What is implemented at the end of Phase 6?

An app-internal registry with an allow-list, deterministic approval policy,
execution timeout, sanitized failure results, repository-backed support
tools, cited knowledge search, persisted ticket updates and escalation
records, plus local mock billing, workspace, and status adapters.

## Registry and policy

### 7. What is a tool in this system?

A tool is a named asynchronous operation with a defined input schema and
one responsibility, such as reading a subscription or creating a simulated
refund request.

### 8. Why have a registry instead of invoking tool functions directly?

The registry centralizes tool allow-listing, approval checks, timeouts, and
result handling. Callers use one controlled execution path instead of
deciding independently whether an operation is safe.

### 9. What happens when an unregistered tool is requested?

The registry returns a failure result. The tool is not invoked, even if the
caller says it is approved.

### 10. What does the policy decide?

It deterministically classifies known tools as approval-free or
approval-required. Refunds and workspace setting resets require approval by
default. Unknown tool names are classified as requiring approval, and they
are still rejected by the registry because they are not registered.

### 11. What happens when a consequential tool has no approval signal?

The registry returns an approval-required result before calling the
implementation. Tests verify that the mock adapter has no side effect in
that case.

### 12. Does `approved=True` itself create a durable human approval record?

No. It is the internal approval signal consumed by the registry. A persisted
request, human decision, actor attribution, and resume workflow belong to
the later approval phase. Phase 6 does not claim that lifecycle is complete.

### 13. Why does the registry have a timeout?

A slow or stuck tool should not hold the workflow indefinitely. The registry
returns an explicit timeout failure after the configured limit.

### 14. How are tool exceptions handled?

The registry returns a failure result with the error type but does not expose
the internal exception message. It also logs the tool name and error type.
This keeps a tool failure visible without echoing private diagnostic text.

### 15. Can tool calls bypass the registry?

The application constructs a registry as the supported internal execution
path, and tool functions are not exposed through a public HTTP route. The
architecture expects internal callers to use the registry. Python code with
direct access to a tool object could call it, so this is an application
boundary enforced by construction and usage rather than a process sandbox.

## Read-only support tools

### 16. Which read tools are available?

`get_customer`, `get_subscription`, `get_ticket_history`, `search_docs`, and
`check_service_status`.

### 17. What does `get_customer` return?

It reads a customer profile and the names, slugs, and active states of that
customer's workspaces. It does not return workspace setting contents.

### 18. What does `get_subscription` return?

It returns the customer's subscriptions, including plan, status, seat use,
storage use, and any billing-period dates.

### 19. How does `get_ticket_history` protect against unbounded responses?

It limits the result to between 1 and 50 tickets. The default is 10, and the
repository orders the records by recency.

### 20. Does ticket history return every message body?

No. It returns ticket-level information such as subject, status, category,
severity, summary, and creation time. It does not return an unbounded
conversation transcript.

### 21. How does `search_docs` work?

It loads published article records through the article repository and
delegates retrieval to the existing knowledge service. It returns evidence
including the article source and URL rather than inventing a citation.

### 22. What limits apply to article search?

The query must not be blank, result count must be between 1 and 20, and
retrieval can be selected as hybrid, semantic, or keyword. Only published
articles are searched.

### 23. What does `check_service_status` check?

It asks the status integration interface, which Phase 6 wires to a mock
implementation. Known mock services return configured status. Unknown
service names return `unknown` with an explanatory message.

### 24. Are these tools read-only in the database sense?

The five tools in P6-2 do not write customer or ticket records. `search_docs`
may initialize or refresh its derived search index through the existing
knowledge service, but it does not change support tickets or customers.

## Write tools and approval

### 25. Which write tools exist?

`update_ticket`, `create_refund_request`, `reset_demo_setting`, and
`create_escalation`.

### 26. Which actions require approval?

Refund requests and workspace setting resets are approval-gated by default.
Ticket updates and creating an escalation are not gated by the current
policy. Escalation is the safe route for handing off a risky issue.

### 27. Does `create_refund_request` issue a refund?

No. It asks the mock billing adapter to create a simulated request. The
result is marked as a mock and explicitly says no money was moved.

### 28. Why does the refund policy validate the amount?

The optional approval-free policy path must fail closed. Invalid, missing,
negative, or non-finite amounts do not qualify for an approval exemption.
The tool itself also requires a valid positive amount before calling the
mock adapter.

### 29. Can a refund tool act on a different customer's ticket?

The tool loads the ticket and checks that its customer ID matches the
supplied customer ID before calling billing. A mismatch fails explicitly.

### 30. What does `reset_demo_setting` change?

It calls the mock workspace adapter, which resets one of its supported
settings in process memory. It does not update the persisted workspace
record or call a real workspace service.

### 31. What fields can `update_ticket` change?

It accepts a supported ticket status and/or an internal summary. It rejects
unknown statuses, blank summaries, and requests that provide no fields.
Repository validation still protects immutable database fields.

### 32. What does `create_escalation` persist?

It records a named team, reason, ticket, and optional workflow-run reference
in the existing escalation table. If a workflow-run ID is provided, the
tool verifies that the run belongs to the specified ticket.

### 33. Why is escalation not approval-gated?

Escalation is a controlled hand-off to a support team, rather than a money
movement or account mutation. The policy treats this as the safe path.

## Integrations and architecture

### 34. What is an integration protocol?

It is a Python interface describing the operation expected from an external
system, without tying tool code to a specific vendor's SDK.

### 35. Which integration protocols are present?

Billing request creation, workspace setting reset, and service status lookup.

### 36. What does the integration factory return?

It returns a bundle containing mock billing, workspace, and service-status
implementations. The support tool factory uses that bundle to build the
registered tools.

### 37. Why use mocks?

Mocks make the flows testable offline, avoid API keys and service costs, and
ensure tests cannot accidentally move money or alter a real workspace.

### 38. Can a real service implementation be added later?

Yes. The protocol is the boundary for doing so. A real adapter would need
separate credentials, network controls, error handling, audit requirements,
and security review; none are claimed in this phase.

### 39. Where is the registry created?

The FastAPI lifespan creates it after the knowledge service is initialized
and stores it in `app.state.tool_registry`. It does not add a public tool
route or a new process.

### 40. Why do tools use repositories?

Repositories own SQL access. Tool functions orchestrate a small support
operation without writing SQL directly, keeping data persistence in its
designated layer.

### 41. Does the tool layer call an LLM?

No. These tools are ordinary structured async functions. The LLM and
workflow orchestration are separate later-phase components.

### 42. Does Phase 6 add Docker networking?

No. The tool registry and mock adapters run in the existing backend process.
There are no new ports, containers, DNS names, or Compose services in this
phase.

### 43. What database or vector store does it use?

It uses the application's configured session factory and the existing
knowledge service. The local default is SQLite and an in-memory vector store.
Optional configured database or Qdrant connections are not provisioned by
Phase 6.

## Testing and honest status

### 44. How was Phase 6 tested?

Offline tests cover registered tool behavior, read results and citations,
approval blocking before side effects, approved mock actions, ticket update
and escalation persistence, and mock service outputs. Existing registry and
policy tests cover unknown tools, timeouts, error results, and refund
threshold behavior.

### 45. Do the tests require API keys or live integrations?

No. The tests use an in-memory SQLite database, an in-memory vector store,
fake embeddings, and local mock adapters.

### 46. What is not done after Phase 6?

There is no workflow graph or UI that calls these tools, no durable approval
decision lifecycle, no real billing or workspace connector, and no Docker
or cloud deployment change from this phase.

### 47. What would you do before production?

I would complete durable approval recording and identity attribution, add
audit coverage for internal tool execution, implement and review real
provider adapters, set least-privilege credentials, and test failure,
idempotency, rate-limit, and data-isolation behavior under deployment
conditions.

### 48. How would you summarize the largest design decision?

“I put one policy-enforcing registry in front of named tools, and kept
provider-specific behavior behind interfaces. That made the local demo safe
and testable while preserving a clear place to add real integrations later.”

### 49. How would you summarize Phase 6 in one sentence?

“Phase 6 added repository-backed support tools and a centralized execution
policy, with approval gates for consequential actions and mock-only
integrations for safe offline testing.”

## Repository references

- [Phase 6 codebase explanation](../explain_codebase/phase6_explained.md)
- [Phase 6 system design evolution](../design_evolution/Phase6_Project_System_Design_Evolution.md)
- [Phase 6 infrastructure and wiring](../Infra_design_evolution/Phase6_Infra_design_evolution.md)
- [Tool registry, policy, and tool construction](../../backend/app/tools/)
- [Integration protocols and mocks](../../integrations/)
- [Application startup](../../backend/app/main.py)
- [Phase 6 support-tool tests](../../tests/unit/test_support_tools.py)
- [Registry and policy tests](../../tests/unit/test_tool_registry.py) and [approval policy tests](../../tests/unit/test_tool_policy.py)
- [Task tracker](../../TASKS.md)
