-- Migration 009: Alter organizations table
-- Feature: ANCLORA-MTM-001 Multi-Tenant Memberships v1
-- Purpose: Add owner_id, status, and metadata to organizations.

BEGIN;

-- 1. Add columns to organizations
ALTER TABLE organizations 
  ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES auth.users(id),
  ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active' 
    CHECK (status IN ('active', 'inactive')),
  ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- 2. Create indices
CREATE INDEX IF NOT EXISTS idx_organizations_owner_id ON organizations(owner_id);

COMMIT;

-- Rollback Procedure:
-- ALTER TABLE organizations DROP COLUMN IF EXISTS owner_id;
-- ALTER TABLE organizations DROP COLUMN IF EXISTS status;
-- ALTER TABLE organizations DROP COLUMN IF EXISTS metadata;
