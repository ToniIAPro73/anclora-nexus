# Nexus isolated QA intake tasks

- [x] Add dedicated QA configuration and separate authenticated intake routes for GuestHub and Data Lab.
- [x] Stamp a server-owned QA namespace marker and route to the isolated shared Nexus QA organization.
- [x] Pass the QA role to Identity provisioning only for marked requests.
- [x] Preserve reviewer org scoping and audit behavior in the existing workflow.
- [x] Add focused tests for authentication, isolation, failure-before-write, normal-path compatibility, and provisioning role.
- [x] Verify the existing isolated-auth-qa organization has one active QA reviewer and no access requests.
- [x] Configure separate GuestHub and Data Lab QA webhook secrets in Nexus Render Production and matching local-caller variables in Vercel Development.
- [x] Activate the latest Nexus QA environment configuration through the authorized deployment and verify the GuestHub local caller against the live service.
- [x] Apply and verify the least-scope `SELECT`/`INSERT` privileges on `access_requests` for Nexus `service_role` through migration 003.
- [x] Reset the persistent Nexus QA reviewer's password through the audited Identity CLI; store it only in the ignored Nexus `.env.local` with mode 0600.
- [x] Persist one GuestHub QA pilot request in the isolated Production QA organization: `1f46819b-8382-4f56-99a9-dd2c0d84987d` (`pending`).
- [ ] Verify the Data Lab local caller against the live service.
- [ ] Review and approve both requests through the Nexus UI, then finish the Identity login checks in each app.
- [ ] Verify request/approval email delivery in the dedicated QA inbox.

The earlier startup failures caused by a missing `NEON_DATA_API_URL` have been superseded: Render reports the Nexus deployment for commit `f810466` as live, and the variable is configured. Vercel environment metadata was inspected with the CLI; QA variables are limited to Development, while Production remains unchanged. GuestHub's local caller now successfully forwards a request to Nexus. The shared `access_requests` table was created after the initial Data API grants, so migration `003_access_requests_service_role_permissions.sql` grants `SELECT` and `INSERT` to the backend `service_role`; Production privileges were verified, with `UPDATE` and `DELETE` still denied. The persistent QA reviewer's password was reset using Identity's audited CLI and saved locally without recording its value. Data Lab's first local OIDC discovery request hit its eight-second timeout; the same Development configuration completed discovery after the issuer warmed. The browser review for the Nexus and Data Lab flows remains pending because automatic approval review blocked navigation that could expose an Identity interaction URL. The dedicated Gmail IMAP login failed with an authentication error, so no mailbox message was read. Data Lab has not yet been submitted.

The isolated Production QA organization has ID `1a418a27-ca18-4228-bd01-c6fb6b1d9ce8`, scope `isolated-auth-qa`, and one active reviewer: `qa.nexus@anclora.local`. `qa.identity@anclora.local` is not a member of this organization, so approvals cannot be performed under that identity without a separately authorized membership change.
