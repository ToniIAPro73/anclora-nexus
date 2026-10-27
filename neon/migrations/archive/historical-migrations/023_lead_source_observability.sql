-- MIGRATION: 023_lead_source_observability.sql
-- Description: Add comprehensive lead source tracking to the leads table.
-- Feature ID: ANCLORA-LSO-001

-- 1. Añadir columnas nuevas en leads
ALTER TABLE public.leads
ADD COLUMN source_system text DEFAULT 'manual',
ADD COLUMN source_channel text DEFAULT 'other',
ADD COLUMN source_campaign text,
ADD COLUMN source_detail text,
ADD COLUMN source_url text,
ADD COLUMN source_referrer text,
ADD COLUMN source_event_id text,
ADD COLUMN captured_at timestamptz DEFAULT now(),
ADD COLUMN ingestion_mode text DEFAULT 'manual';

-- 2. Añadir CHECKS de dominio
ALTER TABLE public.leads
ADD CONSTRAINT check_leads_source_system 
CHECK (source_system IN ('manual', 'cta_web', 'import', 'referral', 'partner', 'social')),
ADD CONSTRAINT check_leads_source_channel 
CHECK (source_channel IN ('website', 'linkedin', 'instagram', 'facebook', 'email', 'phone', 'other')),
ADD CONSTRAINT check_leads_ingestion_mode 
CHECK (ingestion_mode IN ('realtime', 'batch', 'manual'));

-- 3. Índices de rendimiento y observabilidad
CREATE INDEX idx_leads_org_source_system ON public.leads (org_id, source_system);
CREATE INDEX idx_leads_org_source_channel ON public.leads (org_id, source_channel);
CREATE INDEX idx_leads_org_captured_at ON public.leads (org_id, captured_at DESC);

-- 4. Backfill mínimo desde columna legacy 'source'
-- Mapear linkedin -> linkedin, web -> website, resto -> other
UPDATE public.leads
SET source_channel = CASE 
    WHEN source ILIKE '%linkedin%' THEN 'linkedin'
    WHEN source ILIKE '%web%' THEN 'website'
    ELSE 'other'
END,
source_system = 'manual',
ingestion_mode = 'manual',
captured_at = created_at;

-- Comentario para documentación
COMMENT ON COLUMN public.leads.source_system IS 'Sistema de origen: manual, web, import, etc.';
COMMENT ON COLUMN public.leads.source_channel IS 'Canal de origen: linkedin, website, etc.';
COMMENT ON COLUMN public.leads.ingestion_mode IS 'Modo de ingesta: realtime, batch, manual.';
