-- Migration 008: Create organization_members table
-- Feature: ANCLORA-MTM-001 Multi-Tenant Memberships v1
-- Purpose: Central source of truth for membership and roles.

BEGIN;

-- 1. Create helper function if not exists
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 2. Create organization_members table
CREATE TABLE IF NOT EXISTS organization_members (
  -- Identifiers
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  
  -- Membership
  role TEXT NOT NULL CHECK (role IN ('owner', 'manager', 'agent')),
  status TEXT NOT NULL DEFAULT 'active' 
    CHECK (status IN ('active', 'pending', 'suspended', 'removed')),
  joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  
  -- Invitation
  invited_by UUID REFERENCES auth.users(id),
  invitation_code TEXT UNIQUE,
  invitation_accepted_at TIMESTAMP WITH TIME ZONE,
  
  -- Audit
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  
  -- Constraints
  UNIQUE(org_id, user_id)
);

-- 3. Create optimized indices
CREATE INDEX IF NOT EXISTS idx_org_members_org_id ON organization_members(org_id);
CREATE INDEX IF NOT EXISTS idx_org_members_user_id ON organization_members(user_id);
CREATE INDEX IF NOT EXISTS idx_org_members_role ON organization_members(role);
CREATE INDEX IF NOT EXISTS idx_org_members_status ON organization_members(status);
CREATE INDEX IF NOT EXISTS idx_org_members_org_user ON organization_members(org_id, user_id);
CREATE INDEX IF NOT EXISTS idx_org_members_code ON organization_members(invitation_code) 
  WHERE status = 'pending';

-- 4. Create trigger
DROP TRIGGER IF EXISTS update_organization_members_updated_at ON organization_members;
CREATE TRIGGER update_organization_members_updated_at
BEFORE UPDATE ON organization_members
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

COMMIT;
