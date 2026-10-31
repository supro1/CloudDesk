# PostgreSQL and Supabase setup

The SQLAlchemy models remain the portable application schema. The PostgreSQL
scripts provide the Supabase deployment schema and access controls.

For a new Supabase project, apply `schema.sql`, then `rls_policies.sql`, then
`seed.sql` in the SQL editor. These scripts assume Supabase's `auth` schema and
the `anon`, `authenticated`, and `service_role` roles. The authenticated browser
role can read data only when its `auth.uid()` maps to an active `profiles` row
with a `viewer`, `agent`, or `admin` role. It receives no direct write access.
Viewers cannot read internal ticket messages or workflow, approval, action,
escalation, and memory records; agents and admins can. The backend service-role
credential must remain server-side.

Alternatively, apply the numbered files in `migrations/` in order. The
migrations are immutable once applied; make future schema changes in a new
numbered migration and update `schema.sql` to the current schema. The migration
files intentionally mirror the corresponding SQL editor scripts; tests enforce
that they remain synchronized.

`seed.sql` intentionally contains no application rows yet. P2-4 introduces
`sample_data/` as the canonical fixture source and loads it through the backend,
avoiding duplicate or conflicting demo data.
