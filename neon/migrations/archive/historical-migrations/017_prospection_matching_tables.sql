-- ══════════════════════════════════════════════════════════════════════════════
-- Migration 017: Prospection & Buyer Matching v1 — Tables
-- Feature: ANCLORA-PBM-001
-- Principles: non-destructive, idempotent, reversible, audited
-- ══════════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Prospected Properties
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prospected_properties (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    source          TEXT NOT NULL,
    source_url      TEXT,
    title           TEXT,
    zone            TEXT,
    city            TEXT,
    price           NUMERIC(14,2),
    property_type   TEXT,
    bedrooms        INT,
    bathrooms       INT,
    area_m2         NUMERIC(10,2),
    high_ticket_score NUMERIC(5,2),
    score_breakdown JSONB DEFAULT '{}'::JSONB,
    status          TEXT NOT NULL DEFAULT 'new',
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE prospected_properties IS 'Properties in the prospection pipeline with high-ticket scoring';

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Buyer Profiles
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS buyer_profiles (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              UUID NOT NULL REFERENCES organizations(id),
    full_name           TEXT,
    email               TEXT,
    phone               TEXT,
    budget_min          NUMERIC(14,2),
    budget_max          NUMERIC(14,2),
    preferred_zones     TEXT[],
    preferred_types     TEXT[],
    required_features   JSONB DEFAULT '{}'::JSONB,
    purchase_horizon    TEXT,
    motivation_score    NUMERIC(5,2),
    status              TEXT NOT NULL DEFAULT 'active',
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE buyer_profiles IS 'Potential buyer profiles with preferences and motivation scoring';

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Property-Buyer Matches
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS property_buyer_matches (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              UUID NOT NULL REFERENCES organizations(id),
    property_id         UUID NOT NULL REFERENCES prospected_properties(id) ON DELETE CASCADE,
    buyer_id            UUID NOT NULL REFERENCES buyer_profiles(id) ON DELETE CASCADE,
    match_score         NUMERIC(5,2) NOT NULL,
    score_breakdown     JSONB DEFAULT '{}'::JSONB,
    match_status        TEXT NOT NULL DEFAULT 'candidate',
    commission_estimate NUMERIC(14,2),
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (property_id, buyer_id)
);

COMMENT ON TABLE property_buyer_matches IS 'Scored buyer-property match links with pipeline status tracking';

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. Match Activity Log
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS match_activity_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    match_id        UUID NOT NULL REFERENCES property_buyer_matches(id) ON DELETE CASCADE,
    activity_type   TEXT NOT NULL,
    outcome         TEXT,
    details         JSONB DEFAULT '{}'::JSONB,
    created_by      UUID REFERENCES auth.users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE match_activity_log IS 'Commercial activity log for each property-buyer match';

-- ══════════════════════════════════════════════════════════════════════════════
-- ROLLBACK (uncomment to revert):
-- DROP TABLE IF EXISTS match_activity_log CASCADE;
-- DROP TABLE IF EXISTS property_buyer_matches CASCADE;
-- DROP TABLE IF EXISTS buyer_profiles CASCADE;
-- DROP TABLE IF EXISTS prospected_properties CASCADE;
-- ══════════════════════════════════════════════════════════════════════════════
