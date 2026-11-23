# Phase 13 - Ticket Workflow Screen: Interview Questions and Answers

These questions follow Phase 13 in `TASKS.md`: P13-1 through P13-4. The
phase adds the ticket detail workspace, workflow progress, and agent actions
to the Phase 12 support console.

## Goals and system design

### 1. What was the goal of Phase 13?

To let support staff open a ticket, understand its history, follow the
automated investigation, and take the next action from one screen.

### 2. How would you explain this phase to a non-technical interviewer?

I made a shared case file for support agents. It shows the customer's
conversation and account context alongside the computer's investigation.
The computer can propose a response, but a person remains in control of
approval and escalation. The demo records actions but does not send real
email or move money.

### 3. What did the project have before Phase 13?

It had a signed-in console with read-only ticket, customer, knowledge, and
escalation lists, plus backend workflow and approval services. There was no
ticket detail screen or browser workflow action panel.

### 4. Which tasks make up this phase?

P13-1 builds ticket details. P13-2 shows and polls workflow progress. P13-3
adds approval, rejection, reply, request-information, and escalation
controls. P13-4 adds focused frontend tests.

### 5. What can an agent do from the ticket page?

Review messages and customer facts, run the workflow, see progress and
evidence, approve or reject a pending action, record a reply or request for
information, and escalate the case to a named team.

### 6. What remains out of scope?

Real email delivery, real refunds, real external team notifications,
containerization, cloud deployment, and a customer-facing chat widget.

## Ticket detail and frontend structure

### 7. How is the detail page reached?

The ticket number in the ticket list links to the dynamic route
`/tickets/{id}`. The ID is used to fetch the ticket detail from FastAPI.

### 8. What does the detail endpoint return?

It returns ticket fields, ordered messages, a customer summary, and the
latest workflow and approval summaries when present.

### 9. Why show the conversation and customer details together?

The agent can understand the request and its context without switching
between separate pages. It reduces navigation while keeping the information
grouped into clear areas.

### 10. Why keep API calls in one client module?

The shared client centralizes URL construction, bearer-token headers, error
handling, and typed requests. The page focuses on presentation and user
actions rather than reimplementing HTTP behavior.

### 11. Where are ticket and workflow data shapes declared?

In `frontend/lib/types.ts`. They describe the JSON shapes returned by the
backend. The backend Pydantic response models remain the authoritative
runtime contract.

### 12. Do TypeScript types validate API JSON at runtime?

No. TypeScript catches frontend development mistakes but does not validate
the JSON received at runtime. FastAPI's Pydantic models validate and
serialize the server responses.

## Workflow progress and polling

### 13. How does the agent start a workflow?

The browser calls `POST /api/v1/tickets/{id}/run`. The backend creates a
workflow run and starts the graph using its existing workflow service.

### 14. How does the page learn about progress?

It requests `GET /api/v1/tickets/{id}/workflow` every two seconds while the
run is queued or running. It stops polling when the workflow pauses or
reaches a terminal state.

### 15. Why use polling instead of a websocket?

Polling is simple, matches the existing API, and is sufficient for a
support screen with modest update frequency. A websocket or server-sent
events connection could be considered if scale or latency requirements
change.

### 16. What happens when polling fails?

The screen surfaces the error and offers a retry. It does not claim the
workflow succeeded or substitute an empty result.

### 17. How are workflow steps matched to backend progress?

The frontend has one list of labels mapped to backend node IDs. The
`completed_nodes`, `current_node`, and workflow status determine whether
each step is completed, active, pending, or conditionally skipped.

### 18. Why can a step be skipped?

Some graph paths are conditional. For example, a low-risk request may go
straight to resolution without human approval or escalation. A skipped
conditional step is different from a step that is still pending.

### 19. What happens if a workflow pauses for approval?

The backend marks the workflow paused and the ticket waiting on approval.
The page stops polling, shows the pending approval, and lets an eligible
agent decide. The backend records the decision and resumes the saved graph.

### 20. What workflow details are visible?

The page can show status, category, severity and its reason, a summary,
probable causes, numbered troubleshooting steps, cited knowledge evidence,
token counts in the API shape, and a customer reply preview when it passed
output validation.

### 21. Does the page show a reply draft that failed safety checks?

No. It displays that the suggested reply was withheld instead of rendering
the rejected customer-facing text.

## Actions, permissions, and safety

### 22. Who can take actions?

Agents and administrators. Viewers can inspect the ticket, but their action
controls are disabled.

### 23. Is disabling a button sufficient security?

No. Browser controls are only a user-experience cue. The backend verifies
the signed JWT and role on each write request and returns `403` when access
is insufficient.

### 24. When are approve and reject buttons shown?

Only when the ticket detail includes an approval with status `pending`.
Once a decision is recorded, the pending controls are no longer shown.

### 25. Does clicking Approve directly issue a refund?

No. The browser calls the approval endpoint. The backend records the
decision and resumes the paused workflow through the same policy-controlled
tool path. The demo billing integration does not move money.

### 26. What happens when an agent rejects an approval?

The backend records the rejection and resumes the workflow through its safe
rejection path, which creates an escalation rather than executing the
rejected action.

### 27. What does Send reply do in this phase?

It records a public agent message on the ticket after safety checks. It is a
demo action and does not send an email to a real customer.

### 28. What checks are made before a reply is recorded?

The backend checks for known secret patterns, internal URLs, and contact
details associated with other customers. Invalid output is rejected with a
validation error and is not stored as a public reply.

### 29. How is Request information different from Send reply?

Both record a public agent message, but requesting information also changes
the ticket status to `waiting_on_customer`.

### 30. How does manual escalation work?

An agent supplies a named team and a reason. The backend records an
escalation, links the latest workflow when available, and changes the ticket
status to `escalated`. It does not notify a real external team.

### 31. Are user-entered messages rendered as HTML?

No. React renders the message body as text. It is not treated as executable
markup.

### 32. Where are writes audited?

The existing audit middleware records non-GET requests. The API also
requires an authenticated agent role for these actions.

## API and backend changes

### 33. Why were backend routes added as part of a frontend phase?

The API contract described reply, request-information, and manual
escalation routes, but those routes were missing from the backend. Adding
the matching endpoints was necessary so the requested UI actions work
instead of failing when clicked.

### 34. Which backend routes support the screen?

Ticket detail and workflow routes, workflow start, approval approve/reject,
and ticket reply, request-info, and escalation routes.

### 35. How are request and response shapes kept aligned?

The API contract documents the route payloads, Pydantic models validate
backend input/output, and TypeScript interfaces describe frontend responses.
The contract was updated alongside the new backend request models.

### 36. Which layers own the action logic?

The API validates/authenticates HTTP requests. `TicketActionService`
coordinates ticket/message/escalation repositories and output validation.
Repositories persist SQL records. The workflow service continues to own
graph runs and approval resume behavior.

### 37. Does manual escalation use an LLM?

No. An agent chooses a team and gives a reason. The API records that choice.
Automated policy escalation remains part of the backend workflow and its
deterministic rules.

## Testing and operations

### 38. What frontend behavior is tested?

Tests check completed, active, and skipped workflow steps; disabled
controls for viewers; reply submission; and the API method, path, and body
used by action requests.

### 39. What backend behavior is tested?

API tests check that replies and requests are recorded, customer-output
violations are rejected, request-info changes the status, escalation is
persisted, missing tickets return `404`, invalid requests return `422`, and
viewers cannot perform writes.

### 40. What does the frontend build verify?

It compiles the Next.js routes and TypeScript, including the dynamic ticket
detail route and its shared components.

### 41. Does the browser connect directly to the database?

No. The browser calls FastAPI. The backend uses repositories to read or
write the configured database.

### 42. Is the frontend behind an API proxy?

No. The browser calls the configured FastAPI base URL directly, so the
backend CORS configuration must allow the frontend origin.

### 43. Does Phase 13 add a Docker network?

No. It adds frontend and API code, not Dockerfiles, Compose services, or
container networking.

### 44. What is the main design trade-off?

Polling is straightforward and reliable with the existing HTTP API, but it
creates periodic requests. A push-based connection could reduce repeated
requests if the product later needs more real-time updates.

### 45. What would you improve before production?

Integrate a real communication provider with delivery tracking, add
appropriate operational alerting and retry policy, review identity/session
hardening, and consider push-based workflow updates if polling becomes
costly.

### 46. How would you summarize Phase 13 in one sentence?

"Phase 13 gives support agents one place to review a case, follow its
automated investigation, and make safe, auditable decisions."

## Repository references

- [Phase 13 codebase explanation](../explain_codebase/phase13_explained.md)
- [Phase 13 system design evolution](../design_evolution/Phase13_Project_System_Design_Evolution.md)
- [Phase 13 infrastructure and wiring](../Infra_design_evolution/Phase13_Infra_design_evolution.md)
- [Ticket detail page](<../../frontend/app/(console)/tickets/[id]/page.tsx>)
- [Ticket action controls](../../frontend/components/tickets/ticket-actions.tsx)
- [Workflow step definitions](../../frontend/lib/workflow-steps.ts)
- [Frontend API client](../../frontend/lib/api.ts)
- [Ticket API routes](../../backend/app/api/tickets.py)
- [Ticket action service](../../backend/app/services/ticket_actions.py)
- [API contract](../../docs/API_CONTRACT.md)
- [Ticket API tests](../../tests/api/test_tickets.py)
- [Task tracker](../../TASKS.md)
