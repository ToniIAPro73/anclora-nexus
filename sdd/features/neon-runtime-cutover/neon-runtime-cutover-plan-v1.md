# Neon Runtime Cutover — Plan v1

1. Inventory all database, Auth, Storage, and Realtime call sites; identify direct database paths and their authorization rules.
2. Compare Neon and Supabase schema objects and security metadata, not only table names/row counts. Prepare least-privilege RLS/grant corrections on an isolated Neon branch.
3. Implement a backend data-access facade that routes table/RPC calls to Neon while Auth and Storage remain on Supabase.
4. Adapt the frontend's direct database calls and Realtime subscriptions to Neon without changing login/session behavior.
5. Add provider, token-validation, org-isolation, audit immutability, Storage, and Realtime regression tests.
6. Verify Neon with a dedicated QA account on development Preview. Preserve Supabase as rollback source.
7. After Toni validates Preview, promote through the governed workflow, then update the production runtime contract and deployment secrets.

Production Neon schema/security migrations, production provider changes, and Supabase shutdown remain separate reviewed steps. Cloudflare migration is out of scope.
