-- ══════════════════════════════════════════════════════════════════════════════
-- Migration 018: Prospection & Buyer Matching v1 — Indexes, Constraints & Triggers
-- Feature: ANCLORA-PBM-001
-- ══════════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. CHECK Constraints — Score ranges [0, 100]
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE prospected_properties
    ADD CONSTRAINT chk_high_ticket_score_range
    CHECK (high_ticket_score IS NULL OR (high_ticket_score >= 0 AND high_ticket_score <= 100));

ALTER TABLE buyer_profiles
    ADD CONSTRAINT chk_motivation_score_range
    CHECK (motivation_score IS NULL OR (motivation_score >= 0 AND motivation_score <= 100));

ALTER TABLE property_buyer_matches
    ADD CONSTRAINT chk_match_score_range
    CHECK (match_score >= 0 AND match_score <= 100);

-- Budget consistency
ALTER TABLE buyer_profiles
    ADD CONSTRAINT chk_budget_consistency
    CHECK (budget_min IS NULL OR budget_max IS NULL OR budget_min <= budget_max);

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Performance Indexes
-- ─────────────────────────────────────────────────────────────────────────────

-- Prospected Properties: ranking by score within org
CREATE INDEX IF NOT EXISTS idx_pp_org_score
    ON prospected_properties (org_id, high_ticket_score DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_pp_org_status
    ON prospected_properties (org_id, status);

CREATE INDEX IF NOT EXISTS idx_pp_org_zone
    ON prospected_properties (org_id, zone);

-- Buyer Profiles: org isolation + status filter
CREATE INDEX IF NOT EXISTS idx_bp_org_status
    ON buyer_profiles (org_id, status);

CREATE INDEX IF NOT EXISTS idx_bp_org_motivation
    ON buyer_profiles (org_id, motivation_score DESC NULLS LAST);

-- Property-Buyer Matches: ranking + pipeline
CREATE INDEX IF NOT EXISTS idx_pbm_org_score
    ON property_buyer_matches (org_id, match_score DESC);

CREATE INDEX IF NOT EXISTS idx_pbm_org_status
    ON property_buyer_matches (org_id, match_status);

CREATE INDEX IF NOT EXISTS idx_pbm_property
    ON property_buyer_matches (property_id);

CREATE INDEX IF NOT EXISTS idx_pbm_buyer
    ON property_buyer_matches (buyer_id);

-- Match Activity Log: timeline per match
CREATE INDEX IF NOT EXISTS idx_mal_match_created
    ON match_activity_log (match_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_mal_org
    ON match_activity_log (org_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Auto-update updated_at Trigger
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to tables with updated_at
DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOR tbl IN SELECT unnest(ARRAY[
        'prospected_properties',
        'buyer_profiles',
        'property_buyer_matches'
    ])
    LOOP
        EXECUTE format(
            'DROP TRIGGER IF EXISTS trg_%s_updated_at ON %I; '
            'CREATE TRIGGER trg_%s_updated_at '
            'BEFORE UPDATE ON %I '
            'FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();',
            tbl, tbl, tbl, tbl
        );
    END LOOP;
END;
$$;

-- ══════════════════════════════════════════════════════════════════════════════
-- ROLLBACK (uncomment to revert):
-- DROP TRIGGER IF EXISTS trg_prospected_properties_updated_at ON prospected_properties;
-- DROP TRIGGER IF EXISTS trg_buyer_profiles_updated_at ON buyer_profiles;
-- DROP TRIGGER IF EXISTS trg_property_buyer_matches_updated_at ON property_buyer_matches;
-- DROP INDEX IF EXISTS idx_pp_org_score, idx_pp_org_status, idx_pp_org_zone;
-- DROP INDEX IF EXISTS idx_bp_org_status, idx_bp_org_motivation;
-- DROP INDEX IF EXISTS idx_pbm_org_score, idx_pbm_org_status, idx_pbm_property, idx_pbm_buyer;
-- DROP INDEX IF EXISTS idx_mal_match_created, idx_mal_org;
-- ALTER TABLE prospected_properties DROP CONSTRAINT IF EXISTS chk_high_ticket_score_range;
-- ALTER TABLE buyer_profiles DROP CONSTRAINT IF EXISTS chk_motivation_score_range;
-- ALTER TABLE buyer_profiles DROP CONSTRAINT IF EXISTS chk_budget_consistency;
-- ALTER TABLE property_buyer_matches DROP CONSTRAINT IF EXISTS chk_match_score_range;
-- ══════════════════════════════════════════════════════════════════════════════
