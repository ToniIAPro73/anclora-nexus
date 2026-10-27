-- ============================================================
-- 027_cost_governance_foundation.sql
-- Feature: ANCLORA-CGF-001 Cost Governance Foundation
-- Purpose: Schema for organization budget, usage tracking, and alerts
-- ============================================================

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Organization Cost Policies
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS org_cost_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    monthly_budget_eur NUMERIC(14,2) NOT NULL DEFAULT 0,
    warning_threshold_pct NUMERIC(5,2) NOT NULL DEFAULT 80,
    hard_stop_threshold_pct NUMERIC(5,2) NOT NULL DEFAULT 100,
    hard_stop_enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    CONSTRAINT uq_org_cost_policies_org_id UNIQUE (org_id),
    CONSTRAINT chk_monthly_budget_positive CHECK (monthly_budget_eur >= 0),
    CONSTRAINT chk_warning_threshold_range CHECK (warning_threshold_pct BETWEEN 1 AND 100),
    CONSTRAINT chk_hard_stop_threshold_range CHECK (hard_stop_threshold_pct BETWEEN warning_threshold_pct AND 200)
);

COMMENT ON TABLE org_cost_policies IS 'Budget configuration and thresholds per organization';

-- RLS
ALTER TABLE org_cost_policies ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'org_cost_policies' AND policyname = 'org_cost_policies_select_members'
    ) THEN
        CREATE POLICY "org_cost_policies_select_members" ON org_cost_policies
            FOR SELECT
            USING (
                org_id IN (
                    SELECT org_id FROM organization_members
                    WHERE user_id = auth.uid()
                    AND status = 'active'
                )
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'org_cost_policies' AND policyname = 'org_cost_policies_update_owners_managers'
    ) THEN
        CREATE POLICY "org_cost_policies_update_owners_managers" ON org_cost_policies
            FOR UPDATE
            USING (
                org_id IN (
                    SELECT org_id FROM organization_members
                    WHERE user_id = auth.uid()
                    AND status = 'active'
                    AND role IN ('owner', 'manager')
                )
            )
            WITH CHECK (
                org_id IN (
                    SELECT org_id FROM organization_members
                    WHERE user_id = auth.uid()
                    AND status = 'active'
                    AND role IN ('owner', 'manager')
                )
            );
    END IF;
END
$$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Organization Cost Usage Events
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS org_cost_usage_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    capability_code TEXT NOT NULL,
    provider TEXT,
    units NUMERIC(14,4) NOT NULL DEFAULT 0,
    cost_eur NUMERIC(14,6) NOT NULL DEFAULT 0,
    trace_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_units_positive CHECK (units >= 0),
    CONSTRAINT chk_cost_eur_positive CHECK (cost_eur >= 0)
    -- capability_code enum check omitted for flexibility as per spec
);

COMMENT ON TABLE org_cost_usage_events IS 'Immutable log of consumption events by capability';

-- Indices
CREATE INDEX IF NOT EXISTS idx_org_cost_usage_org_created ON org_cost_usage_events(org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_org_cost_usage_org_cap_created ON org_cost_usage_events(org_id, capability_code, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_org_cost_usage_trace_id ON org_cost_usage_events(trace_id) WHERE trace_id IS NOT NULL;

-- RLS
ALTER TABLE org_cost_usage_events ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'org_cost_usage_events' AND policyname = 'org_cost_usage_events_select_members'
    ) THEN
        CREATE POLICY "org_cost_usage_events_select_members" ON org_cost_usage_events
            FOR SELECT
            USING (
                org_id IN (
                    SELECT org_id FROM organization_members
                    WHERE user_id = auth.uid()
                    AND status = 'active'
                )
            );
    END IF;
END
$$;

-- Insert by Service Role only (implied, no explicit policy needed for auth users)

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Organization Cost Alerts
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS org_cost_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    alert_type TEXT NOT NULL CHECK (alert_type IN ('warning', 'hard_stop', 'recovered')),
    month_key TEXT NOT NULL, -- Format YYYY-MM
    threshold_pct NUMERIC(5,2) NOT NULL,
    current_pct NUMERIC(8,2) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

COMMENT ON TABLE org_cost_alerts IS 'Active and historical budget alerts';

-- Unique constraint for active alerts
CREATE UNIQUE INDEX IF NOT EXISTS uq_org_cost_alerts_active 
    ON org_cost_alerts(org_id, alert_type, month_key) 
    WHERE is_active = true;

-- RLS
ALTER TABLE org_cost_alerts ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'org_cost_alerts' AND policyname = 'org_cost_alerts_select_members'
    ) THEN
        CREATE POLICY "org_cost_alerts_select_members" ON org_cost_alerts
            FOR SELECT
            USING (
                org_id IN (
                    SELECT org_id FROM organization_members
                    WHERE user_id = auth.uid()
                    AND status = 'active'
                )
            );
    END IF;
END
$$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. Backfill
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO org_cost_policies (org_id, monthly_budget_eur, warning_threshold_pct, hard_stop_threshold_pct, hard_stop_enabled)
SELECT 
    id, 
    250.00, 
    80, 
    100, 
    true
FROM organizations
ON CONFLICT (org_id) DO NOTHING;

COMMIT;
