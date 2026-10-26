# Neon Runtime Cutover — Specification v1

## Status

Draft for implementation and Preview validation. The application is not migrated merely because the schema and rows exist in Neon.

## Goal

Move Anclora Nexus application-data reads and writes from Supabase PostgreSQL to the existing Neon project while retaining Supabase Auth and Supabase Storage. Keep the change reversible and do not move the deployment from Vercel in this work.

## Current evidence

- Neon and Supabase each contain 68 public tables, with matching names and exact per-table row counts (1,214 rows in total at the last comparison).
- Nexus has no Neon Data API configured. Its 68 backend service modules and four frontend files still access tables through Supabase.
- The same Supabase client also handles Auth and Storage, so a URL-only replacement would break those capabilities.
- Neon reports RLS enabled on 50/68 public tables and disabled on 18/68; 64 policies exist. The `anon` role has broad table grants. This access posture must be reviewed and restricted before exposing a Neon Data API.
- The frontend uses Supabase Realtime channels; those channels will not observe writes to Neon after cutover and need an explicit replacement or documented compatibility path.
- Nexus memory records that Neon must not be treated as a drop-in replacement without redesigning auth/data paths.

## Scope

- Separate data access from Supabase Auth and Supabase Storage in the backend service facade.
- Route all application table/RPC operations to Neon through a supported, authenticated interface; preserve existing service-level query behavior and org scoping.
- Route the small number of frontend direct database operations to Neon while keeping sign-in, session, and OAuth callbacks on Supabase Auth.
- Replace or adapt Realtime subscriptions so they observe Neon writes, without leaving stale Supabase subscriptions presented as live data.
- Establish least-privilege Neon Data API roles/grants and RLS policies before enabling public access. Preserve append-only `audit_log` and `org_id` isolation.
- Verify schema objects beyond row counts: columns, defaults, sequences, indexes, constraints, functions, triggers, extensions, grants, policies, and vector behavior.
- Keep Supabase PostgreSQL active and unchanged as rollback source until the production cutover is validated.

## Acceptance criteria

1. All application table and RPC traffic uses Neon after provider selection; no database reads/writes remain on Supabase.
2. Supabase Auth token verification, login, refresh, and callbacks continue to use the existing Supabase project.
3. Supabase Storage uploads/downloads continue to use Supabase Storage.
4. Realtime behavior reflects writes made to Neon, or the affected UI has an explicit, tested alternative.
5. Anonymous users cannot access protected Neon tables; authenticated users are isolated by organization/user ownership; service credentials stay server-side.
6. No writes or deletes are performed on `audit_log`; existing signed append behavior remains intact.
7. Schema/data parity and dedicated-account read/write QA pass on the intended deployment before production cutover.
8. Backend tests, frontend typecheck/lint/tests, and Preview integration smoke pass before production promotion.
9. Supabase remains available for rollback; no automatic dual-write or project deletion.

## Out of scope

- Migrating Supabase Auth to Neon Auth or Anclora Identity.
- Moving Supabase Storage or uploaded objects.
- Moving Vercel deployment to Cloudflare.
- Pausing/deleting Supabase.

## Rollback

Switch the application-data provider back to Supabase and redeploy. Keep Neon data and schema intact. Do not use dual-write during migration; if any writes happen after cutover, rollback requires an explicit reconciliation procedure first.
