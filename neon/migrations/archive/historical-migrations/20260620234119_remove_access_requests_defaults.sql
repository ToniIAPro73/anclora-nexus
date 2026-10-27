-- Migration: 20260620234119_remove_access_requests_defaults
-- Purpose: Final forward-only hardening for public.access_requests after all
--          active writers were verified to send explicit intake fields.
-- Scope: public.access_requests only.
--
-- This migration:
--   - does not drop columns;
--   - does not delete or mutate existing data;
--   - does not modify the domain CHECK constraints already applied;
--   - does not touch leads, valuation_requests, DMS, AML, signature flows,
--     or historical migrations.
--
-- Operational rule: apply manually once, only after the Supabase Cloud backup
-- gate documented in docs/release/access-requests-final-hardening-runbook.md.

BEGIN;

-- Abort before DDL if any existing row would violate the final required fields.
DO $$
DECLARE
  null_count integer;
BEGIN
  SELECT COUNT(*) INTO null_count
  FROM public.access_requests
  WHERE product IS NULL
     OR source IS NULL
     OR request_type IS NULL
     OR routing_target_domain IS NULL;

  IF null_count > 0 THEN
    RAISE EXCEPTION
      'MIGRATION ABORTED: % access_requests rows have required-field NULLs.',
      null_count;
  END IF;
END $$;

-- Remove legacy SyncXML database defaults. Writers must provide explicit values.
ALTER TABLE public.access_requests
  ALTER COLUMN product DROP DEFAULT,
  ALTER COLUMN source DROP DEFAULT;

-- Make the remaining intake routing fields mandatory.
ALTER TABLE public.access_requests
  ALTER COLUMN request_type SET NOT NULL,
  ALTER COLUMN routing_target_domain SET NOT NULL;

COMMIT;
