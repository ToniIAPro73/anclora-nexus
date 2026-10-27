-- ============================================================
-- 027_cost_governance_foundation_verify.sql
-- Feature: ANCLORA-CGF-001 Cost Governance Foundation
-- Purpose: Verify migration success
-- ============================================================

BEGIN;

DO $$
DECLARE
    org_count INT;
    policy_count INT;
    test_org_id UUID;
BEGIN
    -- 1. Verify tables exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'org_cost_policies') THEN
        RAISE EXCEPTION 'Table org_cost_policies missing';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'org_cost_usage_events') THEN
        RAISE EXCEPTION 'Table org_cost_usage_events missing';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'org_cost_alerts') THEN
        RAISE EXCEPTION 'Table org_cost_alerts missing';
    END IF;

    -- 2. Verify backfill
    SELECT COUNT(*) INTO org_count FROM organizations;
    SELECT COUNT(*) INTO policy_count FROM org_cost_policies;

    IF policy_count < org_count THEN
        RAISE WARNING 'Policy count (%) does not match Org count (%)', policy_count, org_count;
    END IF;

    -- 3. Verify constraints (positive check)
    BEGIN
        SELECT id INTO test_org_id FROM organizations LIMIT 1;
        IF test_org_id IS NOT NULL THEN
            INSERT INTO org_cost_usage_events (org_id, capability_code, units, cost_eur)
            VALUES (test_org_id, 'test', -1, 0);
            RAISE EXCEPTION 'Constraint chk_units_positive failed to catch negative units';
        EXCEPTION WHEN check_violation THEN
            -- Expected
        END;
    END;

    RAISE NOTICE 'Verification passed successfully.';
END
$$;

ROLLBACK;
