-- ============================================================================
-- 026_currency_surface_localization_rollback.sql
-- Feature: ANCLORA-CSL-001
-- Description: Rollback for surface fields addition
-- ============================================================================

BEGIN;

-- 1. Drop constraints (optional if dropping columns, but good practice)
ALTER TABLE public.properties DROP CONSTRAINT IF EXISTS properties_useful_area_m2_non_neg;
ALTER TABLE public.properties DROP CONSTRAINT IF EXISTS properties_built_area_m2_non_neg;
ALTER TABLE public.properties DROP CONSTRAINT IF EXISTS properties_plot_area_m2_non_neg;
ALTER TABLE public.properties DROP CONSTRAINT IF EXISTS properties_useful_le_built;

-- 2. Drop columns
ALTER TABLE public.properties DROP COLUMN IF EXISTS useful_area_m2;
ALTER TABLE public.properties DROP COLUMN IF EXISTS built_area_m2;
ALTER TABLE public.properties DROP COLUMN IF EXISTS plot_area_m2;

COMMIT;
