# Phase 12 - Console Shell: Interview Questions and Answers

These questions follow Phase 12 in `TASKS.md`: P12-1 through P12-4. This
phase delivers the authenticated console shell and read-only list pages.
Ticket workflow actions are a later phase.

## Goals and overall design

### 1. What was the goal of Phase 12?

To give support staff a browser-based console for signing in and browsing
existing tickets, customers, knowledge articles, and escalations.

### 2. How would you explain it to a non-technical interviewer?

I built the first support-team workspace. Staff can sign in, see their access
level, and browse the records the backend already manages. In this phase the
pages are read-only, so they cannot accidentally change an account or reply
to a customer.

### 3. What did the project have before this phase?

It already had a FastAPI backend with demo JWT authentication and read
endpoints, but it did not yet have a Next.js web console.

### 4. Which tasks make up this phase?

P12-1 adds the Next.js shell and navigation. P12-2 adds the typed API client.
P12-3 connects demo login and role-aware layout. P12-4 adds the read-only
list pages.

### 5. What can a user see in the console?

The overview, ticket list, customer list, published knowledge list, and
escalation list. The header shows the authenticated profile and role.

### 6. What is deliberately not in scope?

Ticket detail actions, workflow progress, approve/reject, reply, escalation
creation, editing, a Docker stack, and cloud deployment.

## Frontend structure and API client

### 7. Why use Next.js App Router?

It provides a standard route and layout structure for the console, while
letting related pages share the same shell and frontend build setup.

### 8. Why have one API client file?

It centralizes URL construction, bearer headers, pagination query strings,
request IDs, and error handling. Pages do not each implement their own
network rules.

### 9. Where are the API types defined?

`frontend/lib/types.ts` contains the response types used by the frontend. The
types follow the actual backend Pydantic models and the API contract for the
routes this phase calls.

### 10. Do TypeScript types validate API responses at runtime?

No. TypeScript catches mistakes while developing the frontend but does not
inspect a JSON response at runtime. The FastAPI Pydantic models are the
server-side validation boundary. Runtime frontend schema validation could be
added later if needed.

### 11. Which endpoints do the read pages call?

`GET /api/v1/tickets`, `/customers`, `/knowledge`, and `/escalations`. Login
uses `POST /api/v1/auth/login`, and session restoration calls
`GET /api/v1/auth/me`.

### 12. How does pagination work?

The frontend sends `limit` and `offset`. The backend responds with `items`,
`total`, `limit`, and `offset`. Previous and Next buttons request another
bounded page instead of loading every record at once.

### 13. How does the overview get its totals?

The backend has no dashboard summary route yet. The overview asks each
existing list endpoint for one item and uses the endpoint's `total` value.
This keeps the frontend honest about available API capabilities.

### 14. How are API errors shown?

The client uses the backend's `detail` message and includes its
`X-Request-ID` when available. That ID can help correlate a user-visible
failure with backend logs.

### 15. What happens when the backend cannot be reached?

The error is represented as a `NetworkError`. The data hook retries it once
after a short delay, then leaves a visible message and manual retry button.
HTTP errors are shown without pretending that the operation succeeded.

### 16. Why not silently show an empty list after a failure?

An empty list and a failed request mean different things. Showing a clear
error prevents a connection problem from being mistaken for "there are no
records."

## Authentication and authorization

### 17. How does demo login work?

The login form sends one of the seeded demo emails to the existing backend
login route. The backend returns a signed token and profile when demo mode is
enabled.

### 18. Does the demo login use a password?

No. It is intentionally passwordless and restricted to configured demo
accounts in demo mode. It is a local demonstration mechanism, not a
production identity provider.

### 19. What is a bearer token?

It is a signed credential the browser attaches to a protected API request in
the `Authorization: Bearer ...` header. The server verifies it before
allowing access.

### 20. Where does the frontend store the token?

In browser local storage, along with a cached profile for display. This
matches the project's current frontend convention, but local storage can be
read by injected scripts. Production hardening should evaluate secure
HttpOnly cookies and the required CSRF protections.

### 21. Does the cached role grant access?

No. The cached role is only used to present the interface. The backend
validates the JWT and enforces the required role on each protected route.

### 22. How does the app restore a login after a page refresh?

The auth provider reads the stored token and asks `/auth/me` for the current
profile. The cached profile can keep the shell understandable during a
temporary connection issue, but it does not replace server-side checks.

### 23. What happens if a token is expired?

The API client clears the token and cached profile, then sends the browser to
the login page with an expired-session notice.

### 24. What is role-aware about the layout?

The signed-in role is displayed. Viewers get an explicit read-only indicator
and message. There are no write actions on the Phase 12 pages; when actions
are later added, the server must still be the authorization authority.

### 25. Can a viewer access data by changing the browser interface?

The interface does not provide write controls in this phase. More generally,
hiding or disabling a control is never security enforcement. The backend
checks the role and returns `403` for a forbidden operation.

## Read-only pages and user experience

### 26. Which ticket data is listed?

Ticket number and subject, status, category, severity, channel, and creation
date. The page uses a subset of the API response suitable for scanning.

### 27. What is shown for an unclassified ticket?

The status-style label displays "Unclassified" for a null category or
severity rather than rendering an empty value.

### 28. Why are there no ticket links yet?

The ticket detail and workflow screen is scheduled for the later UI phase.
This phase intentionally avoids a navigation link that would lead to an
unimplemented detail page.

### 29. What happens when there are no records?

The page shows a specific empty-state message. It does not show a blank table
or an error unless the request actually failed.

### 30. Does the console send replies or issue refunds?

No. Phase 12 only reads records. The project integrations are also mocks;
the Phase 12 UI does not call any write or money-related route.

## Testing and operations

### 31. What frontend tests were added?

Vitest tests cover bearer token and pagination query construction, propagation
of API detail and request IDs, network error reporting, and human-readable
status labels.

### 32. What does the production build validate?

It compiles the Next.js app, checks TypeScript and route generation, and
produces static route output for the console pages.

### 33. Is the API URL a secret?

No. `NEXT_PUBLIC_API_URL` is public browser configuration. It is compiled
into the frontend bundle, so secrets must never be placed in it.

### 34. How does the browser reach the backend locally?

The browser typically loads Next.js from `http://localhost:3000` and calls
FastAPI at `http://localhost:8000`. The backend CORS allow-list must allow
the frontend origin.

### 35. Is the frontend running behind a Next.js API proxy?

No. The browser-side API client calls the configured FastAPI URL directly.
There is no server-side proxy added in this phase.

### 36. Is the frontend containerized?

Not in Phase 12. The frontend builds locally with npm, but a Dockerfile,
Compose wiring, and deployment configuration belong to the later delivery
phase.

### 37. What is the main design trade-off?

The console stays small and reuses the backend API rather than adding a
duplicate data layer or a new dashboard endpoint. The trade-off is that the
overview makes four lightweight count requests and the browser holds a
demo token in local storage.

### 38. What would you improve before production?

Use a production identity provider, evaluate HttpOnly-cookie session
handling, configure API origins per environment, add runtime response
validation if required, and provide a backend dashboard-summary endpoint if
the overview grows.

### 39. How would you summarize Phase 12 in one sentence?

"Phase 12 gives CloudDesk support staff an authenticated, typed, read-only
web console for browsing the records the backend already manages."

## Repository references

- [Phase 12 codebase explanation](../explain_codebase/phase12_explained.md)
- [Phase 12 system design evolution](../design_evolution/Phase12_Project_System_Design_Evolution.md)
- [Phase 12 infrastructure and wiring](../Infra_design_evolution/Phase12_Infra_design_evolution.md)
- [Frontend application](../../frontend/)
- [API client and types](../../frontend/lib/)
- [Backend auth route](../../backend/app/api/auth.py)
- [Backend API contract](../../docs/API_CONTRACT.md)
- [Task tracker](../../TASKS.md)
