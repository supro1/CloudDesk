# Phase 2 — Interview Questions and Answers

This question bank covers Phase 2: persistence and demo data. The answers are
written so they can be spoken to a mixed technical and non-technical interview
board. They describe the implementation in this repository and distinguish it
from later planned features.

## Product and design overview

### 1. What was the goal of Phase 2?

To give CloudDesk a consistent way to represent and store support data, a
reusable database-access layer, PostgreSQL setup assets, and realistic demo
records for a clean local database.

### 2. How would you explain Phase 2 without technical terms?

Phase 2 built the filing system for the support team. It defines what belongs
in a customer, ticket, or message record; how those records are connected; how
staff can find them; and how a new demo installation gets realistic example
cases.

### 3. What changed from Phase 1?

Phase 1 provided the running application foundation. Phase 2 added the support
domain's data model, persistence components, database scripts, and demo-data
loading. It did not yet add the customer-support API or AI resolution workflow.

### 4. What is the difference between a model and a repository?

A model describes the shape of one kind of record, such as a ticket. A
repository provides operations for working with those records, such as finding
a ticket by its public number. The separation keeps record structure distinct
from database lookup behavior.

### 5. What can you confidently say is complete?

The Phase 2 task table marks all four tasks complete: SQLAlchemy entities and
ticket categories, PostgreSQL schema/RLS/migrations, repositories, and
sample-data bootstrap. Tests cover model behavior, database compatibility,
repository operations, and bootstrap safety.

### 6. Does Phase 2 already solve support tickets with AI?

No. It creates storage shapes for support and future workflow information, but
the API, AI agents, and ticket-resolution workflow are later work.

## Data modeling and database design

### 7. What kinds of information does the data model cover?

It includes profiles, customers, subscriptions, workspaces, products, tickets,
ticket messages, support articles, incidents, workflow runs and events,
resolution actions, approval requests, escalations, customer memory, and
audit logs.

### 8. Why define workflow tables before the workflow is built?

The data model needs a place for later phases to store workflow history and
decisions. Defining those records early provides a consistent foundation; it
does not claim that the workflow behavior is already implemented.

### 9. How are records connected?

Stable IDs identify records, and foreign keys connect related records. For
example, a ticket points to a customer, and a ticket message points to a
ticket. These relationships help prevent records from referring to missing
parents.

### 10. Why use a fixed ticket-category enum?

It limits ticket categories to the agreed list, avoiding inconsistent values
such as different spellings for the same issue. The category list lives in a
shared schema module and is represented in the database constraints.

### 11. How does the model support both SQLite and PostgreSQL?

The SQLAlchemy entities use portable column types and types such as JSON and
string UUIDs rather than database-specific types. SQLite is used for local
demonstrations and tests, while PostgreSQL has matching SQL setup scripts.
Database-specific behavior still needs to be considered when deploying.

### 12. Why use string UUIDs?

The model uses a common textual ID format that can be stored in both SQLite
and PostgreSQL. This avoids making local development dependent on one
database's native UUID column type.

### 13. What do the constraints and indexes do?

Constraints protect data rules, such as unique ticket numbers, unique
workspace slugs per customer, valid relationships, and non-negative
subscription counts. Indexes help the database find common records, such as
tickets by status or customer, more efficiently.

### 14. How are creation and update timestamps handled?

The shared timestamp mixin supplies `created_at` and `updated_at` to the
models. The ORM uses UTC-aware defaults and updates the update timestamp when
an ORM-managed record changes. PostgreSQL schema setup also supplies
database-side timestamp defaults and triggers.

### 15. Why use JSON columns?

Some fields naturally contain structured but variable details, such as
workspace settings or workflow state. JSON columns let the application retain
that structure without creating a separate column for every possible nested
value. The model uses a portable JSON type for SQLite and PostgreSQL.

## Repository layer

### 16. Why not let every feature write SQL directly?

That would spread database details across the codebase and make behavior
harder to test or change. Repositories provide one controlled place for
common database operations and domain-specific lookups.

### 17. What does the base repository provide?

It supports common create, get, list, count, update, and delete operations. It
also validates pagination and blocks updates to protected fields such as IDs
and timestamps.

### 18. What do specialized repositories add?

They provide common lookups in business language, such as finding a profile by
email, a product by slug, tickets by ticket number or status, messages for a
ticket, or pending approvals for a ticket.

### 19. Why are the database calls asynchronous?

The application uses FastAPI and SQLAlchemy's async interfaces. Asynchronous
database calls let the server yield while waiting for database I/O instead of
blocking the event loop for that wait.

### 20. Does the repository layer commit every operation itself?

The repositories add or flush changes through the supplied session. The
caller controls the session's transaction and commit boundary. This makes it
possible for a service such as demo bootstrap to group related writes into one
transaction.

### 21. How do you handle missing records?

Read and update methods return `None` when a record does not exist; delete
returns `False`. Invalid pagination or attempts to modify protected fields
raise a clear `ValueError`. API routes and HTTP error mapping are not part of
Phase 2.

## Demo-data bootstrap

### 22. When is demo data loaded?

During application startup, after the tables are created, the lifespan checks
the `DEMO_MODE` setting. The bootstrap runs only when demo mode is enabled.

### 23. How does the bootstrap avoid duplicate data?

Before importing fixtures, it checks whether any modeled table contains
records. If the database is not completely empty, it returns without loading
the fixtures. Tests verify a second bootstrap does not duplicate customers or
tickets.

### 24. How does it connect related fixture records?

The JSON files can refer to a customer by email or a ticket by ticket number.
The loader builds lookup maps, finds the corresponding database record, and
stores its ID as the relationship. An unknown reference raises an error
instead of being silently ignored.

### 25. What does “atomic” mean for the demo import?

The loader performs the import inside a database transaction. If loading fails,
the transaction rolls back so the database does not retain only part of the
demo dataset. Tests check that a missing fixture does not leave partial
customer or ticket records behind.

### 26. What happens to previous resolutions in the sample data?

The loader turns each previous resolution into a ticket message marked
internal. That preserves it as support history rather than presenting it as a
message sent by the customer.

### 27. What sample-data coverage is tested?

The tests verify 3 profiles, 8 customers, 8 subscriptions, 9 workspaces, 13
tickets, 2 incidents, and 16 ticket messages, along with relationships and a
previous-resolution example.

### 28. What happens if demo mode is off?

The application still creates missing tables during startup, but it does not
call the demo-data bootstrap. The production database should be initialized
with the documented schema/migration process and controlled data operations.

## PostgreSQL and security

### 29. What is row-level security?

It is a database feature that checks which rows an authenticated database user
may read or change. In this project, the PostgreSQL/Supabase policies restrict
reads by the support role and prevent viewers from seeing internal ticket
messages and agent-only workflow information.

### 30. Does SQLite enforce those RLS policies?

No. The RLS policies are PostgreSQL/Supabase SQL. SQLite is for local demo and
test use and does not provide the same database-side access control.

### 31. Is the application already connected to Supabase?

No live Supabase deployment or credential use is claimed. The repository
contains PostgreSQL schema, migration, and RLS setup scripts, and its database
documentation describes how to apply them.

### 32. Where should a privileged database credential be kept?

On the server side only, supplied through protected environment or deployment
configuration. It must never be embedded in browser code or committed to the
repository.

### 33. Is RLS the only authorization layer?

No. Database RLS is a database-side boundary for the PostgreSQL/Supabase
configuration. Application authentication and route-level role checks are
separate later-phase work. A database policy does not replace API
authorization.

### 34. How are migrations intended to be maintained?

Apply numbered migrations in order and treat applied migrations as immutable.
A future schema change should add a new migration and update the current
`schema.sql`, rather than rewriting the history of an already-applied
migration.

## Testing and lessons

### 35. How do you test this without a real database service?

Repository and bootstrap tests create an in-memory SQLite engine and tables.
This keeps the tests offline and isolated while still exercising SQLAlchemy
queries and transactions.

### 36. What does the schema parity test protect?

It checks that the PostgreSQL setup scripts and SQLAlchemy models describe
compatible structures. This helps catch drift between the schema used by the
application and the schema prepared for PostgreSQL.

### 37. What was an important design decision in this phase?

Keeping database access in repositories while keeping the domain shape in
models. This gives future APIs and services a consistent foundation without
mixing HTTP behavior into database code.

### 38. What is one limitation of the current demo bootstrap?

It intentionally seeds only a completely empty database. It is not a general
data migration or fixture merge mechanism. That conservative rule avoids
mixing demo records into a database that may already contain meaningful data.

### 39. What would you build next?

The task plan moves into identity and request guards, then support API routes.
Those features can use the models and repositories created here. I would keep
the same boundaries: API validation and authorization at the route layer,
orchestration in services, and SQL access in repositories.

### 40. How would you summarize the phase in one sentence?

“Phase 2 turned CloudDesk from a runnable service into an application with a
portable support-data model, a disciplined persistence layer, PostgreSQL
security setup assets, and safe repeatable demo data.”

## Repository references

- [Phase 2 codebase explanation](../explain_codebase/phase2_explained.md)
- [SQLAlchemy entities](../../backend/app/models/entities.py)
- [Repository implementations](../../backend/app/repositories/)
- [Database engine and sessions](../../backend/app/core/database.py)
- [Demo bootstrap service](../../backend/app/services/seed_service.py)
- [PostgreSQL schema, migrations, and RLS](../../database/)
- [Repository and bootstrap tests](../../tests/unit/)
- [Phase 2 task tracker](../../TASKS.md)
