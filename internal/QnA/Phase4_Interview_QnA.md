# Phase 4 — Interview Questions and Answers

This question bank covers Phase 4: the support API contract, core ticket
routes, and read-only customer routes. Answers are phrased for a mixed
technical and non-technical interview board. They describe the repository as
implemented and call out later-phase work rather than claiming it is already
live.

## Product and phase overview

### 1. What was the goal of Phase 4?

To define a clear interface for support data and implement the core ticket and
customer HTTP routes on top of the database and authentication foundations
from earlier phases.

### 2. How would you explain Phase 4 to a non-technical person?

I built the support team's secure front desk. It gives approved staff a
consistent way to create or find tickets and view the correct customer's
account details, while checking their access and avoiding unnecessary data
exposure.

### 3. What did Phase 4 consist of?

P4-1 wrote the ticket and customer API contract. P4-2 implemented core ticket
operations. P4-3 implemented read-only customer list and detail operations.

### 4. What changed from Phase 3?

Phase 3 established identity and request protections such as JWT roles,
request IDs, rate limiting, and auditing. Phase 4 used those protections to
make support records accessible through ticket and customer HTTP routes.

### 5. What can you confidently say is implemented?

The ticket router implements create, list, detail, and limited patch
operations. The customer router implements list and detail. The task tracker
marks the three Phase 4 tasks complete, and focused API tests exercise those
routes.

### 6. Does the API contract mean every route listed is already available?

No. The contract is the interface plan for the wider product. Workflow
execution, replies, approvals, escalations, and other listed future operations
are implemented in later tasks or phases; they should not be claimed as
working solely because they appear in the contract.

### 7. Is there a customer-facing chat widget?

No. This product is a support-agent tool, and a customer-facing widget is
outside the Phase 4 scope.

## API contract and route design

### 8. Why write the API contract before building the routes?

It gives frontend and backend work one agreement on paths, fields, roles,
pagination, and errors. That reduces guesswork and helps both sides evolve
without silently breaking each other.

### 9. What is an API in simple terms?

It is a defined way for one program to ask another program to perform an
operation or provide information. Here, clients use HTTP requests and receive
JSON responses from CloudDesk.

### 10. Why use `/api/v1`?

The prefix groups version-one application routes and leaves room to introduce
a different API version later without silently changing existing clients.
Health routes are intentionally outside that prefix.

### 11. What is the difference between `GET`, `POST`, and `PATCH` here?

`GET` reads records, `POST` creates a ticket, and `PATCH` changes only
supported ticket fields. The customer routes are read-only and use `GET`.

### 12. Why return JSON?

JSON is a widely supported structured format. It lets clients reliably
identify fields such as `ticket_number`, `customer_id`, and `status` rather
than interpreting an unstructured paragraph.

### 13. Why have separate list and detail endpoints?

A list endpoint supports search and paging without sending every related
record. A detail endpoint can return the additional information needed for one
selected ticket or customer.

### 14. What does pagination solve?

It limits the amount of data returned in one request. The API uses `limit`
and `offset` and includes `total`, so a client can request results in pages
and show how many records match.

### 15. What does an exact-match filter mean?

It returns records whose email or company name equals the supplied value. It
does not search for partial text.

### 16. Why include a total count with a page?

The total tells a client how many records match the filters across all pages,
not just how many are in the current response.

## Ticket API

### 17. What information is required to create a ticket?

The client provides a subject, customer ID, channel, and initial message body.
An external source ID can optionally be supplied. The server provides the
ticket ID, ticket number, initial status, and timestamps.

### 18. Why does the server generate the ticket number?

It prevents clients from choosing conflicting numbers and keeps ticket
numbering under server control. The human-readable number is separate from
the stable UUID used as the record ID.

### 19. What happens when a new ticket is created?

The route checks that the customer exists, checks for a duplicate
`(channel, external_id)` when an external ID is supplied, creates the ticket,
records the request body as the initial customer message, and commits the
records together.

### 20. Why create the ticket and first message in one transaction?

They represent one customer submission. If part of the operation fails, the
database should not be left with a ticket but no initial message, or vice
versa.

### 21. What prevents a duplicate ticket from an external system?

The route checks whether the pair of channel and external ID already exists.
The database also has a uniqueness constraint. A conflict is returned as
`409 Conflict`.

### 22. Why does the duplicate check have both an application check and a
database constraint?

The application check can give a clear response before attempting a write.
The database constraint remains the final protection if two requests arrive
at nearly the same time.

### 23. What does the ticket list endpoint support?

It supports pagination and exact-match filters for status, category,
severity, channel, and customer ID. Results are ordered newest first with a
stable ID tie-breaker.

### 24. What does ticket detail return?

It returns ticket fields, its messages in creation order, a small customer
summary, and workflow or approval summaries when those related records exist.
It does not return those optional summaries when there is no corresponding
record.

### 25. What can an agent change with `PATCH`?

Only the documented editable fields: status, category, severity,
severity-reason text, and summary. The request cannot change a ticket's
customer, channel, external ID, messages, ID, or timestamps.

### 26. Why reject unknown patch fields?

Rejecting them helps catch client mistakes and prevents a client from
accidentally modifying a field that the API did not intend to expose.

### 27. What is a `409 Conflict` used for in ticket creation?

It indicates that the request conflicts with an existing record, such as a
duplicate external ID or a ticket-number collision, rather than being a
malformed request.

## Customer API and data privacy

### 28. What can a caller do with the customer API?

An authenticated caller can list customers with pagination and optional
exact email/company filters, or retrieve one customer's profile and related
subscription, workspace, and recent-ticket summary.

### 29. Why is the customer API read-only?

Phase 4 needs support staff to look up customer context, but it does not
define a verified customer-edit workflow. Avoiding mutations keeps this
surface narrow until a later task explicitly designs them.

### 30. How much ticket history does customer detail return?

It returns at most the latest 20 ticket summaries. For full paginated history,
the contract points clients to the ticket-list route filtered by customer ID.

### 31. Does customer detail include ticket messages?

No. It returns ticket summaries without messages, keeping the response
bounded and avoiding unnecessary disclosure of conversation content.

### 32. Does customer detail expose customer-memory notes?

No. The route does not query customer memory, and the response schema does
not include it.

### 33. How do you prevent one customer's related records from appearing in
another customer's response?

The detail route passes the requested customer's ID to each related
repository. Tests create records for a second customer and verify they do not
appear in the first customer's response.

### 34. Why use explicit response schemas instead of returning database
objects directly?

The response schema is an allow-list of fields. It prevents extra database
fields from being exposed accidentally and documents what the client can
depend on.

### 35. What happens when a customer or ticket ID does not exist?

The route returns `404 Not Found` with a clear resource-specific detail.

## Authentication and authorization

### 36. How is a protected API request authenticated?

The client sends a bearer JWT. Shared security code validates the token's
signature and required claims, then makes the user's subject and role
available to the route dependency.

### 37. What is the difference between authentication and authorization?

Authentication checks who the caller is. Authorization checks whether that
caller has permission to perform the requested operation.

### 38. Which roles can use the Phase 4 routes?

All three roles can read tickets and customers. The ticket create and patch
routes require at least the agent role. The role hierarchy lets admins inherit
agent capabilities.

### 39. What happens when a request has no token?

The shared authentication dependency rejects it with `401 Unauthorized`.

### 40. What happens when a valid viewer tries to create a ticket?

The role dependency rejects the request with `403 Forbidden`, because a
viewer is below the required agent role.

### 41. Does the customer API let a user create a customer by sending `POST`?

No such customer mutation route is implemented. The customer API in this
phase only exposes `GET` list and detail operations.

## Architecture and implementation

### 42. Why keep routes, schemas, and repositories separate?

Routes handle HTTP, validation, and permissions. Schemas describe accepted
and returned data. Repositories handle database queries. This separation
makes each part easier to test and change without spreading responsibilities
throughout the code.

### 43. What does a repository do?

A repository is the application's database-access component for a group of
records. For example, the ticket repository contains ticket queries and
pagination; the customer route calls it without constructing SQL itself.

### 44. Why use asynchronous database access?

Database operations wait on I/O. Async database calls let the server yield
while waiting rather than blocking its event loop for that wait, which fits
the async FastAPI application.

### 45. Where is the database transaction committed?

The API route controls the transaction boundary for the Phase 4 write
operations. Ticket creation commits the ticket and initial message together;
ticket patch commits after the update. Read-only operations do not commit
changes.

### 46. How are request fields validated?

FastAPI and Pydantic schemas validate types, required values, enum values,
field limits, and unsupported fields before or during handler execution.
Invalid requests return a validation response rather than being written as
valid data.

### 47. How does the API fit with the earlier phases?

It uses the SQLAlchemy entities and repositories from Phase 2 and the JWT,
role, middleware, and request-guard foundation from Phase 3.

### 48. How can request IDs help support or debugging?

Each request has an `X-Request-ID`. A client can share that identifier when
reporting an issue, helping an operator correlate the response with
server-side logs and audit records.

### 49. Are all GET requests audited?

The current audit middleware records non-GET HTTP requests. GET requests are
not written to the audit table by that middleware.

### 50. Is rate limiting implemented in the route handler?

No. Rate limiting is middleware around the application routes, so it can
apply before route-specific logic.

## Testing, errors, and limitations

### 51. How are the routes tested without a cloud database?

The API tests create an isolated in-memory SQLite database, add test profiles
and support records, and override the normal session dependency. They can
exercise HTTP behavior without provisioning cloud services.

### 52. What customer-specific behaviors are tested?

The tests cover filtering, pagination, authentication, a missing-customer
`404`, the 20-ticket limit, and isolation from other customers' subscriptions,
workspaces, tickets, and memory notes.

### 53. What ticket-specific behaviors are tested?

The tests cover ticket creation and its initial message, rejection of a
missing customer, duplicate external IDs, list filters and pagination,
detail responses, and constrained updates.

### 54. What common HTTP errors should a client understand?

`401` means missing or invalid authentication; `403` means insufficient
role; `404` means the requested resource is missing; `409` means a conflict;
`422` means request validation failed; and `429` means the request was
rate-limited.

### 55. Does Phase 4 include Docker networking?

No. The Phase 4 implementation has no Dockerfile or Compose stack. Locally,
the API process can use a SQLite file; SQLite itself is not a network service.

### 56. Is the API deployed to production or connected to a live PostgreSQL
service?

No such deployment is claimed. The code supports a configured database URL
and the repository includes PostgreSQL setup assets, but Phase 4 does not
prove that a cloud service was provisioned or deployed.

### 57. Does Phase 4 send a real email or issue a refund?

No. Those are outside the Phase 4 API implementation; consequential actions
and mock integrations are later work.

### 58. What would you improve or add next?

I would implement the next planned workflow capabilities behind the existing
contract, keeping approval and account-changing actions protected. I would
also continue integration tests as those handlers arrive and add deployment
configuration only in the delivery phase.

### 59. What was an important design decision in this phase?

Treating the API contract as a shared agreement, while keeping HTTP handling,
permission checks, response schemas, and database queries in distinct layers.
That makes the system easier to extend without exposing database internals
or granting broader access than needed.

### 60. How would you summarize Phase 4 in one sentence?

“Phase 4 added a documented, role-protected support API for core ticket
operations and safe, read-only customer context, while leaving AI workflows
and container deployment to later phases.”

## Repository references

- [Phase 4 codebase explanation](../explain_codebase/phase4_explained.md)
- [Phase 4 system design evolution](../design_evolution/Phase4_Project_System_Design_Evolution.md)
- [Phase 4 infrastructure and wiring](../Infra_design_evolution/Phase4_Infra_design_evolution.md)
- [API contract](../../docs/API_CONTRACT.md)
- [Ticket routes and tests](../../backend/app/api/tickets.py) · [tests](../../tests/api/test_tickets.py)
- [Customer routes and tests](../../backend/app/api/customers.py) · [tests](../../tests/api/test_customers.py)
- [Task tracker](../../TASKS.md)
