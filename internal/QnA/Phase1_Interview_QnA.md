# Phase 1 — Interview Questions and Answers

This question bank covers the Phase 1 runtime foundation only. It avoids
claiming that future ticket, authentication, database, AI-workflow, or Docker
features are already implemented.

## Product and design overview

### 1. What was the goal of Phase 1?

To establish a dependable runtime foundation for CloudDesk: centralized
configuration, structured logs, health endpoints, request IDs, and a repeatable
offline test setup.

### 2. What problem does this phase solve for the business?

It makes the service easier to start, monitor, troubleshoot, and test before
more complicated support-ticket features are added. It reduces setup surprises
and gives developers a consistent way to investigate a request.

### 3. Does Phase 1 already resolve customer support tickets?

No. It is the application foundation. Ticket persistence, authentication,
knowledge retrieval, AI agents, and the resolution workflow belong to later
phases.

### 4. How would you describe the design to a non-technical person?

It is like preparing a support office before opening: configure the office,
put up a working-status sign, give each visitor a reference number, and create
a practice environment. The actual ticket-solving team is built later.

### 5. What is the request flow?

A caller sends an HTTP request. Middleware validates or creates a request ID,
FastAPI routes the request (for Phase 1, to a health endpoint), the response
returns with the same ID, and log entries can use that ID for correlation.

## Configuration and logging

### 6. How are application settings loaded?

The Pydantic Settings model in `backend/app/core/config.py` reads environment
variables and an optional `.env` file. Typed fields and validators check values
such as CORS origins and positive numeric settings.

### 7. Why use environment-based configuration?

The same code can run in local development, tests, and future deployments
without hard-coding environment-specific values. Secrets can be supplied
outside the source code.

### 8. What are the Phase 1 default provider settings?

The defaults select fake LLM and embedding providers and an in-memory vector
store. This supports an offline-friendly runtime configuration; it does not
mean a complete AI support workflow has been implemented.

### 9. Why use `SecretStr` for secret settings?

It reduces the chance of accidentally displaying secret values in normal
representations. It is a safety aid, not a replacement for careful secret
handling or secure deployment configuration.

### 10. Why is the settings factory cached?

The `get_settings()` factory is cached so the application can reuse one
validated settings object instead of repeatedly rebuilding it. Tests can
construct `Settings` directly when they need isolation.

### 11. What does structured JSON logging mean?

Instead of an unstructured sentence alone, each log entry is a JSON object with
fields such as time, severity, logger name, and message. This makes logs easier
for both people and log-search systems to filter and process.

### 12. Why include request or workflow IDs in logs?

They provide a way to connect related events. In Phase 1, request context is
available to the formatter. A workflow ID field is supported by the formatter
for future workflow telemetry, but Phase 1 does not run workflows.

## Health and request tracking

### 13. What is the difference between liveness and readiness?

Liveness answers, “Can this process respond?” Readiness answers, “Are the
checks required to serve work passing?” They let an operator distinguish a
running process from one that is ready to receive normal traffic.

### 14. What do the Phase 1 health endpoints return?

`/health` and `/health/live` return HTTP 200 with `{"status":"ok"}`.
`/health/ready` reports each configured check and returns HTTP 503 if any
check fails.

### 15. Does readiness verify the database or Redis in Phase 1?

Not by default. The current app registers an application-only readiness check.
There is no Phase 1 database or Redis service health check wired in.

### 16. What is an `X-Request-ID`?

It is a short reference attached to a web request. If the caller provides a
valid ID, the app preserves it; otherwise, the app creates a UUID. The ID is
returned in the response and can appear in request-scoped logs.

### 17. Why validate a caller-supplied request ID?

To keep the value within a predictable character set and length, and to avoid
unsafe header content. Invalid IDs are replaced with a generated UUID.

### 18. Why put the request ID on error responses too?

A caller still needs a reference when something fails. The middleware wraps
the application stack so even server-generated error responses can carry the
ID.

### 19. What is CORS doing here?

CORS controls which browser origins may make cross-origin requests and which
response headers browser code can read. The Phase 1 app exposes
`X-Request-ID`; the default allowed origin is local development. CORS does not
authenticate users.

## Testing and developer workflow

### 20. How does the test harness avoid external services?

`tests/conftest.py` sets environment values before the app is imported. It
selects fake providers, in-memory vector-store mode, and a temporary SQLite
database path. The current runtime tests can run without an AI API key or
Docker.

### 21. Why use a temporary database path in tests?

It keeps test state separate from developer data and avoids accidental
modification of a persistent local database. The temporary directory is
cleaned up when the test process exits.

### 22. How are tests sent to the application?

The health API tests call the application through an in-process ASGI helper.
That verifies routing, status codes, response headers, and body behavior
without starting a network server.

### 23. What behaviors are tested in Phase 1?

The tests cover settings defaults and overrides, validation, JSON log
formatting, health responses, failed readiness, request-ID preservation and
generation, invalid ID replacement, IDs on errors, and CORS exposure of the
header.

### 24. What does `make demo` do at this phase?

It starts the Phase 1 runtime and explicitly prints that support tickets and
workflows are not implemented yet. It should not be presented as an end-to-end
ticket-resolution demo.

### 25. How does a developer run or validate the service?

The Makefile provides setup, backend, test, lint, and demo targets. On Windows,
the Python command defaults to `.venv/Scripts/python.exe`; setup uses `uv`.

## Operational and trade-off questions

### 26. Is the service containerized in Phase 1?

No. The implemented setup runs as a local FastAPI process. Docker and Compose
networking are future infrastructure work, so I would distinguish the future
design from what is currently present.

### 27. What is the current default server address?

The Makefile uses `127.0.0.1` and port `8000`. These are developer defaults
and can be overridden with `HOST` and `PORT`.

### 28. What is one limitation of Phase 1 readiness?

The default readiness check only confirms application availability. Once
external dependencies are introduced, their checks should be registered so
readiness reflects the actual services required for work.

### 29. How would you extend health checks later?

Supply named checks to the application for dependencies such as a database or
cache. Keep liveness lightweight and use readiness for the checks needed before
accepting work. Each check should report failure clearly.

### 30. How would you extend the request ID into later phases?

Propagate it from HTTP middleware through services and structured logs, and
include it in relevant audit or telemetry records where appropriate. Avoid
using it as a substitute for user identity or authorization.

### 31. What happens if a readiness check raises an exception?

The health endpoint records an exception in the server logs, marks that named
check as an error, and returns an unavailable status rather than claiming that
the app is ready.

### 32. What security protections does this phase provide?

It validates request IDs before reflecting them, keeps secret configuration in
secret-aware settings fields, and avoids requiring credentials for offline
tests. It does not yet implement authentication, authorization, rate limiting,
or the full application security controls.

### 33. What is the main design trade-off?

The phase favors a small local runtime and offline tests over production
infrastructure. That keeps the foundation quick to run and validate, while
making it clear that real dependency checks, containers, and business features
must be added in later phases.

### 34. How do you know the implementation is complete?

The Phase 1 task tracker marks the configuration/logging, health/request-ID,
offline test harness, and Makefile/environment-example tasks complete. The
tests exercise the runtime behavior. The broader project plan still includes
many phases and should not be described as complete based on Phase 1 alone.

## Statistics follow-up: why divide by a standard error in a t-test?

The t-statistic measures a difference in **standard-error units**. For a
one-sample test,

```text
t = (sample mean - hypothesized population mean) / (sample standard deviation / sqrt(sample size))
```

For a paired test, first compute each pair's difference, then use

```text
t = (mean of paired differences - hypothesized difference) /
    (standard deviation of paired differences / sqrt(number of pairs))
```

The denominator is the **estimated standard error of the sample mean**, not
simply the sample standard deviation. It accounts for the variation in
observations and the number of observations. Dividing by it puts the observed
difference on a comparable scale: how many estimated standard errors away from
the null value it is. Because the population standard deviation is unknown and
estimated from the sample, the statistic follows a Student t distribution
under the test assumptions.

## Repository references

- [Runtime app](../../backend/app/main.py)
- [Settings](../../backend/app/core/config.py)
- [Logging](../../backend/app/core/logging.py)
- [Health tests](../../tests/api/test_health.py)
- [Settings and logging tests](../../tests/unit/test_settings_logging.py)
- [Offline test setup](../../tests/conftest.py)
- [Makefile](../../Makefile)
