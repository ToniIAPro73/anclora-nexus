-- Migration: lead outreach interactions
-- Feature ID: ANCLORA-HNWI-001

BEGIN;

CREATE TABLE IF NOT EXISTS public.lead_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    lead_id UUID NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL CHECK (tipo IN ('email', 'note', 'lead_brief', 'email_draft')),
    contenido TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'realizado' CHECK (estado IN ('programado', 'realizado')),
    resultado TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lead_interactions_lead_created
    ON public.lead_interactions (org_id, lead_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_lead_interactions_tipo
    ON public.lead_interactions (org_id, lead_id, tipo, created_at DESC);

ALTER TABLE public.lead_interactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "org_isolation_lead_interactions"
    ON public.lead_interactions
    USING (org_id = current_setting('app.org_id', true)::UUID);

COMMENT ON TABLE public.lead_interactions IS
    'Lead-side supervised outreach interactions, briefs and email drafts for HNWI prospection.';

COMMIT;
