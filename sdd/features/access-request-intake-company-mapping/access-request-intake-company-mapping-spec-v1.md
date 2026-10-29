# Access Request Intake Company Mapping — Spec v1

## Problem

The Data Lab and Synergi intake webhooks use `company_name` in their payload metadata, while Nexus `access_requests` stores the canonical field as `company`. Copying the payload key directly into the database insert causes PostgREST to reject the request and return HTTP 500.

## Decision

Normalize the intake-only `company_name` alias to the existing `company` database column before insertion. Preserve all other supported intake fields and allow an explicitly supplied `company` value to take precedence. Do not add a duplicate database column.

## Acceptance criteria

1. Intake payloads using `company_name` persist the value in `access_requests.company`.
2. No unsupported `company_name` column is sent to PostgREST.
3. Existing `company` values and other intake metadata remain unchanged.
4. The behavior is verified with a mocked database client; the test must not write to Production.
