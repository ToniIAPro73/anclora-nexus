# ANCLORA-ARRP-001 — Atomic access request review persistence

Status: Draft  
Scope: Nexus access-request review and audit persistence

## Problem

The production `service_role` is intentionally restricted to `SELECT` and `INSERT` on `access_requests` and has no direct privileges on `audit_log`. The review service currently calls Anclora Identity before it updates the request, and its lifecycle views query `audit_log` directly. This can grant an application membership before Nexus can persist the decision, while the review UI reports audit permission errors.

## Goal

Make approvals and rejections durable and auditable before any external provisioning side effect. Preserve the least-privilege contract: the API role must not receive direct `UPDATE` or `DELETE` on `access_requests`, nor direct `SELECT` or `INSERT` on `audit_log`.

## Design

- Add narrowly scoped, `SECURITY DEFINER` PostgreSQL functions for access-request decisions, provisioning-result persistence, access-request audit writes, and scoped audit reads.
- Revoke function execution from `PUBLIC`; grant execution only to `service_role`.
- Scope every function by organization and request ID, enforce pending/approved transitions, and constrain audit actions to the access-request namespace.
- Persist an approved decision and its audit event atomically before calling Anclora Identity.
- Persist the provisioning result and its audit event atomically after the Identity call. A provisioning failure remains an approved request with a recorded failure that can be retried.
- Route access-request analytics, SLA reads, lifecycle reads, retries, and audit writes through those functions.
- Keep the existing direct table grants unchanged.

## Acceptance criteria

1. A failed decision persistence causes no Identity provisioning call.
2. A successful approval is durably recorded and audited before Identity provisioning starts.
3. The provisioning outcome and corresponding audit event persist atomically.
4. Rejection, email retries, lifecycle reads, analytics reads, and SLA audit reads/writes work through scoped RPCs.
5. Duplicate or stale decisions fail without provisioning.
6. `service_role` still has no direct `UPDATE`/`DELETE` on `access_requests` and no direct `SELECT`/`INSERT` on `audit_log`.
7. SQL functions are executable only by `service_role` and enforce organization/request scoping.

## Out of scope

- Applying the migration to the production branch.
- Changing Identity membership or invitation policy.
- Changing reviewer authentication or approval UI behavior.
- Deleting or modifying existing audit records.
