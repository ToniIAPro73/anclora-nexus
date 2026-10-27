-- Rollback: Source Connectors Unified Ingestion
-- Feature ID: ANCLORA-SCUI-001

-- Disable Realtime
ALTER PUBLICATION supabase_realtime DROP TABLE IF EXISTS public.ingestion_events;

-- Drop Tables
DROP TABLE IF EXISTS public.ingestion_events;
DROP TABLE IF EXISTS public.ingestion_connectors;
