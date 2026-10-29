# Access Request Intake Company Mapping — Tasks v1

- [x] Confirm the production `access_requests` schema and capture the failing webhook response.
- [x] Add a focused persistence test for the `company_name` to `company` mapping.
- [x] Normalize the intake field alias before the database insert.
- [x] Run the focused backend test and inspect the scoped diff.
- [ ] Retry the existing Data Lab request with its original idempotency key after the fix is deployed.
- [ ] Submit and verify a GuestHub request after the Nexus fix is deployed.
