-- ============================================================================
-- 022_property_origin_unification_verify.sql
-- Feature: ANCLORA-POU-001
-- Purpose:
--   Verify that the migration 020 was applied correctly.
-- ============================================================================

-- 1) Check for column existence
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'properties'
  AND column_name IN ('source_system', 'source_portal');

-- 2) Data counts by source_system
SELECT source_system, count(*) 
FROM public.properties 
GROUP BY 1 
ORDER BY 2 DESC;

-- 3) Check for invalid source_portal values (should be 0)
SELECT count(*) AS invalid_portals_count
FROM public.properties
WHERE source_portal NOT IN ('idealista', 'fotocasa', 'facebook', 'instagram', 'rightmove', 'kyero', 'other')
  AND source_portal IS NOT NULL;

-- 4) Verify constraints exist
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conname IN ('properties_source_system_check', 'properties_source_portal_check');

-- 5) Verify indexes exist
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'properties'
  AND indexname IN ('idx_properties_org_source_system', 'idx_properties_org_source_portal');
