-- ============================================================================
-- 021_property_origin_unification_rollback.sql
-- Feature: ANCLORA-POU-001
-- Purpose:
--   Roll back source-system unification changes on properties table.
-- ============================================================================

BEGIN;

-- Drop indexes first
DROP INDEX IF EXISTS public.idx_properties_org_source_portal;
DROP INDEX IF EXISTS public.idx_properties_org_source_system;

-- Drop constraints
ALTER TABLE public.properties
  DROP CONSTRAINT IF EXISTS properties_source_portal_check;

ALTER TABLE public.properties
  DROP CONSTRAINT IF EXISTS properties_source_system_check;

-- Drop columns
ALTER TABLE public.properties
  DROP COLUMN IF EXISTS source_portal;

ALTER TABLE public.properties
  DROP COLUMN IF EXISTS source_system;

COMMIT;

