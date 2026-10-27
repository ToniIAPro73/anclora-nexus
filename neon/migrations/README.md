# Nexus Supabase-to-Neon cutover

The database copy already exists in Neon. This sequence configures an isolated branch and the application path; it does not switch production or retire Supabase.

## Isolated branch sequence

1. Run `000_prepare_neon_data_api_roles.sql` on the temporary branch. It renames the imported Supabase `anon`, `authenticated`, and `service_role` roles so Neon can create its managed API roles.
2. Provision Neon Data API with external JWT auth, schema `public`, role claim `.role`, audience `authenticated`, `db_anon_role=anonymous`, and `skip_auth_schema=true` because the Supabase `auth` schema was copied.
3. Run `001_neon_data_api_access_security.sql` after provisioning. It creates/grants a server-only `service_role`, revokes anonymous table access, and adds user/org-scoped RLS for the small set of browser reads and writes.
4. Configure Neon Data API's JWKS URL to the deployed Nexus Preview endpoint `https://<preview-host>/api/neon-jwks`. Supabase's current legacy HS256 keys cannot be verified by Neon Data API's JWKS verifier; Nexus exchanges validated Supabase sessions for short-lived ES256 tokens. Do not point Neon at the Supabase JWKS for these application tokens.
5. Configure the Preview runtime with `DATABASE_PROVIDER=neon`, `NEXT_PUBLIC_DATABASE_PROVIDER=neon`, both Neon Data API URL variables, and the server-only ES256 key plus key ID. The private key must never use a `NEXT_PUBLIC_` variable.
6. Verify anonymous denial, dedicated QA-user reads/writes, cross-organization denial, backend service access, Anclora Identity login/session, object storage per the separate Blob cutover contract, and polling-based notifications. Keep Supabase PostgreSQL intact as rollback until Toni validates Preview and production.

Neon Data API URLs end in `/rest/v1`; the Supabase clients add this path themselves, so runtime code removes that suffix before initialization.

## Current status

- Data and table counts were compared earlier: 68 public tables and 1,214 rows match between Supabase and Neon.
- Security and Data API setup has been applied only to branch `nexus-neon-cutover-security-review-20261026`.
- Requests with no bearer token were denied. The legacy Supabase HS256 anon JWT was rejected by Neon because it did not contain a key ID; that is expected with the configured external JWKS verifier. Full JWT/RLS integration verification still requires the Preview JWKS endpoint and the dedicated QA identity.
- CORS `*` is allowed only on this disposable security-review branch. Set the actual Preview origin before testing in Preview, and the production origin before any production cutover.
- Historical note (2026-10-26): no production environment variables had been changed and no production database had been altered at that time. Current production provider status is recorded in `.anclora/PRODUCTION_RUNTIME.md`.
