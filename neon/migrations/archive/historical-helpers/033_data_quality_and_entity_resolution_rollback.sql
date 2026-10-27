-- Rollback: Data Quality and Entity Resolution
-- Feature ID: ANCLORA-DQER-001

-- Disable Realtime
ALTER PUBLICATION supabase_realtime DROP TABLE IF EXISTS public.dq_resolution_log;
ALTER PUBLICATION supabase_realtime DROP TABLE IF EXISTS public.dq_entity_candidates;
ALTER PUBLICATION supabase_realtime DROP TABLE IF EXISTS public.dq_quality_issues;

-- Drop Tables in reverse order
DROP TABLE IF EXISTS public.dq_resolution_log;
DROP TABLE IF EXISTS public.dq_entity_candidates;
DROP TABLE IF EXISTS public.dq_quality_issues;
