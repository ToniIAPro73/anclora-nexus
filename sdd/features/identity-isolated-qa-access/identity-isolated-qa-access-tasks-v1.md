# Nexus isolated QA intake tasks

- [x] Add dedicated QA configuration and separate authenticated intake routes for GuestHub and Data Lab.
- [x] Stamp a server-owned QA namespace marker and route to the isolated shared Nexus QA organization.
- [x] Pass the QA role to Identity provisioning only for marked requests.
- [x] Preserve reviewer org scoping and audit behavior in the existing workflow.
- [x] Add focused tests for authentication, isolation, failure-before-write, normal-path compatibility, and provisioning role.
- [x] Verify the existing isolated-auth-qa organization has one active QA reviewer and no access requests.
- [ ] Configure dedicated webhook secrets and deploy the approved code through governed releases before live E2E.

Render's latest two deployment attempts fail at startup because `NEON_DATA_API_URL` is unset; the live service remains on an older successful revision. Vercel environment listing is denied (403), and CLI inspection failed with a network fetch error.
