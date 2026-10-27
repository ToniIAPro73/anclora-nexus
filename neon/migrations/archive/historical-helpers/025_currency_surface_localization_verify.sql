-- ============================================================================
-- 025_currency_surface_localization_verify.sql
-- Feature: ANCLORA-CSL-001
-- Verification script
-- ============================================================================

-- 1. Check columns
SELECT column_name, data_type, numeric_precision, numeric_scale
FROM information_schema.columns
WHERE table_name = 'properties' 
  AND column_name IN ('useful_area_m2', 'built_area_m2', 'plot_area_m2');

-- 2. Check constraints
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'public.properties'::regclass
  AND conname IN (
    'properties_useful_area_m2_non_neg', 
    'properties_built_area_m2_non_neg', 
    'properties_plot_area_m2_non_neg',
    'properties_useful_le_built'
  );

-- 3. Check backfill quality (rows with surface_m2 but no built_area_m2)
SELECT count(*) as pending_backfill
FROM public.properties
WHERE surface_m2 IS NOT NULL AND built_area_m2 IS NULL;

-- 4. Sample data check
SELECT id, surface_m2, useful_area_m2, built_area_m2, plot_area_m2
FROM public.properties
WHERE surface_m2 IS NOT NULL
LIMIT 5;
