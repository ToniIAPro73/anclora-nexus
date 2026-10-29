# GuestHub insert-only intake — Spec v1

## Problem

The production `service_role` has `SELECT` and `INSERT` privileges on `access_requests`, but intentionally has no direct `UPDATE` or `DELETE` privileges. The GuestHub pilot handler inserted a pending request and then attempted a separate update, returning HTTP 500 after the request had already been persisted. Retries could therefore create a misleading error and another request row.

## Decision

Compute the final status and review metadata before inserting the access request. Do not perform a direct post-insert update. An idempotent replay returns the existing request without inserting another row. The existing task helper remains best-effort; production `service_role` has no grants on `tasks`, so it cannot create pilot review tasks.

## Acceptance criteria

1. A GuestHub request compatible with manual review is inserted once with `status=pending` and its review metadata.
2. The intake path does not call `UPDATE` on `access_requests`.
3. An idempotent retry of an existing pending request returns the existing row without inserting another request.
4. Auto-approval remains disabled for the production request flow.
5. No database migration or broadened `service_role` privilege is required for request persistence.
