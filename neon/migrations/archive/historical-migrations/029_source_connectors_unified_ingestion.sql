-- Migration: Source Connectors Unified Ingestion
-- Feature ID: ANCLORA-SCUI-001

-- 1) ingestion_connectors
CREATE TABLE IF NOT EXISTS public.ingestion_connectors (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    connector_name text NOT NULL,
    entity_type text NOT NULL CHECK (entity_type IN ('lead', 'property')),
    source_system text NOT NULL,
    source_channel text,
    is_enabled boolean NOT NULL DEFAULT true,
    config jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (org_id, connector_name, entity_type)
);

-- 2) ingestion_events
CREATE TABLE IF NOT EXISTS public.ingestion_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    connector_name text NOT NULL,
    entity_type text NOT NULL CHECK (entity_type IN ('lead', 'property')),
    external_id text NOT NULL,
    dedupe_key text NOT NULL,
    status text NOT NULL CHECK (status IN ('received', 'validated', 'processed', 'rejected', 'failed')),
    error_code text,
    error_message text,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    trace_id text,
    processed_entity_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    processed_at timestamptz,
    UNIQUE (org_id, dedupe_key)
);

-- Indices
CREATE INDEX IF NOT EXISTS idx_ingestion_events_org_created ON public.ingestion_events (org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ingestion_events_org_status_created ON public.ingestion_events (org_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ingestion_events_org_connector_created ON public.ingestion_events (org_id, connector_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ingestion_events_trace_id ON public.ingestion_events (trace_id) WHERE trace_id IS NOT NULL;

-- Enable Realtime
ALTER PUBLICATION supabase_realtime ADD TABLE public.ingestion_events;

-- RLS (Basic)
ALTER TABLE public.ingestion_connectors ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ingestion_events ENABLE ROW LEVEL SECURITY;

-- Note: In v0, single-tenant with fixed org_id is assumed, 
-- but we add the policy for future-proofing and consistency with current workspace rules.
CREATE POLICY "Allow all on ingestion_connectors" ON public.ingestion_connectors FOR ALL USING (true);
CREATE POLICY "Allow all on ingestion_events" ON public.ingestion_events FOR ALL USING (true);
