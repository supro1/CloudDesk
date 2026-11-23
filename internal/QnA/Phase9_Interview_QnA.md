# Phase 9 - Specialist Agent Interview Questions and Answers

This Q&A explains the Specialist Agents phase in the `TASKS.md` tracker.
The canonical phase plan calls this work Phase 8. The components are
implemented and tested, but they are not yet wired into the workflow graph.

## Phase overview and architecture

### 1. What was the goal of Phase 9?

To turn the existing policies, data tools, knowledge search, and memory
helpers into six focused support specialists with validated results.

### 2. How would you explain the phase to a non-technical interviewer?

I organized support work into a supervisor, customer researcher, knowledge
researcher, troubleshooter, resolution writer, and escalation specialist.
Each one has a clear job, and safety rules remain in charge of sensitive
decisions.

### 3. What are the eight tasks?

P9-1 creates workflow schemas and a fake LLM. P9-2 through P9-7 create the
six specialists. P9-8 adds a category evaluation dataset.

### 4. Is this a complete working workflow?

No. The specialists can be run and tested individually. The next phase
connects them in a LangGraph workflow and persists node progress.

### 5. Why split the work into specialist agents?

It gives each component a narrow responsibility. A customer lookup does not
need to classify a ticket, and a resolution writer does not need permission
to decide which tools exist.

### 6. How do specialists exchange information?

They return Pydantic models such as `Classification`, `CustomerContext`,
`Evidence`, `Diagnosis`, `ResolutionPlan`, and `EscalationDecision`.

### 7. Why use structured output instead of free-form text?

Typed models validate required fields and allowed values before later code
uses the result. A malformed response produces an error instead of being
silently interpreted as a valid decision.

## Schemas and LLM provider

### 8. What does `call_structured` do?

It calls the selected provider for a particular Pydantic schema, validates
the returned object, and reports elapsed time and token usage. It makes one
bounded retry by default when schema validation fails.

### 9. What is `FakeLLM`?

It is a local deterministic provider for offline tests and demos. It can
return defaults or test-specific responses without an API key or network
connection.

### 10. Does the fake provider behave like a real model?

No. It proves that the call path, schema validation, retry behavior, and
agent logic work. It does not prove the quality of a production model.

### 11. Can the application use a real provider?

The helper uses LangChain's provider initialization and structured-output
interface when settings select a non-fake provider. That environment also
needs the matching provider package and API key.

### 12. What happens when a schema rejects model output?

`call_structured` retries once by default with a correction instruction.
If the next response is still invalid, the validation error is raised to the
caller.

### 13. Are prompts or API keys written to logs?

This phase does not log prompt text or API keys. The fake provider retains
its calls only on its in-memory test instance so tests can inspect wrapping;
it does not expose them through an API.

### 14. How is token usage measured for the fake provider?

The fake provider estimates tokens from prompt and output character counts
so the interface can be tested. Its estimated cost is explicitly zero.

### 15. Is real-provider cost accurate in this phase?

No. Provider token usage metadata is captured when available, but a real
cost estimate needs provider-specific pricing configuration and is outside
this phase.

## Supervisor and policy

### 16. How does the supervisor classify a ticket?

It requests a structured category and summary. If deterministic category
rules clearly match, that result overrides the model's category.

### 17. How is prompt injection handled?

The subject and body are escaped and wrapped as untrusted content before a
model call. A scanner separately flags common attempts to override
instructions or request unauthorized data.

### 18. Does wrapping guarantee that a model ignores malicious text?

No. It marks a clear boundary but is not a complete security control. Tool
allow-lists, deterministic rules, output validation, and human approval
remain necessary.

### 19. Can the severity rules lower a model's severity?

No. The supervisor keeps the higher proposed or model severity, and
deterministic policy may raise it further.

### 20. Does the supervisor change the ticket in the database?

No. It returns typed classification and severity results for a future
workflow node to persist.

## Customer and knowledge specialists

### 21. How does the customer specialist load context?

It calls `get_customer`, `get_subscription`, and `get_ticket_history`
through `ToolRegistry`, then recalls up to ten notes through
`LongTermMemory`.

### 22. Does the customer specialist call an LLM?

No. It combines read results into `CustomerContext` without asking a model
to interpret database facts.

### 23. What happens if a customer record is missing?

The customer field is `None`; empty subscription, history, and memory lists
remain explicit empty context. A tool execution failure instead raises an
error.

### 24. How does the knowledge specialist find evidence?

It calls the existing `search_docs` tool and validates each result as
`Evidence`, including its title, source, snippet, score, and URL.

### 25. How are similar resolved cases found?

The agent compares normalized word sets from the query and each case's
resolution and steps. Jaccard similarity is the overlap divided by the
union; the highest scoring cases are returned first.

### 26. Where do prior resolved examples come from?

By default, the agent reads `sample_data/previous_resolutions.json`. Tests
can also provide their own case list.

### 27. Is Jaccard similarity semantic search?

No. It is an inexpensive deterministic word-overlap heuristic. It is easy
to test, but synonyms and paraphrases may be missed.

## Troubleshooting and resolution

### 28. What does the troubleshooter combine?

It combines a structured diagnosis, relevant article evidence, service
status from the existing mock tool where applicable, and a category-specific
playbook.

### 29. Are troubleshooting steps numbered?

Yes. The agent creates contiguous one-based numbers after combining model
steps and playbook checks.

### 30. Does the troubleshooter call production status systems?

No. It calls the existing `check_service_status` registry tool, which uses
the mock service-status integration in this project.

### 31. How does the resolution agent ground a reply?

It appends the provided numbered diagnosis steps and article references to
the draft. If the final reply has a recognized secret, internal URL, or
caller-provided forbidden value, the plan returns a blank customer reply
and the issue codes.

### 32. Does the resolution agent execute refunds or workspace changes?

No. It creates deterministic `PlannedAction` objects. Refunds and setting
resets are marked approval-required, and a later workflow decides how to
execute them through `ToolRegistry`.

### 33. How are actions kept deterministic?

The model schema for the draft has no tool-action field. The `plan_actions`
function uses explicit ticket, customer, amount, and workspace inputs to
create allow-listed actions.

### 34. What if a refund amount is invalid or missing IDs?

The action planner rejects invalid or non-positive amounts and requires
both ticket and customer IDs before creating a refund request action.

## Escalation

### 35. How does the escalation specialist make its decision?

It checks `matching_escalation_rules` first. A policy match returns the
named team and reason immediately, without asking the model. The model is
used only when no mandatory rule matches.

### 36. Which cases have deterministic escalation rules?

The rules cover suspected security compromise, data loss, payment disputes,
account/data deletion, legal matters, and broad Enterprise outages.

### 37. Why suppress low-confidence model escalations?

To avoid acting on a vague model suggestion. A low-confidence escalation is
discarded for lower severity, while high- or critical-severity cases retain
the escalation recommendation for review.

### 38. Does `run()` write an escalation record?

No. It returns the decision. A separate explicit `record_escalation()`
method uses the allow-listed `create_escalation` tool when the caller
chooses to record it.

## Evaluation and validation

### 39. What is in the evaluation dataset?

Thirteen demo scenarios with `expected_category` labels, covering every
supported category. The dataset includes the instruction-like export
request, which remains in the `other` category and is separately flagged as
untrusted.

### 40. Does the dataset prove that evaluation thresholds are met?

No. It is a case fixture and a focused offline classification check. The
threshold-based evaluation suite belongs to the later evaluation phase.

### 41. What tests were added?

They cover schemas, structured fake output and retries, each specialist's
main behavior, action approval flags, prompt wrapping, and evaluation
category coverage.

### 42. Why use mock tools in specialist tests?

The tests can verify tool arguments and returned context without Docker,
live Redis, external model credentials, or real integrations.

### 43. What are the main limitations?

Pattern rules and word-overlap similarity are heuristics. The fake LLM does
not assess language quality. Output checks recognize known patterns rather
than every possible secret, and the graph still needs to enforce workflow
ordering, persistence, approval, and tracing.

### 44. What is the next engineering step?

Build the LangGraph state and nodes, call the specialists in the correct
order, persist partial state and trace events, and ensure the graph executes
only the actions permitted by the registry and approval decisions.

### 45. How would you summarize the largest design decision?

“I kept each agent narrow, validated every handoff with a schema, and kept
mandatory policy and action planning outside the model.”

### 46. How would you summarize Phase 9 in one sentence?

“Phase 9 creates six typed support specialists that can be tested offline,
with deterministic policies and approval-aware action plans.”

## Repository references

- [Phase 9 codebase explanation](../explain_codebase/phase9_explained.md)
- [Phase 9 system design evolution](../design_evolution/Phase9_Project_System_Design_Evolution.md)
- [Phase 9 infrastructure and wiring](../Infra_design_evolution/Phase9_Infra_design_evolution.md)
- [Workflow schemas](../../backend/app/schemas/workflow.py)
- [Structured LLM helper](../../backend/app/core/llm.py)
- [Specialist agents](../../agents/specialists/)
- [Evaluation dataset](../../tests/evaluation/datasets/eval_cases.json)
- [Agent tests](../../tests/agents/)
- [Task tracker](../../TASKS.md)
