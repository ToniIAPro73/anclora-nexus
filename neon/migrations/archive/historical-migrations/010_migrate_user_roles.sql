-- Migration 010: Migrate user roles
-- Feature: ANCLORA-MTM-001 Multi-Tenant Memberships v1
-- Purpose: Data migration of user_profiles.role to organization_members.role.

BEGIN;

-- --------- PRE-MIGRATION CHECKS ---------
DO $$
DECLARE
  v_count_with_role INT;
  v_count_null_org INT;
  v_count_dup_user INT;
BEGIN
  SELECT COUNT(*) INTO v_count_with_role 
    FROM user_profiles WHERE role IS NOT NULL;
  
  SELECT COUNT(*) INTO v_count_null_org 
    FROM user_profiles WHERE org_id IS NULL AND role IS NOT NULL;
  
  SELECT COUNT(*) INTO v_count_dup_user 
    FROM (SELECT id FROM user_profiles WHERE role IS NOT NULL 
          GROUP BY id HAVING COUNT(*) > 1) t;
  
  RAISE NOTICE 'PRE-MIGRACIÓN:';
  RAISE NOTICE '  Usuarios con role: %', v_count_with_role;
  RAISE NOTICE '  Usuarios con org_id NULL: %', v_count_null_org;
  RAISE NOTICE '  Usuarios duplicados: %', v_count_dup_user;
END $$;

-- --------- MIGRATION ---------

-- 1. Insert roles of user_profiles into organization_members
-- Using COALESCE to ensure we don't have nulls and handling potential missing orgs
INSERT INTO organization_members (
  org_id, user_id, role, status, joined_at
)
SELECT 
  COALESCE(up.org_id, (SELECT id FROM organizations LIMIT 1)) as org_id,
  up.id,
  COALESCE(NULLIF(up.role, ''), 'agent') as role,
  'active' as status,
  COALESCE(up.created_at, NOW()) as joined_at
FROM user_profiles up
WHERE up.id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM organization_members om 
    WHERE om.user_id = up.id 
    AND om.org_id = COALESCE(up.org_id, (SELECT id FROM organizations LIMIT 1))
  )
ON CONFLICT (org_id, user_id) DO NOTHING;

-- 2. Update organizations.owner_id (the first 'owner' found for the org)
UPDATE organizations o SET owner_id = (
  SELECT om.user_id FROM organization_members om 
  WHERE om.org_id = o.id 
  AND om.role = 'owner' 
  ORDER BY om.joined_at ASC 
  LIMIT 1
)
WHERE o.owner_id IS NULL 
  AND EXISTS (
    SELECT 1 FROM organization_members om 
    WHERE om.org_id = o.id AND om.role = 'owner'
  );

-- 3. If an organization still has no owner, assign the first member joined
UPDATE organizations o SET owner_id = (
  SELECT om.user_id FROM organization_members om 
  WHERE om.org_id = o.id 
  ORDER BY om.joined_at ASC 
  LIMIT 1
)
WHERE o.owner_id IS NULL;

-- --------- POST-MIGRATION CHECKS ---------
DO $$
DECLARE
  v_count_migrated INT;
  v_count_orphaned INT;
  v_count_no_owner INT;
BEGIN
  SELECT COUNT(*) INTO v_count_migrated FROM organization_members;
  
  SELECT COUNT(*) INTO v_count_orphaned 
    FROM organization_members om
    WHERE NOT EXISTS (SELECT 1 FROM auth.users au WHERE au.id = om.user_id);
  
  SELECT COUNT(*) INTO v_count_no_owner 
    FROM organizations WHERE owner_id IS NULL;
  
  RAISE NOTICE 'POST-MIGRACIÓN:';
  RAISE NOTICE '  Registros migrados: %', v_count_migrated;
  RAISE NOTICE '  Orfanados detectados: %', v_count_orphaned;
  RAISE NOTICE '  Orgs sin owner: %', v_count_no_owner;
  
  -- Fall if critical problems found
  IF v_count_orphaned > 0 THEN
    RAISE EXCEPTION 'MIGRACIÓN FALLIDA: Datos inconsistentes detectados (Users huérfanos)';
  END IF;
END $$;

COMMIT;

-- Rollback Procedure:
-- Within the same transaction block, ROLLBACK is automatic if an exception occurs.
-- Manual rollback after commit (DANGEROUS): 
-- DELETE FROM organization_members; 
-- UPDATE organizations SET owner_id = NULL;
