# Phase 9 - Project System Design Evolution

## Scope and implementation status

In `TASKS.md`, Phase 9 is the Specialist Agents phase (P9-1 through P9-8).
`PLAN_PHASE.md` numbers this product stage Phase 8. This phase implements
typed specialist components and an offline evaluation dataset. It does not
wire them into a LangGraph, API endpoint, or application route; those belong
to the next workflow phase.

## Starting point: policies, data, RAG, tools, and memory, but no agents

At the start of this phase, CloudDesk has deterministic rules and guardrails,
SQL repositories, a permissioned tool registry, knowledge retrieval, mock
integrations, and short-/long-term memory facades. There is no set of
specialist classes coordinating those pieces.

```mermaid
flowchart LR
    Ticket["Ticket data"] --> Rules["Existing category, severity, escalation, and injection rules"]
    Ticket --> Tools["Existing support ToolRegistry"]
    Tools --> SQL["SQL repositories"]
    Tools --> RAG["Knowledge service and retrieval"]
    Tools --> Mocks["Mock integrations"]
    Memory["Short- and long-term memory facades"]
    Missing["No structured specialist agents or workflow graph"]
```

## Milestone P9-1: define schemas and a structured LLM boundary

Workflow Pydantic models make the expected result explicit. `call_structured`
is the only model-call helper: it uses the configured LangChain chat model or
the deterministic fake provider, validates the result, measures elapsed time,
and returns token usage. A schema-validation failure gets one bounded retry
by default; provider and validation errors remain visible.

```mermaid
flowchart TB
    Agent["Specialist caller"] --> Call["call_structured(schema, prompts)"]
    Call --> Provider{"Configured provider"}
    Provider -->|DEMO_MODE / fake| Fake["FakeLLM with configured or default structured response"]
    Provider -->|real provider| LangChain["LangChain structured-output adapter"]
    Fake --> Raw["Structured result and usage"]
    LangChain --> Raw
    Raw --> Validate["Pydantic model validation"]
    Validate -->|valid| Result["Typed output + token counts + duration"]
    Validate -->|invalid, retry remains| Retry["One bounded repair attempt"]
    Retry --> Provider
    Validate -->|invalid after retry| Error["Validation error returned to caller"]
```

The fake provider uses no API key or external service. Its configured test
responses allow tests to exercise both valid and malformed output paths.

## Milestone P9-2: add the supervisor

The supervisor wraps the ticket's subject and body as untrusted text before
asking for structured classification. Deterministic category rules override
the model when a known pattern matches. The injection scanner supplies a
separate safety flag. Severity is the greater of the proposed and model
levels, after which policy rules may raise it further.

```mermaid
flowchart LR
    TicketText["Subject and customer body"] --> Rules["Deterministic category and severity rules"]
    TicketText --> Scanner["Injection scanner"]
    TicketText --> Wrapped["Escaped untrusted-content boundary"]
    Wrapped --> LLM["Structured classification / severity call"]
    Rules --> Category["Policy category overrides model category"]
    LLM --> Category
    Scanner --> Result["Classification with injection flag"]
    Category --> Result
    Severity["Proposed severity"] --> Max["Keep higher proposed or model level"]
    LLM --> Max
    Rules --> Max
    Max --> Assessment["Final severity and reason"]
```

This keeps untrusted ticket text as data. It does not grant model output tool
permissions or change a ticket.

## Milestone P9-3: add the customer-context specialist

The customer specialist makes no LLM call and has no SQL in the agent
module. It gathers the customer, subscription, and ticket history through
the registered read tools, and recalls the customer's memory through the
long-term-memory facade.

```mermaid
flowchart LR
    Agent["CustomerAgent"] --> Registry["ToolRegistry"]
    Registry --> CustomerTool["get_customer"]
    Registry --> SubscriptionTool["get_subscription"]
    Registry --> HistoryTool["get_ticket_history"]
    CustomerTool --> Context["Typed CustomerContext"]
    SubscriptionTool --> Context
    HistoryTool --> Context
    Agent --> Memory["LongTermMemory.recall_customer"]
    Memory --> SQLRepo["CustomerMemoryRepository"]
    SQLRepo --> SQL["customer_memory table"]
    Memory --> Notes["Same-customer memory notes, max 10"]
    Notes --> Context
```

Each tool failure is surfaced as an error. Empty records for a valid customer
are valid empty context, rather than fabricated data.

## Milestone P9-4: add the knowledge specialist

The knowledge specialist uses `search_docs` through the tool registry and
validates the returned citation fields as `Evidence`. It compares the
request's words with prior resolution text and steps using Jaccard overlap.
The three sample resolved cases are read from the existing JSON fixture.

```mermaid
flowchart TB
    Query["Ticket text and category"] --> Agent["KnowledgeAgent"]
    Agent --> Registry["ToolRegistry.search_docs"]
    Registry --> Retrieval["Hybrid knowledge retrieval"]
    Retrieval --> Cited["Evidence: title, source, snippet, score, URL"]
    Query --> Similarity["Token-set Jaccard overlap"]
    Cases["previous_resolutions.json"] --> Similarity
    Similarity --> Prior["Ranked PreviousCase results"]
    Cited --> Result["Typed KnowledgeResult"]
    Prior --> Result
```

The similar-case result is a signal for the caller; it is not asserted to be
a guaranteed solution for a new customer.

## Milestone P9-5: add the troubleshooting specialist

The troubleshooter checks the mock status service for categories with a
known service mapping. It asks for structured probable causes and steps,
then adds category-specific playbook checks. Step numbers are assigned
deterministically and in order.

```mermaid
flowchart LR
    Issue["Ticket issue and category"] --> Agent["TroubleshootingAgent"]
    Agent --> Status{"Mapped service?"}
    Status -->|yes| Registry["ToolRegistry.check_service_status"]
    Status -->|no| LLM["Structured diagnosis call"]
    Registry --> StatusResult["Service status"]
    StatusResult --> LLM
    Evidence["Cited knowledge snippets"] --> Wrapped["Wrapped as untrusted evidence"]
    Wrapped --> LLM
    Issue --> WrappedIssue["Issue wrapped as untrusted text"]
    WrappedIssue --> LLM
    LLM --> Draft["Probable causes and ordered candidate steps"]
    Draft --> Playbook["Category-specific safety playbook"]
    Playbook --> Diagnosis["Typed Diagnosis with 1-based step numbers"]
```

The mock status can report `unknown`; it does not contact a production
service.

## Milestone P9-6: add the resolution specialist

The specialist requests a structured draft for the summary, customer reply,
and internal notes. It grounds the reply with the supplied numbered steps
and article references. A deterministic planner separately creates
allow-listed update/refund/reset actions from explicit arguments. Refunds
and workspace-setting resets are marked as requiring approval. The agent
does not execute these actions.

```mermaid
flowchart TB
    Context["Classification, diagnosis, ticket, and evidence"] --> DraftCall["Structured ResolutionDraft"]
    DraftCall --> Ground["Append numbered steps and article citations"]
    Ground --> Validate["Customer-output guardrail"]
    Forbidden["Caller-provided forbidden values"] --> Validate
    Validate -->|valid| Reply["Customer reply is available"]
    Validate -->|invalid| Block["Return blank reply and issue codes"]
    Inputs["Explicit ticket/customer/refund/reset arguments"] --> Planner["Deterministic plan_actions"]
    Planner --> Update["Optional internal ticket summary action"]
    Planner --> Refund["Refund action: approval required"]
    Planner --> Reset["Setting reset: approval required"]
    Update --> Plan["ResolutionPlan"]
    Refund --> Plan
    Reset --> Plan
    Reply --> Plan
    Block --> Plan
```

Model output cannot select a tool name or invent action arguments. Execution
will be handled by the later workflow through the shared registry path.

## Milestone P9-7: add the escalation specialist

The escalation specialist checks deterministic policy rules before calling
the LLM. A matched security, data-loss, dispute, deletion, legal, or
Enterprise-outage rule directly returns its named team and reason. Otherwise
the model may recommend escalation; a low-confidence recommendation is
discarded unless severity is high or critical. Recording an accepted
decision is a separate explicit method that calls `create_escalation`
through the registry.

```mermaid
flowchart LR
    Ticket["Ticket text and plan"] --> Policy["matching_escalation_rules"]
    Policy -->|matched| Mandatory["Return policy team and reason; no model override"]
    Policy -->|no match| LLM["Structured gray-area assessment"]
    Severity["Severity level"] --> Confidence["Confidence guard"]
    LLM --> Confidence
    Confidence -->|low confidence + lower severity| Suppress["Do not retain model escalation"]
    Confidence -->|high severity or adequate confidence| Decision["EscalationDecision"]
    Decision -->|explicit caller request| Registry["ToolRegistry.create_escalation"]
```

The caller controls when to record a decision, which avoids an implicit
database write during policy analysis.

## Milestone P9-8: add the evaluation cases

The evaluation file captures 13 demo scenarios with a valid expected
category, including prompt-injection text that must remain classified as
ordinary support data. An offline test checks category coverage and runs
each case through the supervisor rules with the fake provider.

```mermaid
flowchart TB
    Dataset["tests/evaluation/datasets/eval_cases.json"] --> Validate["Validate expected category labels"]
    Validate --> Coverage["Confirm all 10 category labels are represented"]
    Dataset --> Supervisor["SupervisorAgent with FakeLLM"]
    Supervisor --> Compare["Compare category with expected_category"]
    Compare --> Tests["Offline agent test result"]
    Metrics["Threshold metric suite is a later phase"] -. not added here .-> Tests
```

This dataset and test are not a claim that the later evaluation thresholds
have been implemented or reached.

## End-of-Phase-9 design

```mermaid
flowchart LR
    Ticket["Ticket input"] --> Supervisor["Supervisor"]
    Ticket --> Customer["Customer context"]
    Ticket --> Knowledge["Knowledge and prior cases"]
    Knowledge --> Troubleshooting["Diagnosis and safe playbook"]
    Supervisor --> Resolution["Grounded reply and deterministic plan"]
    Customer --> Resolution
    Troubleshooting --> Resolution
    Ticket --> Escalation["Policy-first escalation"]
    Supervisor -. schemas .-> WorkflowModels["Pydantic workflow contracts"]
    Customer -. schemas .-> WorkflowModels
    Knowledge -. schemas .-> WorkflowModels
    Troubleshooting -. schemas .-> WorkflowModels
    Resolution -. schemas .-> WorkflowModels
    Escalation -. schemas .-> WorkflowModels
    Structured["call_structured + fake / configured provider"] -. model requests .-> Supervisor
    Structured -. model requests .-> Troubleshooting
    Structured -. model requests .-> Resolution
    Structured -. model requests .-> Escalation
    Tools["Existing ToolRegistry"] --> Customer
    Tools --> Knowledge
    Tools --> Troubleshooting
    Tools --> Escalation
    NotYet["LangGraph orchestration and API integration are later work"]
```

## Design choices and trade-offs

| Concern | Phase 9 starting point | Phase 9 end state |
|---|---|---|
| Agent outputs | No specialist contracts. | Pydantic output models reject malformed or extra fields. |
| Offline model behavior | No fake structured provider. | Deterministic fake model supports defaults and scenario-specific responses. |
| Category/severity policy | Rule helpers existed without supervisor call sites. | Supervisor applies category and severity rules around model judgment. |
| Customer data reads | Tools and memory existed without an agent composition layer. | Customer agent aggregates registry reads and same-customer memory. |
| Knowledge history | Search existed without a case-similarity specialist. | Cited article results plus deterministic Jaccard case ranking. |
| Resolution actions | Safe tools existed without a deterministic proposal layer. | Tool names and approval flags derive from explicit inputs, not model output. |
| Escalation | Rules existed without an agent decision contract. | Policy matches win; gray-area model decisions have a confidence guard. |
| Runtime wiring | No LangGraph. | Specialists are tested components; graph wiring remains future work. |

## Boundaries and next steps

- Specialist agents never write SQL directly. They use tools or the memory
  facade backed by repositories.
- Tool errors are surfaced; there is no success-shaped fallback for failed
  reads or escalation recording.
- `call_structured` supports the fake provider offline. A configured real
  provider additionally requires its LangChain provider package and API key.
- Resolution actions are proposals. Approval and execution routing belong to
  the later workflow/approval phases.
- Evaluation cases are in place, but classification/retrieval/escalation
  threshold evaluation is later work.
- The workflow graph phase should call these agents, persist their outputs,
  trace tool/model calls, and define retry and error routing.

## Related files

- [Phase 9 codebase explanation](../explain_codebase/phase9_explained.md)
- [Phase 9 infrastructure and wiring](../Infra_design_evolution/Phase9_Infra_design_evolution.md)
- [Phase 9 interview Q&A](../QnA/Phase9_Interview_QnA.md)
- [Specialist implementations](../../agents/specialists/)
- [Workflow schemas](../../backend/app/schemas/workflow.py)
- [Structured LLM helper](../../backend/app/core/llm.py)
- [Evaluation dataset](../../tests/evaluation/datasets/eval_cases.json)
- [Phase 9 tests](../../tests/agents/)
- [Task tracker](../../TASKS.md)
