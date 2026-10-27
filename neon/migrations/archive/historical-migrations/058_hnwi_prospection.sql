-- Migration: HNWI prospection support
-- Feature ID: ANCLORA-HNWI-001

BEGIN;

ALTER TABLE public.leads
ADD COLUMN IF NOT EXISTS nationality text,
ADD COLUMN IF NOT EXISTS zone_interest text,
ADD COLUMN IF NOT EXISTS qualification_score integer NOT NULL DEFAULT 0,
ADD COLUMN IF NOT EXISTS qualification_tier text NOT NULL DEFAULT 'cold',
ADD COLUMN IF NOT EXISTS hnwi_intent_signal text,
ADD COLUMN IF NOT EXISTS email_verified boolean NOT NULL DEFAULT false,
ADD COLUMN IF NOT EXISTS email_verification_source text,
ADD COLUMN IF NOT EXISTS hnwi_source_channel text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'check_leads_qualification_tier'
    ) THEN
        ALTER TABLE public.leads
        ADD CONSTRAINT check_leads_qualification_tier
        CHECK (qualification_tier IN ('hot', 'warm', 'cold'));
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_leads_org_qualification_tier
    ON public.leads (org_id, qualification_tier);
CREATE INDEX IF NOT EXISTS idx_leads_org_nationality
    ON public.leads (org_id, nationality);
CREATE INDEX IF NOT EXISTS idx_leads_org_email_verified
    ON public.leads (org_id, email_verified);

CREATE TABLE IF NOT EXISTS public.hnwi_prospection_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    lead_id uuid REFERENCES public.leads(id) ON DELETE SET NULL,
    connector_name text,
    trace_id text,
    event_type text NOT NULL,
    channel text,
    nationality text,
    qualification_tier text,
    score integer,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_hnwi_event_type CHECK (
        event_type IN ('detected', 'enriched', 'scored', 'ingested', 'email_prepared', 'contacted', 'qualified')
    ),
    CONSTRAINT chk_hnwi_event_tier CHECK (
        qualification_tier IS NULL OR qualification_tier IN ('hot', 'warm', 'cold')
    )
);

CREATE INDEX IF NOT EXISTS idx_hnwi_events_org_created
    ON public.hnwi_prospection_events (org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_hnwi_events_org_lead
    ON public.hnwi_prospection_events (org_id, lead_id);
CREATE INDEX IF NOT EXISTS idx_hnwi_events_trace
    ON public.hnwi_prospection_events (trace_id)
    WHERE trace_id IS NOT NULL;

COMMIT;
