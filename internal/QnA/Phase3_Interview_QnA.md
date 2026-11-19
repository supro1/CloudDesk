# Phase 3 — Interview Questions and Answers

This question bank covers Phase 3: JWT identity, role-based access, demo
tokens, Redis rate limiting, audit logging, and middleware ordering. The
answers are written for a mixed technical and non-technical interview board
and distinguish demo behavior from production-ready identity infrastructure.

## Product and phase overview

### 1. What was the goal of Phase 3?

To give CloudDesk shared ways to identify callers, check their support roles,
limit excessive request volume, and record state-changing HTTP requests.

### 2. How would you explain Phase 3 to a non-technical person?

I added a badge check, a traffic counter, and an activity log around the
application. The badge check decides who is calling and what they may do. The
traffic counter prevents one source from overwhelming the service. The log
helps the team investigate important actions.

### 3. What tasks are included in Phase 3?

P3-1 adds JWT verification and reusable role checks. P3-2 adds demo login
and tokens. P3-3 adds Redis-backed rate limiting. P3-4 adds audit middleware
and defines middleware order.

### 4. What changed from Phase 2?

Phase 2 built the data and persistence foundation. Phase 3 added identity
and request protections around that application so later routes can use
consistent authentication and authorization.

### 5. What can you confidently claim is complete?

All four Phase 3 task rows are marked complete. The code includes the shared
JWT and role dependency, demo auth endpoints, rate-limit middleware, audit
middleware, and tests for each of those behaviors.

### 6. Is Phase 3 the same as production authentication?

No. The login endpoint is explicitly a demo flow. It issues a token for an
allow-listed demo profile without verifying a password. It is not a
production password or identity-provider integration.

## JWT and authentication

### 7. What is a JWT?

A JWT is a signed token that carries claims about a user, such as a stable
subject ID, role, and expiration time. The server verifies its signature
before trusting those claims.

### 8. Why use a signed token?

The signature lets the server detect whether token contents were changed
after issuance. A valid signature does not encrypt the token, so secrets
should not be placed in its claims.

### 9. What is a bearer token?

It is a token presented by the caller in an HTTP `Authorization` header. The
server treats possession of a valid token as proof of the token's identity
claims, so it must be protected in transit and storage.

### 10. What algorithm does this implementation accept?

The verifier accepts HS256 and uses the configured effective JWT secret,
which prefers the Supabase JWT secret when set and otherwise uses the
application JWT secret.

### 11. Which claims are required by the verifier?

The verifier requires a subject (`sub`) and expiration (`exp`). It also
requires a supported role to build the authenticated-user object.

### 12. How does the verifier determine the role?

It first checks `app_metadata.role`, then `user_role`, and then `role`. The
result must be one of `viewer`, `agent`, or `admin`.

### 13. What happens when the bearer token is missing or invalid?

The request is rejected with `401 Unauthorized` and a bearer authentication
challenge.

### 14. Does the security dependency query the profile database for every
request?

No. General token verification trusts valid signed claims. The `/me` route
specifically looks up the profile and confirms it exists and is active.

### 15. What happens when the JWT signing secret is not configured?

Protected-route verification and demo-token issuance return a service
configuration error (`503`) rather than pretending authentication succeeded.

### 16. How long do demo tokens last?

Eight hours. The response includes the token lifetime in seconds and the JWT
contains issue and expiration times.

### 17. Can an issued token be revoked immediately?

Phase 3 does not implement a token revocation list. A signed token remains
valid until expiration unless the route performs an additional profile check,
as `/me` does. This is one limitation to address when choosing a production
identity and revocation strategy.

## Demo login and profile

### 18. How does demo login work?

The route checks that demo mode is on and a signing secret exists, confirms
the email is on the demo allow-list, then finds an active matching profile
with a supported role. It signs and returns an eight-hour token.

### 19. Why is demo login restricted to a fixed list?

It keeps local demonstration access limited to the intended seeded demo
identities rather than issuing tokens to arbitrary email addresses.

### 20. Does demo login verify a password?

No. It accepts an allowed demo email and active profile only. The route is
disabled when demo mode is off and must not be presented as production
authentication.

### 21. What does `/api/v1/auth/me` do?

It verifies the bearer token, finds the profile whose ID matches the token
subject, confirms the profile is active, and returns the profile's ID, email,
role, and display name.

### 22. Why normalize a demo email?

The request schema strips surrounding whitespace and case-folds the email
before the allow-list lookup, so harmless casing and whitespace differences
do not make a valid demo address fail.

## Roles and authorization

### 23. What roles does CloudDesk use?

`viewer`, `agent`, and `admin`.

### 24. How does the role hierarchy work?

The levels are viewer 1, agent 2, and admin 3. A route can require a minimum
role, so an agent route also permits an admin.

### 25. What is the difference between authentication and authorization?

Authentication establishes the caller's identity from a valid token.
Authorization checks whether the caller's role is high enough for the
requested action.

### 26. What is `require_role`?

It is a dependency factory. A route asks for a minimum role, and the returned
dependency verifies the current authenticated user's role before the route
handler runs.

### 27. What is the difference between `401` and `403`?

`401` means the request is not authenticated, for example because the token
is missing or invalid. `403` means the caller is authenticated but lacks the
required role.

### 28. Why centralize role checks?

It avoids duplicating role logic across endpoints and makes the access
hierarchy consistent. It also makes route requirements easier to review.

## Rate limiting and Redis

### 29. What is rate limiting?

It limits how many requests a source can make during a time period. This
helps protect availability and gives clients a clear response when they send
too many requests.

### 30. What rate-limit algorithm is implemented?

A fixed window: the client address and current 60-second window identify a
counter, and each request increments it.

### 31. What is the default rate limit?

120 requests per minute, configurable through the application settings.

### 32. Why use Redis for the counter?

Redis provides fast shared counters and expiration. In a multi-process
deployment, multiple application workers can use the same Redis service
rather than keeping separate counters in each process.

### 33. Is Redis required for local tests?

No. FakeRedis can be selected for local development and tests. The tests
exercise the middleware without requiring a running Redis server.

### 34. How is a real Redis connection configured?

Disable fake Redis and provide `REDIS_URL`. If fake Redis is disabled and the
URL is missing, client creation fails explicitly.

### 35. What happens when a caller exceeds the limit?

The middleware returns `429 Too Many Requests` with the configured limit,
remaining count, reset time, and a `Retry-After` header. It does not forward
that request to the route.

### 36. What happens if Redis is unavailable?

Redis operation errors return `503 Service Unavailable` and log a warning.
The middleware fails closed instead of silently bypassing rate limiting.

### 37. Is this a sliding-window or per-user limiter?

No. It is a fixed-window limiter keyed by client address. It is not
per-account throttling, a sliding window, or a full abuse-detection system.

## Audit logging and middleware

### 38. What does the audit middleware record?

For non-GET HTTP requests, it records the actor ID when available, request
ID, HTTP method, route path, status code, and a generic action name.

### 39. Are GET requests audited?

No. The current middleware deliberately skips GET requests.

### 40. Does the audit log contain request bodies or query-string values?

No. The audit record stores an empty details object and uses the route path
rather than the full URL. It does not log the request body or query string.

### 41. What happens when a request raises an unhandled exception?

The middleware writes an audit row with status 500 if it has not already
written one, then re-raises the exception so the application can return its
server error response.

### 42. Why is the audit layer outside the rate limiter?

That placement lets audit middleware observe non-GET requests that the rate
limiter rejects, so rejections can be recorded as well as successful route
operations.

### 43. What is middleware?

Middleware is application-wide code that runs around requests and responses.
It can apply shared behavior before a route runs and inspect or modify the
response afterward.

### 44. What is the effective middleware order?

Request ID wrapper, Starlette server-error handling, audit middleware, CORS,
rate limiter, then the FastAPI router and route dependencies.

### 45. Why is request-ID middleware outermost?

It can attach `X-Request-ID` to responses created by inner middleware or
server-error handling, not just normal route responses.

### 46. How does an audit record know who the actor is?

The JWT dependency stores the authenticated subject in request state. The
audit middleware reads it when the response is sent and verifies that it
matches a profile before recording the actor ID. Requests that fail before
authentication may have no actor ID.

### 47. Does rate limiting run before authentication?

Yes. The rate limiter is middleware around the router, so it can reject
excessive traffic before token verification and route handling.

## Testing, limitations, and design decisions

### 48. How are these behaviors tested offline?

Tests create an in-memory SQLite database, use FakeRedis, and exercise the
routes or middleware directly. This checks behavior without cloud credentials
or a Redis service.

### 49. What does the auth test suite cover?

It checks each demo role's token and profile, token claims and lifetime,
normalized email behavior, unknown/invalid identities, disabled demo mode,
missing signing secret, and protected `/me` access.

### 50. What does the rate-limit test suite cover?

It checks per-client fixed-window counting, `429` and retry headers, separate
client counters, Redis failure behavior, real-client configuration, and
request-ID preservation on a blocked response.

### 51. What does the audit test suite cover?

It checks that non-GET requests are recorded with actor and request details,
GET is skipped, query-string secrets are not captured, unhandled failures
are recorded, rate-limit rejections are audited, and middleware is assembled
in the intended order.

### 52. Does Phase 3 include Docker networking?

No. There is no Dockerfile or Compose configuration in Phase 3. FakeRedis is
an in-process local option; a real Redis server would be a separately
configured service.

### 53. Is production identity-provider integration complete?

No. The code can verify compatible HS256 JWTs when given the appropriate
secret, but the demo login route does not authenticate passwords or provision
a production identity service.

### 54. What is one important security boundary?

The JWT secret is server-side configuration. The server validates tokens,
and clients should send them over HTTPS in a protected authorization header.
Secrets must not be placed in source control or exposed to browser code.

### 55. What would you improve for a production rollout?

Use an approved production identity provider and credential flow, define a
token revocation/rotation strategy, configure shared Redis and secure secret
storage, and validate proxy-aware client identity so rate limits use the
intended client key. Then test the deployment and its operational failure
modes.

### 56. How would you summarize Phase 3 in one sentence?

“Phase 3 established reusable identity, role-based authorization,
rate-limiting, request tracing, and audit foundations so later support routes
can be protected consistently.”

## Repository references

- [Phase 3 codebase explanation](../explain_codebase/phase3_explained.md)
- [Phase 3 system design evolution](../design_evolution/Phase3_Project_System_Design_Evolution.md)
- [Phase 3 infrastructure and wiring](../Infra_design_evolution/Phase3_Infra_design_evolution.md)
- [JWT and role dependency](../../backend/app/core/security.py)
- [Demo authentication routes](../../backend/app/api/auth.py)
- [Rate-limit middleware](../../backend/app/middleware/rate_limit.py)
- [Audit middleware](../../backend/app/middleware/audit.py)
- [Application middleware setup](../../backend/app/main.py)
- [Auth, rate-limit, and audit tests](../../tests/api/)
- [Phase 3 task tracker](../../TASKS.md)
