-- ============================================================
-- 028_cost_governance_foundation_rollback.sql
-- Feature: ANCLORA-CGF-001 Cost Governance Foundation
-- Purpose: Rollback tables and policies
-- ============================================================

BEGIN;

DROP TABLE IF EXISTS org_cost_alerts CASCADE;
DROP TABLE IF EXISTS org_cost_usage_events CASCADE;
DROP TABLE IF EXISTS org_cost_policies CASCADE;

COMMIT;
