-- ============================================================
-- 015_membership_integrity_hardening.sql
-- Purpose:
--   1) Normalize membership/profile role values.
--   2) Remove duplicate memberships per (org_id, user_id).
--   3) Enforce a single ACTIVE owner per organization.
--   4) Keep user_profiles role/org synced from active memberships.
-- ============================================================

BEGIN;

-- 1) Normalize case on role/status.
UPDATE public.organization_members
SET
  role = lower(role),
  status = lower(status),
  updated_at = NOW()
WHERE role <> lower(role) OR status <> lower(status);

UPDATE public.user_profiles
SET role = lower(role)
WHERE role IS NOT NULL AND role <> lower(role);

-- 2) Remove duplicates for the same (org_id, user_id), keeping the best candidate.
WITH ranked AS (
  SELECT
    id,
    ROW_NUMBER() OVER (
      PARTITION BY org_id, user_id
      ORDER BY
        CASE status
          WHEN 'active' THEN 0
          WHEN 'pending' THEN 1
          ELSE 2
        END,
        updated_at DESC NULLS LAST,
        created_at DESC NULLS LAST,
        id DESC
    ) AS rn
  FROM public.organization_members
  WHERE user_id IS NOT NULL
)
DELETE FROM public.organization_members om
USING ranked r
WHERE om.id = r.id
  AND r.rn > 1;

-- 3) If an org has multiple active owners, keep the earliest and demote the rest to manager.
WITH owners_ranked AS (
  SELECT
    id,
    org_id,
    ROW_NUMBER() OVER (
      PARTITION BY org_id
      ORDER BY created_at ASC, id ASC
    ) AS rn
  FROM public.organization_members
  WHERE role = 'owner'
    AND status = 'active'
)
UPDATE public.organization_members om
SET
  role = 'manager',
  updated_at = NOW()
FROM owners_ranked o
WHERE om.id = o.id
  AND o.rn > 1;

-- 4) Backfill user_profiles from active memberships.
WITH active_members AS (
  SELECT DISTINCT ON (user_id)
    user_id,
    org_id,
    role
  FROM public.organization_members
  WHERE user_id IS NOT NULL
    AND status = 'active'
  ORDER BY
    user_id,
    CASE role
      WHEN 'owner' THEN 0
      WHEN 'manager' THEN 1
      ELSE 2
    END,
    updated_at DESC NULLS LAST,
    created_at DESC NULLS LAST
)
UPDATE public.user_profiles up
SET
  org_id = am.org_id,
  role = am.role
FROM active_members am
WHERE up.id = am.user_id
  AND (
    up.org_id IS DISTINCT FROM am.org_id
    OR lower(COALESCE(up.role, '')) IS DISTINCT FROM am.role
  );

-- 5) Enforce single active owner per org at DB level.
CREATE UNIQUE INDEX IF NOT EXISTS uq_org_single_active_owner
  ON public.organization_members(org_id)
  WHERE role = 'owner' AND status = 'active';

-- 6) Keep profile role/org synced when active membership changes.
CREATE OR REPLACE FUNCTION public.sync_user_profile_from_membership()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.user_id IS NOT NULL AND NEW.status = 'active' THEN
    UPDATE public.user_profiles
    SET
      org_id = NEW.org_id,
      role = NEW.role
    WHERE id = NEW.user_id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_sync_user_profile_from_membership ON public.organization_members;
CREATE TRIGGER trg_sync_user_profile_from_membership
AFTER INSERT OR UPDATE OF org_id, user_id, role, status
ON public.organization_members
FOR EACH ROW
EXECUTE FUNCTION public.sync_user_profile_from_membership();

COMMIT;

