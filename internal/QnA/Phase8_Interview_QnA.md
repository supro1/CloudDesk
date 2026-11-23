# Phase 8 - Interview Questions and Answers

This Q&A covers the memory features in the execution tracker Phase 8. In the
canonical `PLAN_PHASE.md` this work is called Phase 11; the task tracker
intentionally schedules it earlier.

## Product and phase overview

### 1. What was the goal of Phase 8?

To add temporary memory for an active ticket or workflow and safe, durable
notes that can help CloudDesk support the same customer in the future.

### 2. How would you explain the feature to a non-technical person?

It is like giving the support desk a scratchpad that gets cleaned each day
and a carefully edited customer history that keeps only useful, safe notes.

### 3. What tasks are included?

P8-1 adds an expiring Redis facade. P8-2 adds durable customer-memory access
on the existing SQL table. P8-3 combines recall and safe resolution recording.

### 4. Why use two kinds of memory?

The active conversation and workflow state are temporary working information.
A small resolution note may remain useful across future tickets. Keeping them
separate gives each kind of data a retention period that matches its purpose.

### 5. Is the memory feature connected to a complete AI workflow now?

The storage facades and service behavior are implemented and tested. The
specialist agents and graph nodes that call them are later work, so I do not
claim that a ticket run automatically recalls or writes memory yet.

## Short-term memory

### 6. What is short-term memory used for?

It can keep a ticket conversation, a workflow's current state, and recently
retrieved knowledge results while processing is underway.

### 7. Why Redis?

Redis is well suited to quick reads and values that expire automatically. It
was already part of the application for rate limiting, so this phase reuses
the configured client instead of adding another service.

### 8. What expires and when?

Ticket conversations and workflow state expire after 24 hours. Retrieval
cache entries expire after five minutes.

### 9. How is a retrieval result keyed?

By mode, category, top-k count, and query:
`rag:{mode}:{category}:{top_k}:{query}`. Different retrieval settings
therefore do not accidentally reuse the same result.

### 10. How does offline testing work?

The facade accepts a Redis client, so tests can pass fakeredis. Tests do not
need a Docker container or a live Redis server.

### 11. Does the facade hide Redis failures?

No. Redis command errors propagate. Invalid JSON or data with the wrong
shape raises an explicit error instead of being silently treated as an empty
conversation or workflow state.

### 12. Why store these values as JSON?

It provides a consistent representation for Python dictionaries and lists
and works with both Redis and fakeredis. It also makes the expected shapes
explicit at the facade methods.

## Long-term customer memory

### 13. Where are long-term notes stored?

In the existing `customer_memory` SQL table, through
`CustomerMemoryRepository`. This phase does not add a new table or issue SQL
from the memory package.

### 14. Which note types are allowed?

`preference`, `past_issue`, `troubleshooting`, and `note`. Other types are
rejected.

### 15. How do you keep one customer's information separate?

Every list and duplicate lookup includes the customer ID. A note for one
customer cannot be returned as the other customer's history through this
repository path.

### 16. How many notes are recalled?

The service defaults to ten and caps larger requested limits at ten.

### 17. How are duplicates handled?

Before writing, the service searches for the same customer, note type, and
exact cleaned content. If it finds one, it returns the existing record
instead of inserting another.

### 18. Is duplicate suppression safe under simultaneous writes?

It prevents duplicates in the normal sequential service path. The current
schema has no unique constraint for the text contents, so it is not a
cross-process concurrency guarantee.

### 19. Who commits the SQL transaction?

The caller that owns the `AsyncSession`. The memory service flushes through
the repository but does not commit or roll back a transaction it does not
own.

## Privacy and resolution recording

### 20. What does the resolution recorder save?

A short past-issue summary, up to the first three troubleshooting steps, and
a short resolution note.

### 21. Is the original ticket body stored?

No. It is passed as comparison input only. If a candidate note contains the
full body, the service rejects the write.

### 22. How are recognizable secrets handled?

Each note passes through the existing secret scrubber before storage.
Recognized passwords, tokens, keys, private-key blocks, and likely payment
card numbers have their values replaced with `[REDACTED]`.

### 23. Does scrubbing make all text safe?

No. It recognizes known patterns only. The service also checks the ticket
body and caller-designated prohibited values. It cannot infer every private
value or find unrelated customer data unless the caller supplies the values
that must be excluded.

### 24. What happens when unsafe content is found?

The service raises an explicit `ValueError` before it begins inserting the
prepared notes. The caller can handle the failure, and it is not reported as
a successful memory write.

### 25. Can I store arbitrary ticket text using `record_note`?

Ticket-sourced writes require both a source ticket ID and the ticket body
used for filtering. The resolution method is the intended route for storing
ticket outcomes. Callers must still provide prohibited values for other
customer data they know should not be retained.

### 26. Why store the source ticket ID if not the body?

The ID gives a safe reference back to the source ticket without copying its
full message into permanent memory.

## Design and testing

### 27. Did Phase 8 add a public endpoint?

No. These are internal Python facades. They are not HTTP routes and are not
directly exposed to customers.

### 28. Did Phase 8 change the database schema?

No. The customer-memory model and table already existed. The change adds a
repository query and service behavior on top of them.

### 29. Did Phase 8 add a Redis container or Docker wiring?

No. The application already had a Redis client factory. The phase reuses
that client and adds no container, port, or network.

### 30. How was customer isolation tested?

The focused tests record the same text for two separate customer IDs and
verify that each customer's recall returns only its own record.

### 31. Which important edge cases are tested?

The tests cover expiration values, missing and malformed Redis entries,
duplicate suppression, secret redaction, disallowed note types, recall
limits, per-customer isolation, ticket-body rejection, prohibited values,
and the three-step limit.

### 32. Why test with an in-memory SQL database?

It exercises the actual SQLAlchemy model and repository behavior while
keeping tests deterministic and offline.

### 33. Is the Redis cache the source of truth for customer history?

No. Redis holds temporary values and a short-lived retrieval cache. The SQL
table is the durable store for customer notes.

### 34. What is the main trade-off in this design?

The facades keep storage details and safety checks in one place, but they
cannot know all business context on their own. The future workflow must pass
the correct customer ID, ticket body, and known prohibited values.

### 35. What would be the next step?

When the agent and workflow graph are implemented, connect customer-context
loading to `recall_customer()` and the completed-resolution path to
`record_resolution()`, then add graph-level tests for those call sites.

### 36. How would you summarize the largest design decision?

“I separated temporary runtime data from durable customer notes and put
expiry, customer scoping, de-duplication, and privacy checks behind explicit
memory facades.”

### 37. How would you summarize Phase 8 in one sentence?

“Phase 8 adds a temporary Redis scratchpad and a customer-scoped SQL history
that is limited, deduplicated, scrubbed, and checked before it is saved.”

## Repository references

- [Phase 8 codebase explanation](../explain_codebase/phase8_explained.md)
- [Phase 8 system design evolution](../design_evolution/Phase8_Project_System_Design_Evolution.md)
- [Phase 8 infrastructure and wiring](../Infra_design_evolution/Phase8_Infra_design_evolution.md)
- [Short-term memory facade](../../memory/short_term.py)
- [Long-term memory facade](../../memory/long_term.py)
- [Customer-memory repository](../../backend/app/repositories/workflow.py)
- [Phase 8 tests](../../tests/unit/test_memory.py)
- [Task tracker](../../TASKS.md)
