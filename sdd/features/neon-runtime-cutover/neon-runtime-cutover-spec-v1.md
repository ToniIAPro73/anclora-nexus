# Neon Runtime Cutover — Specification v1

## Status

**Provider reconciliation required (2026-10-27).** Neon schema/data and production Data API credentials exist, and the production frontend is deployed with the Neon-capable code. However, the Vercel project has no `DATABASE_PROVIDER` or `NEXT_PUBLIC_DATABASE_PROVIDER` variables. Both server and browser code default to Supabase when those selectors are absent. Therefore this evidence does not establish that Nexus production routes application data to Neon. The Render service's provider variables have not been independently verified in this audit.

## Goal

Move Anclora Nexus application-data reads and writes from Supabase PostgreSQL to the existing Neon project. Authentication is provided by Anclora Identity in the deployed application; storage is tracked independently by the Vercel Blob cutover specification. Keep the database change reversible and do not move the deployment from Vercel in this work.

## Current evidence

- Neon and Supabase each contain 68 public tables, with matching names and exact per-table row counts (1,214 rows in total at the last comparison).
- Production Vercel has `NEON_DATA_API_URL`, `NEON_JWT_KEY_ID`, and `NEON_JWT_PRIVATE_KEY`, but lacks both provider selectors. The code checks `DATABASE_PROVIDER` / `NEXT_PUBLIC_DATABASE_PROVIDER` explicitly and defaults to Supabase.
- Preview Vercel currently has no Neon Data API URL or Neon JWT signing key, so it is not a ready Neon validation environment.
- Production Vercel has Anclora Identity configuration and the production deployment includes the Identity login integration. Authentication is a separate provider from the application database.
- The code separates Neon database access from authentication and object storage. Supabase credentials and services may remain for legacy paths and rollback, but their presence does not prove active use.
- The storage cutover code and Vercel Blob token are present, but the Render service's `NEXUS_STORAGE_PROVIDER` and Blob token were not visible through the available read-only service metadata; effective storage selection must be confirmed there.
- The earlier RLS/grant audit and row-count comparison are historical evidence, not a substitute for validating current Neon grants, RLS, Realtime behavior, and authenticated access.

## Scope

- Separate application data access from Anclora Identity and object storage in the backend service facade.
- Explicitly select Neon in each intended deployment environment and route all application table/RPC operations through its authenticated interface; preserve existing service-level query behavior and org scoping.
- Route the small number of frontend direct database operations to Neon while leaving sign-in, session, and OIDC callbacks on Anclora Identity.
- Replace or adapt Realtime subscriptions so they observe Neon writes, without leaving stale Supabase subscriptions presented as live data.
- Establish least-privilege Neon Data API roles/grants and RLS policies before enabling public access. Preserve append-only `audit_log` and `org_id` isolation.
- Verify schema objects beyond row counts: columns, defaults, sequences, indexes, constraints, functions, triggers, extensions, grants, policies, and vector behavior.
- Keep Supabase PostgreSQL active and unchanged as rollback source until the production cutover is validated.

## Acceptance criteria

1. Both Vercel provider selectors and the Render backend selector are set to Neon in the intended environment; all application table/RPC traffic is verified against Neon, with no database reads/writes remaining on Supabase.
2. Anclora Identity login, session, and OIDC callbacks continue to work independently of the database provider.
3. Object storage follows the separate Blob cutover contract and is not changed by selecting the database provider.
4. Realtime behavior reflects writes made to Neon, or the affected UI has an explicit, tested alternative.
5. Anonymous users cannot access protected Neon tables; authenticated users are isolated by organization/user ownership; service credentials stay server-side.
6. No writes or deletes are performed on `audit_log`; existing signed append behavior remains intact.
7. Schema/data parity and dedicated-account read/write QA pass on the intended deployment before production cutover.
8. Backend tests, frontend typecheck/lint/tests, and the authorized runtime smoke pass before declaring the cutover complete.
9. Supabase remains available for rollback; no automatic dual-write or project deletion.

## Out of scope

- Changing the Anclora Identity integration.
- Executing the separate object-storage cutover.
- Moving Vercel deployment to Cloudflare.
- Pausing/deleting Supabase.

## Rollback

Switch the application-data provider back to Supabase and redeploy. Keep Neon data and schema intact. Do not use dual-write during migration; if any writes happen after cutover, rollback requires an explicit reconciliation procedure first.
