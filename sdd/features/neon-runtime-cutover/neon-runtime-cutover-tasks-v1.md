# Neon Runtime Cutover — Tasks v1

## Verified state at last audit (2026-10-27)

- Production Vercel has Neon Data API/JWT secrets, but neither `DATABASE_PROVIDER` nor `NEXT_PUBLIC_DATABASE_PROVIDER`; the application code defaults to Supabase.
- Vercel Preview lacks Neon Data API/JWT variables and is not currently configured as a Neon validation target.
- Render's effective database provider could not be verified from available service metadata.
- Anclora Identity is configured for the Nexus production frontend. Storage has a separate Vercel Blob cutover specification; Render's active storage selection is unverified.

## Remaining before declaring the Neon cutover complete

- [ ] Verify database-provider variables on the existing Render production service and identify every runtime that serves application data.
- [ ] Decide and explicitly configure the intended Neon environment selectors for Vercel and Render; do not infer cutover from secret presence.
- [ ] Publish/configure the required Neon JWT trust metadata and verify the currently deployed signer/issuer against the Neon Data API.
- [ ] Re-audit schema, grants, RLS, Realtime, vector behavior, and table/RPC call sites against the live Neon project.
- [ ] Run authenticated read/write smoke using the dedicated QA identity and verify requests reach Neon, including org isolation and audit-log immutability.
- [ ] Update this contract with observed effective provider values after runtime verification; retain Supabase as rollback until then.
