-- ============================================================================
-- 020_property_origin_unification.sql
-- Feature: ANCLORA-POU-001
-- Purpose:
--   1) Add normalized source fields to properties.
--   2) Backfill from legacy notes payload where available.
--   3) Enforce basic domain constraints and add useful indexes.
-- ============================================================================

BEGIN;

-- 1) Add columns (idempotent)
ALTER TABLE public.properties
  ADD COLUMN IF NOT EXISTS source_system TEXT;

ALTER TABLE public.properties
  ADD COLUMN IF NOT EXISTS source_portal TEXT;

-- 2) Backfill logic from notes JSONB
-- Prioritize source_system from notes if available
UPDATE public.properties
SET
  source_system = COALESCE(source_system, NULLIF(lower(notes->>'source_system'), '')),
  source_portal = COALESCE(source_portal, NULLIF(lower(notes->>'source_portal'), ''))
WHERE notes IS NOT NULL;

-- 3) Normalize source_system (default/fallback)
UPDATE public.properties
SET source_system = 'manual'
WHERE source_system IS NULL
   OR source_system NOT IN ('manual', 'widget', 'pbm');

-- 4) Normalize source_portal values
UPDATE public.properties
SET source_portal = CASE
  WHEN source_portal IS NULL OR trim(source_portal) = '' THEN NULL
  WHEN lower(trim(source_portal)) IN ('idealista', 'fotocasa', 'facebook', 'instagram', 'rightmove', 'kyero', 'other') THEN lower(trim(source_portal))
  ELSE 'other'
END;

-- 5) Set NOT NULL + default for source_system
ALTER TABLE public.properties
  ALTER COLUMN source_system SET DEFAULT 'manual';

ALTER TABLE public.properties
  ALTER COLUMN source_system SET NOT NULL;

-- 6) Add constraints (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'properties_source_system_check'
  ) THEN
    ALTER TABLE public.properties
      ADD CONSTRAINT properties_source_system_check
      CHECK (source_system IN ('manual', 'widget', 'pbm'));
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'properties_source_portal_check'
  ) THEN
    ALTER TABLE public.properties
      ADD CONSTRAINT properties_source_portal_check
      CHECK (
        source_portal IS NULL
        OR source_portal IN ('idealista', 'fotocasa', 'facebook', 'instagram', 'rightmove', 'kyero', 'other')
      );
  END IF;
END$$;

-- 7) Indexes for performance
CREATE INDEX IF NOT EXISTS idx_properties_org_source_system
  ON public.properties (org_id, source_system);

CREATE INDEX IF NOT EXISTS idx_properties_org_source_portal
  ON public.properties (org_id, source_portal);

COMMIT;

