# Neon Runtime Cutover — Tasks v1

- [ ] Build a call-site inventory of every table/RPC/Auth/Storage/Realtime path.
- [ ] Compare source/target columns, constraints, indexes, sequences, functions, triggers, extensions, grants, and RLS policies.
- [ ] Identify and correct the 18 tables without RLS and broad `anon` grants on an isolated Neon branch; test org/user isolation before applying to production.
- [ ] Add explicit Neon/Supabase provider settings and separate database, Auth, and Storage clients in the backend.
- [ ] Route backend table/RPC access to Neon while preserving Supabase Auth token validation and Storage.
- [ ] Route frontend direct database reads/writes to Neon; retain Supabase login/session/OAuth.
- [ ] Replace Supabase Realtime subscriptions with a tested Neon-backed mechanism.
- [ ] Add regression tests, including cross-organization denial and append-only audit-log behavior.
- [ ] Run focused backend/frontend gates and dedicated-account Preview smoke tests.
- [ ] Obtain Toni's Preview validation before production cutover; keep Supabase active for rollback.
- [ ] Update the runtime contract to Neon PostgreSQL + Supabase Auth + Supabase Storage after cutover.
