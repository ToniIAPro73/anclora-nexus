# Isolated GuestHub and Data Lab QA intake

## Goal

Keep QA requests and approval decisions inside a dedicated Nexus organization and provision least-privilege QA memberships through Anclora Identity.

## Requirements

1. GuestHub and Data Lab use separate server-to-server QA credentials and server-owned product/scope markers. Both may target the verified isolated Nexus QA organization; requests remain product-distinguishable and every list/decision is constrained to the reviewer's organization.
2. Dedicated QA intake routes derive organization, product, source, and QA scope on the server. They ignore/reject client attempts to set scope or organization.
3. Missing organization or credential configuration fails closed before database writes. Existing production intake routes keep their current routing.
4. The existing `org_id` boundary scopes list, detail, decisions, lifecycle, and audit queries; QA reviewer authorization must resolve to the QA organization.
5. The server-owned QA marker is persisted in request metadata and causes approved provisioning to request the Identity `qa` role.
6. Normal intake can never set the QA marker, and QA requests cannot be reviewed from another organization.

## Acceptance

- Unit tests prove normal intake cannot set QA scope, each QA route chooses only its configured org, and missing settings fail before persistence.
- Tests prove request lookup/approval remains org-scoped and QA provisioning requests the least-privilege role.
- No production migration or data write occurs as part of local development verification.
