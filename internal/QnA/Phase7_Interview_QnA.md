# Phase 7 — Interview Questions and Answers

This Q&A explains the Phase 7 rules and guardrails in plain language. It
distinguishes implemented, tested helpers from the future workflow that will
call them.

## Product and phase overview

### 1. What was the goal of Phase 7?

To create deterministic support policies and reusable checks for risky ticket
text, customer replies, and secrets that might otherwise enter memory.

### 2. How would you explain it to a non-technical person?

I added a dispatcher for sensitive cases, a label that says “this customer
message is information, not an instruction,” a final reply checker, and a
privacy filter that hides recognizable secrets.

### 3. What analogy would you use?

It is like a support office with written routing rules, a secure envelope for
customer statements, a supervisor's final reply checklist, and a document
shredder for secret values before notes are filed.

### 4. What are the Phase 7 tasks?

P7-1 adds category, severity, and escalation rules. P7-2 adds injection
scanning, untrusted-content wrapping, and the security preamble. P7-3 adds
customer-output validation. P7-4 adds secret scrubbing for future memory use.

### 5. Is Phase 7 a complete AI support workflow?

No. It provides tested building blocks. The specialist agents and graph that
will call them belong to later phases.

### 6. Did this phase add a public API route or change ticket behavior?

No. There is no new HTTP route, database write, reply send, or workflow
execution from these helpers in Phase 7.

## Deterministic rules

### 7. Why keep policy rules deterministic instead of asking the model?

Sensitive decisions should be repeatable and testable. A model may help with
unclear cases later, but it should not overrule mandatory policy.

### 8. Which ticket categories can the rule helper return?

It uses the existing `TicketCategory` enum, which contains the ten supported
categories: login, billing, API failure, workspace permissions, storage
quota, integration, feature request, account, security, and other.

### 9. What happens when the category is unclear?

The helper returns no deterministic override. It does not force an uncertain
message into a category; a future structured classifier can decide, with
`other` available as a valid category.

### 10. Can a rule reduce a high or critical severity?

No. A rule may raise the proposed level when a policy requires it. If the
proposed severity is already equal or higher, it is retained.

### 11. What happens when the rule raises severity?

The helper returns the raised severity and a reason. The reason is part of
the result so a future workflow can explain the decision.

### 12. Which cases trigger a named-team escalation?

The policy includes suspected security compromise, possible data loss,
payment disputes, account/data deletion or privacy requests, legal matters,
and broad service outages on Enterprise plans.

### 13. What named teams are used?

`security`, `data_recovery`, `billing`, `privacy_compliance`, `legal`, and
`incident_response`.

### 14. Why does the Enterprise outage rule need a plan name?

The policy is specifically for a broad outage affecting an Enterprise
customer. The caller supplies the plan name; the rule module does not query
customer or subscription data itself.

### 15. What if more than one escalation rule matches?

The helper returns all matching rules in a stable priority order. The first
match is the primary one, while additional matches preserve relevant policy
signals for a future workflow.

## Prompt-injection handling

### 16. What is prompt injection in this application?

It is customer-provided text that tries to make an AI ignore its trusted
instructions, reveal internal information, or perform an unauthorized
action.

### 17. How does the injection scanner work?

It checks for a small set of common instruction-override, prompt-revelation,
tool-command, and bulk-export phrases. It returns a flag; it does not claim
to recognize every possible attack.

### 18. What does `wrap_untrusted` do?

It escapes markup in external text and puts the result between
`<untrusted_content>` tags. This helps the future prompt show a clear
boundary between trusted instructions and customer-provided data.

### 19. Why escape markup before adding the tags?

Without escaping, customer text could contain a closing tag and visually
break out of the intended section. Escaping makes those characters display
as content rather than as markup.

### 20. Does wrapping guarantee that an LLM will ignore malicious text?

No. Prompt boundaries and a preamble are defense-in-depth, not a guarantee.
Tool permissions, deterministic rules, output checks, and human approval
remain necessary.

### 21. What does the security preamble tell a future model?

It says that content inside the untrusted section is data, not instructions,
and forbids following requests there to reveal secrets, access other
customers' information, or perform unauthorized actions.

## Customer-output validation

### 22. What does the output validator check?

It reports empty output, recognized secret formats, local/private service
URLs, explicitly configured internal URLs, and forbidden values supplied by
the caller.

### 23. How are other customers' details detected?

The future caller supplies values that must not appear in the reply. The
validator compares those values without looking up customer records itself.

### 24. What does the validator return?

A typed result with a `valid` flag and reason codes such as
`secret_detected`, `internal_url_detected`, and
`other_customer_data_detected`.

### 25. Does an invalid result automatically block a reply today?

No. The helper only reports the issues. The later workflow must treat the
failure as a stop or risk signal before a reply is shown or sent.

### 26. Can it detect every secret or internal URL?

No. It recognizes common formats, local/private addresses, known internal
hosts, and any extra internal URL strings the caller supplies. New secret
formats or service names may need additional tests and patterns.

## Secret scrubbing and memory

### 27. What does the secret scrubber redact?

It handles labeled passwords and credentials, bearer tokens, common
provider-key formats, JWT-like strings, private-key blocks, and payment-card
numbers that pass the Luhn checksum.

### 28. Why check a card number with Luhn?

The checksum helps distinguish likely payment-card numbers from arbitrary
long digit sequences, reducing accidental redaction of unrelated numeric
identifiers.

### 29. Does secret scrubbing make any text safe to store?

No. It only redacts recognized secrets. Later memory logic must still avoid
raw ticket bodies, unrelated customer information, and unnecessary details.

### 30. Does Phase 7 write to customer memory?

No. It returns scrubbed text for future callers. Memory persistence and its
service/repository path are later work.

## Architecture and testing

### 31. Did Phase 7 add any Docker or network components?

No. All new code runs as ordinary Python functions in the existing backend
process when called. There are no new ports, containers, listeners, or
external connections.

### 32. Does the rules module access the database?

No. It receives text and, when needed, a plan name. Account lookups remain
the responsibility of repositories and future callers.

### 33. How was Phase 7 tested?

Focused offline unit tests cover category matches and ambiguity, named-team
escalation, Enterprise-only outage routing, severity monotonicity,
injection detection and escaped wrapping, output validation, and secret
redaction.

### 34. Why are the tests offline?

The helpers are deterministic and need no external LLM, payment service,
database, or cloud account. Offline tests make policy results repeatable.

### 35. What are the main limitations to acknowledge?

The rules are pattern-based, not a complete language understanding system.
The guardrails are not yet connected to a workflow, and their checks cannot
guarantee detection of every attack or private value.

### 36. What should the next phase do with these helpers?

The agent and workflow phases should call the rules before accepting model
judgment, wrap all external content before prompt assembly, validate
customer-facing output before use, and scrub notes before memory persistence.

### 37. How would you summarize the largest design decision?

“I kept policy outside the model and made each safety check a small,
deterministic helper with an explicit result, so future workflow code can
enforce it and test it independently.”

### 38. How would you summarize Phase 7 in one sentence?

“Phase 7 adds deterministic routing and severity rules, an explicit boundary
for untrusted text, a customer-reply safety check, and secret redaction for
future memory use.”

## Repository references

- [Phase 7 codebase explanation](../explain_codebase/phase7_explained.md)
- [Phase 7 system design evolution](../design_evolution/Phase7_Project_System_Design_Evolution.md)
- [Phase 7 infrastructure and wiring](../Infra_design_evolution/Phase7_Infra_design_evolution.md)
- [Rules and escalation policy](../../agents/rules.py)
- [Prompts](../../agents/prompts.py)
- [Guardrails](../../backend/app/core/guardrails.py)
- [Secret scrubber](../../memory/secret_scrub.py)
- [Phase 7 tests](../../tests/unit/test_rules_guardrails.py)
- [Task tracker](../../TASKS.md)
