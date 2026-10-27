-- ============================================================================
-- 025_currency_surface_localization.sql
-- Feature: ANCLORA-CSL-001
-- Description: Add useful, built and plot area fields to public.properties
-- ============================================================================

BEGIN;

-- 1. Add columns
ALTER TABLE public.properties
  ADD COLUMN IF NOT EXISTS useful_area_m2 NUMERIC(12,2),
  ADD COLUMN IF NOT EXISTS built_area_m2 NUMERIC(12,2),
  ADD COLUMN IF NOT EXISTS plot_area_m2 NUMERIC(12,2);

-- 2. Add non-negative constraints
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'properties_useful_area_m2_non_neg') THEN
        ALTER TABLE public.properties ADD CONSTRAINT properties_useful_area_m2_non_neg CHECK (useful_area_m2 >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'properties_built_area_m2_non_neg') THEN
        ALTER TABLE public.properties ADD CONSTRAINT properties_built_area_m2_non_neg CHECK (built_area_m2 >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'properties_plot_area_m2_non_neg') THEN
        ALTER TABLE public.properties ADD CONSTRAINT properties_plot_area_m2_non_neg CHECK (plot_area_m2 >= 0);
    END IF;
END $$;

-- 3. Add logical constraint: useful <= built
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'properties_useful_le_built') THEN
        ALTER TABLE public.properties ADD CONSTRAINT properties_useful_le_built CHECK (useful_area_m2 <= built_area_m2);
    END IF;
END $$;

-- 4. Backfill from legacy surface_m2
-- We only update if built_area_m2 is null to avoid overwriting existing data if migration is re-run
WITH updated AS (
    UPDATE public.properties
    SET 
        built_area_m2 = COALESCE(built_area_m2, surface_m2),
        useful_area_m2 = COALESCE(useful_area_m2, surface_m2)
    WHERE built_area_m2 IS NULL AND surface_m2 IS NOT NULL
    RETURNING 1
)
SELECT count(*) as updated_rows FROM updated;

COMMIT;
