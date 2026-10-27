-- Migration: 20260620120000_access_requests_access_only_constraints
-- Purpose: Enforce that access_requests table only stores access domain entries.
-- Direction: forward-only. No destructive rollback. Create 20260621* to undo if needed.
-- PRECONDITION: Run preflight queries before applying in staging/production.
-- DO NOT apply to production without: backup, staging validation, PRODUCTION_BACKUP_GATE=PASS

BEGIN;

-- Precondition check: abort if any rows would violate new constraints
DO $$
DECLARE
  invalid_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO invalid_count
  FROM public.access_requests
  WHERE source NOT IN ('syncxml_landing', 'synergi_app', 'data_lab_app', 'nexus_manual', 'external_api')
     OR product NOT IN ('syncxml', 'synergi', 'data_lab')
     OR intake_domain IS DISTINCT FROM 'access_request'
     OR request_type NOT IN ('pilot_request', 'access_request', 'partner_admission', 'workspace_access_request')
     OR routing_target_domain IS DISTINCT FROM 'access_requests';

  IF invalid_count > 0 THEN
    RAISE EXCEPTION 'MIGRATION ABORTED: % rows would violate new constraints. Run preflight and fix data first.', invalid_count;
  END IF;
END $$;

-- Drop any legacy or previously-created constraints (idempotent)
ALTER TABLE public.access_requests
  DROP CONSTRAINT IF EXISTS access_requests_source_check,
  DROP CONSTRAINT IF EXISTS access_requests_product_check,
  DROP CONSTRAINT IF EXISTS access_requests_intake_domain_check,
  DROP CONSTRAINT IF EXISTS access_requests_request_type_check,
  DROP CONSTRAINT IF EXISTS access_requests_routing_target_domain_check,
  DROP CONSTRAINT IF EXISTS access_requests_service_interest_check,
  DROP CONSTRAINT IF EXISTS check_source_product_coherence;

-- Enforce access-only sources
ALTER TABLE public.access_requests
  ADD CONSTRAINT access_requests_source_check
  CHECK (source IN ('syncxml_landing', 'synergi_app', 'data_lab_app', 'nexus_manual', 'external_api'));

-- Enforce access-only products
ALTER TABLE public.access_requests
  ADD CONSTRAINT access_requests_product_check
  CHECK (product IN ('syncxml', 'synergi', 'data_lab'));

-- Enforce access domain only
ALTER TABLE public.access_requests
  ADD CONSTRAINT access_requests_intake_domain_check
  CHECK (intake_domain = 'access_request');

-- Enforce access routing only
ALTER TABLE public.access_requests
  ADD CONSTRAINT access_requests_routing_target_domain_check
  CHECK (routing_target_domain = 'access_requests');

-- Service interest must be null for access requests
ALTER TABLE public.access_requests
  ADD CONSTRAINT access_requests_service_interest_check
  CHECK (service_interest IS NULL);

-- Enforce valid request types for access domain
ALTER TABLE public.access_requests
  ADD CONSTRAINT access_requests_request_type_check
  CHECK (request_type IN ('pilot_request', 'access_request', 'partner_admission', 'workspace_access_request'));

-- Enforce source-product coherence (deterministic mapping)
ALTER TABLE public.access_requests
  ADD CONSTRAINT check_source_product_coherence
  CHECK (
    (source = 'syncxml_landing'  AND product = 'syncxml') OR
    (source = 'synergi_app'      AND product = 'synergi') OR
    (source = 'data_lab_app'     AND product = 'data_lab') OR
    (source IN ('nexus_manual', 'external_api') AND product IN ('syncxml', 'synergi', 'data_lab'))
  );

-- NOTE: NOT removing DEFAULT values for product/source in this migration.
-- Reason: Requires confirmation that all active producers send explicit values.
-- To remove defaults, create migration 20260621*_remove_access_requests_defaults.sql
-- after verifying 100% of producers send explicit source and product.

-- Verification query (informational — included in migration log)
DO $$
DECLARE
  constraint_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO constraint_count
  FROM pg_constraint
  WHERE conrelid = 'public.access_requests'::regclass
    AND conname IN (
      'access_requests_source_check',
      'access_requests_product_check',
      'access_requests_intake_domain_check',
      'access_requests_routing_target_domain_check',
      'access_requests_service_interest_check',
      'access_requests_request_type_check',
      'check_source_product_coherence'
    );
  RAISE NOTICE 'Migration complete. % of 7 expected constraints now active.', constraint_count;
END $$;

COMMIT;
