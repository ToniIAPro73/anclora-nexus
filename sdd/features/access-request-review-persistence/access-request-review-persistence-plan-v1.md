# ANCLORA-ARRP-001 — Implementation plan

1. Add service tests that prove review persistence happens before Identity provisioning, failed persistence stops provisioning, and audit reads/writes use the scoped persistence API.
2. Add forward-only SQL functions with a fixed search path, scoped parameters, transition checks, and restricted execution grants.
3. Update the Nexus review service to use those RPCs for state transitions and access-request audit operations.
4. Run focused backend tests and validate the migration against the isolated Neon security-review branch or a Neon temporary migration branch.
5. Keep the migration unapplied to production and all code uncommitted until Toni reviews the development result. Production QA resumes only after the governed release flow applies the migration and deploys compatible backend code.
