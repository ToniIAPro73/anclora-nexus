# Nexus isolated QA intake plan

1. Add independent GuestHub/Data Lab QA credentials, applicant allowlists, and organization IDs.
2. Add dedicated server-to-server routes that hard-code product/source/scope, persist the server-owned QA marker, and fail before write when configuration is missing.
3. Reuse `access_requests.org_id` for reviewer read/decision/audit isolation; pass the marker to Identity provisioning as role `qa`.
4. Test separate-key authentication, namespace selection, allowlist enforcement, fail-closed behavior, and ordinary route compatibility.
5. Configure QA organizations and reviewer memberships only through governed Nexus operations; no production data mutation or approval in this local task.
