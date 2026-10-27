-- Feature: ANCLORA-MFO-001
-- Migration 034: Multichannel Feed Orchestrator v1.1 (persistence layer)
-- Creates persistent tables for channel configuration, feed runs and validation issues.

-- ─────────────────────────────────────────────────────────────────────────────
-- 1) Channel configuration per organization
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.feed_channel_configs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    channel             TEXT NOT NULL,
    format              TEXT NOT NULL CHECK (format IN ('xml', 'json')),
    is_enabled          BOOLEAN NOT NULL DEFAULT TRUE,
    max_items_per_run   INT NOT NULL DEFAULT 100 CHECK (max_items_per_run > 0 AND max_items_per_run <= 10000),
    rules_json          JSONB NOT NULL DEFAULT '{}'::JSONB,
    credentials_ref     TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (org_id, channel)
);

COMMENT ON TABLE public.feed_channel_configs IS
    'Per-organization channel configuration for multichannel feed publication.';

-- ─────────────────────────────────────────────────────────────────────────────
-- 2) Feed runs (publish / dry-run execution log)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.feed_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    channel             TEXT NOT NULL,
    format              TEXT NOT NULL CHECK (format IN ('xml', 'json')),
    run_mode            TEXT NOT NULL CHECK (run_mode IN ('dry_run', 'publish')),
    status              TEXT NOT NULL CHECK (status IN ('success', 'partial', 'failed')),
    total_candidates    INT NOT NULL DEFAULT 0 CHECK (total_candidates >= 0),
    ready_to_publish    INT NOT NULL DEFAULT 0 CHECK (ready_to_publish >= 0),
    published_count     INT NOT NULL DEFAULT 0 CHECK (published_count >= 0),
    rejected_count      INT NOT NULL DEFAULT 0 CHECK (rejected_count >= 0),
    warning_count       INT NOT NULL DEFAULT 0 CHECK (warning_count >= 0),
    error_count         INT NOT NULL DEFAULT 0 CHECK (error_count >= 0),
    sample_payload      JSONB NOT NULL DEFAULT '{}'::JSONB,
    notes               TEXT,
    triggered_by        UUID REFERENCES auth.users(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.feed_runs IS
    'Execution history for feed validation/publication by channel.';

-- ─────────────────────────────────────────────────────────────────────────────
-- 3) Validation issues per run/entity
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.feed_validation_issues (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    run_id              UUID REFERENCES public.feed_runs(id) ON DELETE CASCADE,
    channel             TEXT NOT NULL,
    entity_type         TEXT NOT NULL DEFAULT 'property',
    entity_id           UUID,
    field_name          TEXT NOT NULL,
    severity            TEXT NOT NULL CHECK (severity IN ('warning', 'error')),
    message             TEXT NOT NULL,
    metadata_json       JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.feed_validation_issues IS
    'Validation findings generated during feed runs.';

-- ─────────────────────────────────────────────────────────────────────────────
-- 4) Indexes
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_feed_configs_org_channel
    ON public.feed_channel_configs (org_id, channel);

CREATE INDEX IF NOT EXISTS idx_feed_runs_org_created
    ON public.feed_runs (org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_feed_runs_org_channel_created
    ON public.feed_runs (org_id, channel, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_feed_issues_org_channel
    ON public.feed_validation_issues (org_id, channel, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_feed_issues_run
    ON public.feed_validation_issues (run_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- 5) updated_at trigger for feed_channel_configs
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_feed_channel_configs_updated_at ON public.feed_channel_configs;
CREATE TRIGGER trg_feed_channel_configs_updated_at
BEFORE UPDATE ON public.feed_channel_configs
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ─────────────────────────────────────────────────────────────────────────────
-- 6) Seed default channel configs for all existing organizations
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO public.feed_channel_configs (org_id, channel, format, is_enabled, max_items_per_run)
SELECT o.id, cfg.channel, cfg.format, TRUE, 100
FROM public.organizations o
CROSS JOIN (
    VALUES
        ('idealista', 'xml'),
        ('fotocasa', 'xml'),
        ('rightmove', 'json'),
        ('kyero', 'json')
) AS cfg(channel, format)
ON CONFLICT (org_id, channel) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- 7) RLS
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.feed_channel_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.feed_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.feed_validation_issues ENABLE ROW LEVEL SECURITY;

-- Configs: owner/manager full access, agent read-only
DROP POLICY IF EXISTS feed_configs_select_all_members ON public.feed_channel_configs;
CREATE POLICY feed_configs_select_all_members ON public.feed_channel_configs
FOR SELECT USING (
    EXISTS (
        SELECT 1
        FROM public.organization_members om
        WHERE om.org_id = feed_channel_configs.org_id
          AND om.user_id = auth.uid()
          AND om.status = 'active'
    )
);

DROP POLICY IF EXISTS feed_configs_modify_owner_manager ON public.feed_channel_configs;
CREATE POLICY feed_configs_modify_owner_manager ON public.feed_channel_configs
FOR ALL USING (
    EXISTS (
        SELECT 1
        FROM public.organization_members om
        WHERE om.org_id = feed_channel_configs.org_id
          AND om.user_id = auth.uid()
          AND om.status = 'active'
          AND om.role IN ('owner', 'manager')
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM public.organization_members om
        WHERE om.org_id = feed_channel_configs.org_id
          AND om.user_id = auth.uid()
          AND om.status = 'active'
          AND om.role IN ('owner', 'manager')
    )
);

-- Runs: owner/manager full access, agent read-only
DROP POLICY IF EXISTS feed_runs_select_all_members ON public.feed_runs;
CREATE POLICY feed_runs_select_all_members ON public.feed_runs
FOR SELECT USING (
    EXISTS (
        SELECT 1
        FROM public.organization_members om
        WHERE om.org_id = feed_runs.org_id
          AND om.user_id = auth.uid()
          AND om.status = 'active'
    )
);

DROP POLICY IF EXISTS feed_runs_modify_owner_manager ON public.feed_runs;
CREATE POLICY feed_runs_modify_owner_manager ON public.feed_runs
FOR ALL USING (
    EXISTS (
        SELECT 1
        FROM public.organization_members om
        WHERE om.org_id = feed_runs.org_id
          AND om.user_id = auth.uid()
          AND om.status = 'active'
          AND om.role IN ('owner', 'manager')
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM public.organization_members om
        WHERE om.org_id = feed_runs.org_id
          AND om.user_id = auth.uid()
          AND om.status = 'active'
          AND om.role IN ('owner', 'manager')
    )
);

-- Validation issues: owner/manager full access, agent read-only
DROP POLICY IF EXISTS feed_issues_select_all_members ON public.feed_validation_issues;
CREATE POLICY feed_issues_select_all_members ON public.feed_validation_issues
FOR SELECT USING (
    EXISTS (
        SELECT 1
        FROM public.organization_members om
        WHERE om.org_id = feed_validation_issues.org_id
          AND om.user_id = auth.uid()
          AND om.status = 'active'
    )
);

DROP POLICY IF EXISTS feed_issues_modify_owner_manager ON public.feed_validation_issues;
CREATE POLICY feed_issues_modify_owner_manager ON public.feed_validation_issues
FOR ALL USING (
    EXISTS (
        SELECT 1
        FROM public.organization_members om
        WHERE om.org_id = feed_validation_issues.org_id
          AND om.user_id = auth.uid()
          AND om.status = 'active'
          AND om.role IN ('owner', 'manager')
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM public.organization_members om
        WHERE om.org_id = feed_validation_issues.org_id
          AND om.user_id = auth.uid()
          AND om.status = 'active'
          AND om.role IN ('owner', 'manager')
    )
);

-- ─────────────────────────────────────────────────────────────────────────────
-- 8) PostgREST schema reload
-- ─────────────────────────────────────────────────────────────────────────────
NOTIFY pgrst, 'reload schema';
