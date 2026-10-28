# Data Lab Internal Webhook Credential Scope — Spec v1

## Problem

Data Lab access requests must be delivered to Nexus without requiring a public CAPTCHA challenge, but the existing internal webhook dependency accepts the GuestHub credential. Reusing that credential would couple product integrations and prevent independent rotation.

## Decision

Add `DATA_LAB_WEBHOOK_SECRET` as a dedicated service credential. Accept it only on `POST /api/internal/webhooks/data-lab-access`. Preserve the existing shared `NEXUS_INTERNAL_API_KEY` as an optional compatibility credential, and keep GuestHub and other internal routes on their current accepted keys.

The endpoint continues to persist through the idempotent Nexus access-request intake path and returns the canonical request ID.

## Acceptance criteria

1. A valid dedicated Data Lab credential accepts the Data Lab route.
2. The Data Lab credential alone is rejected by GuestHub's pilot route.
3. Existing GuestHub and shared Nexus-key behavior remains compatible.
4. The secret is read from protected runtime configuration and never logged or committed.
5. Route tests mock persistence and do not write to Production.

## Verification

Run only the focused internal webhook route tests and inspect the scoped diff.
