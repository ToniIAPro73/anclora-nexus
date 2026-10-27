-- 073_leads_pipeline.sql
-- Creates the leads pipeline table for the commercial loop (Phase 3).
-- Supports lead intake from external sources with temperature scoring,
-- deduplication, and staleness detection (Requirements 13, 14).

CREATE TABLE IF NOT EXISTS public.leads_pipeline (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL,
    contact_name TEXT NOT NULL,
    contact_email TEXT,
    contact_phone TEXT,
    source_system TEXT NOT NULL,
    source_channel TEXT NOT NULL,
    temperature TEXT NOT NULL DEFAULT 'cold' CHECK (temperature IN ('cold', 'warm', 'hot')),
    assigned_owner UUID,
    next_action TEXT,
    next_action_due TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'contacted', 'qualified', 'converted', 'lost', 'stale')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB,
    UNIQUE(org_id, contact_email, source_system)
);

CREATE INDEX IF NOT EXISTS idx_leads_pipeline_temperature
    ON public.leads_pipeline(org_id, temperature);

CREATE INDEX IF NOT EXISTS idx_leads_pipeline_stale
    ON public.leads_pipeline(org_id, status, next_action_due)
    WHERE status NOT IN ('converted', 'lost');
