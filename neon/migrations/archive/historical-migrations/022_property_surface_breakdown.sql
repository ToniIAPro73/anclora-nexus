-- ============================================================================
-- 022_property_surface_breakdown.sql
-- Purpose:
--   Add explicit surface breakdown fields to properties:
--   - useful_area_m2
--   - built_area_m2
--   - plot_area_m2
-- ============================================================================

BEGIN;

ALTER TABLE public.properties
  ADD COLUMN IF NOT EXISTS useful_area_m2 NUMERIC;

ALTER TABLE public.properties
  ADD COLUMN IF NOT EXISTS built_area_m2 NUMERIC;

ALTER TABLE public.properties
  ADD COLUMN IF NOT EXISTS plot_area_m2 NUMERIC;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'properties_useful_area_m2_non_negative'
  ) THEN
    ALTER TABLE public.properties
      ADD CONSTRAINT properties_useful_area_m2_non_negative
      CHECK (useful_area_m2 IS NULL OR useful_area_m2 >= 0);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'properties_built_area_m2_non_negative'
  ) THEN
    ALTER TABLE public.properties
      ADD CONSTRAINT properties_built_area_m2_non_negative
      CHECK (built_area_m2 IS NULL OR built_area_m2 >= 0);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'properties_plot_area_m2_non_negative'
  ) THEN
    ALTER TABLE public.properties
      ADD CONSTRAINT properties_plot_area_m2_non_negative
      CHECK (plot_area_m2 IS NULL OR plot_area_m2 >= 0);
  END IF;
END $$;

COMMIT;

