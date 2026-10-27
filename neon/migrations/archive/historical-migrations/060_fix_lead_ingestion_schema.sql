-- MIGRATION: 060_fix_lead_ingestion_schema.sql
-- Description: Fix missing columns in leads table to match LeadIngestionPayload
-- Feature ID: n8n-unified-lead-intake

-- 1. Añadir columnas de consentimiento GDPR
ALTER TABLE public.leads
ADD COLUMN IF NOT EXISTS gdpr_consent boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS gdpr_consent_at timestamptz,
ADD COLUMN IF NOT EXISTS gdpr_consent_text_version text;

-- 2. Añadir columnas de calificación
ALTER TABLE public.leads
ADD COLUMN IF NOT EXISTS qualification_score integer CHECK (qualification_score >= 0 AND qualification_score <= 100),
ADD COLUMN IF NOT EXISTS qualification_tier text CHECK (qualification_tier IN ('hot', 'warm', 'cold')),
ADD COLUMN IF NOT EXISTS hnwi_intent_signal text,
ADD COLUMN IF NOT EXISTS hnwi_source_channel text;

-- 3. Añadir columnas de verificación y trazabilidad
ALTER TABLE public.leads
ADD COLUMN IF NOT EXISTS email_verified boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS email_verification_source text,
ADD COLUMN IF NOT EXISTS connector_name text,
ADD COLUMN IF NOT EXISTS trace_id text;

-- 4. Índices para calificación
CREATE INDEX IF NOT EXISTS idx_leads_qualification_tier ON public.leads (qualification_tier);
CREATE INDEX IF NOT EXISTS idx_leads_qualification_score ON public.leads (qualification_score);

-- Comentarios para documentación
COMMENT ON COLUMN public.leads.gdpr_consent IS 'Indica si el lead ha dado su consentimiento GDPR';
COMMENT ON COLUMN public.leads.qualification_tier IS 'Nivel de calificación del lead: hot, warm, cold';
COMMENT ON COLUMN public.leads.connector_name IS 'Nombre del conector que originó la ingesta';
