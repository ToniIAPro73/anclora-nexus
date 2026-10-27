-- Migration: Data Quality and Entity Resolution
-- Feature ID: ANCLORA-DQER-001
-- Dependencies: 002_core_schema.sql (organizations), 004_anclora_schema.sql (leads, properties)

-- 1. Table: dq_quality_issues
CREATE TABLE IF NOT EXISTS public.dq_quality_issues (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    entity_type text NOT NULL CHECK (entity_type IN ('lead', 'property')),
    entity_id uuid NOT NULL,
    issue_type text NOT NULL CHECK (issue_type IN ('missing_field', 'invalid_format', 'inconsistent_value', 'duplicate_candidate')),
    severity text NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    issue_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_review', 'resolved', 'ignored')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Indices for dq_quality_issues
CREATE INDEX IF NOT EXISTS idx_dq_quality_issues_org_entity_status ON public.dq_quality_issues (org_id, entity_type, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dq_quality_issues_org_severity_status ON public.dq_quality_issues (org_id, severity, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dq_quality_issues_entity_lookup ON public.dq_quality_issues (entity_type, entity_id);

-- 2. Table: dq_entity_candidates
CREATE TABLE IF NOT EXISTS public.dq_entity_candidates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    entity_type text NOT NULL CHECK (entity_type IN ('lead', 'property')),
    left_entity_id uuid NOT NULL,
    right_entity_id uuid NOT NULL,
    similarity_score numeric(5,2) NOT NULL CHECK (similarity_score >= 0 AND similarity_score <= 100),
    signals jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'suggested_merge' CHECK (status IN ('auto_link', 'suggested_merge', 'approved_merge', 'rejected_merge')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT dq_entity_candidates_no_self_match CHECK (left_entity_id <> right_entity_id),
    UNIQUE (org_id, entity_type, left_entity_id, right_entity_id)
);

-- Indices for dq_entity_candidates
CREATE INDEX IF NOT EXISTS idx_dq_entity_candidates_org_status_similarity ON public.dq_entity_candidates (org_id, entity_type, status, similarity_score DESC);

-- 3. Table: dq_resolution_log
CREATE TABLE IF NOT EXISTS public.dq_resolution_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    entity_type text NOT NULL CHECK (entity_type IN ('lead', 'property')),
    candidate_id uuid REFERENCES public.dq_entity_candidates(id) ON DELETE SET NULL,
    action text NOT NULL CHECK (action IN ('approve_merge', 'reject_merge', 'mark_duplicate', 'undo_merge')),
    actor_user_id uuid, -- Optional link to users table if available
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Indices for dq_resolution_log
CREATE INDEX IF NOT EXISTS idx_dq_resolution_log_org_entity_date ON public.dq_resolution_log (org_id, entity_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dq_resolution_log_candidate ON public.dq_resolution_log (candidate_id);

-- Enable Realtime for DQ tables
ALTER PUBLICATION supabase_realtime ADD TABLE public.dq_quality_issues;
ALTER PUBLICATION supabase_realtime ADD TABLE public.dq_entity_candidates;
ALTER PUBLICATION supabase_realtime ADD TABLE public.dq_resolution_log;

-- Updated at triggers if needed (assuming a common function exists)
-- DO $$ BEGIN
--     CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.dq_quality_issues FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
--     CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.dq_entity_candidates FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
-- EXCEPTION WHEN others THEN NULL; END $$;
