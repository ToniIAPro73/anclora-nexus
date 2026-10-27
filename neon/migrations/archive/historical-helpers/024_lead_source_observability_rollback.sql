-- MIGRATION ROLLBACK: 024_lead_source_observability_rollback.sql
-- Description: Revert changes from 023_lead_source_observability.sql
-- Feature ID: ANCLORA-LSO-001

-- 1. Drop indices
DROP INDEX IF EXISTS public.idx_leads_org_source_system;
DROP INDEX IF EXISTS public.idx_leads_org_source_channel;
DROP INDEX IF EXISTS public.idx_leads_org_captured_at;

-- 2. Drop constraints
ALTER TABLE public.leads
DROP CONSTRAINT IF EXISTS check_leads_source_system,
DROP CONSTRAINT IF EXISTS check_leads_source_channel,
DROP CONSTRAINT IF EXISTS check_leads_ingestion_mode;

-- 3. Drop columns
ALTER TABLE public.leads
DROP COLUMN IF EXISTS source_system,
DROP COLUMN IF EXISTS source_channel,
DROP COLUMN IF EXISTS source_campaign,
DROP COLUMN IF EXISTS source_detail,
DROP COLUMN IF EXISTS source_url,
DROP COLUMN IF EXISTS source_referrer,
DROP COLUMN IF EXISTS source_event_id,
DROP COLUMN IF EXISTS captured_at,
DROP COLUMN IF EXISTS ingestion_mode;
