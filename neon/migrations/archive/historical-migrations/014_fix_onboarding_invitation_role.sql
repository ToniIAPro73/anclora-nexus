-- ============================================================
-- 014_fix_onboarding_invitation_role.sql
-- Purpose:
--   1) Make onboarding respect pending invitations by email.
--   2) Avoid auto-creating extra owner memberships for invited users.
--   3) Cleanup legacy duplicates (pending invitation + active membership same email/org).
-- ============================================================

BEGIN;

-- Recreate onboarding handler with invitation-aware logic.
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
  v_default_org_id UUID;
  v_invitation_id UUID;
  v_invitation_org_id UUID;
  v_invitation_role TEXT;
  v_target_org_id UUID;
  v_target_role TEXT;
  v_has_owner BOOLEAN;
BEGIN
  -- Default organization fallback.
  SELECT id INTO v_default_org_id FROM public.organizations ORDER BY created_at ASC LIMIT 1;

  -- If there is a pending invite for this email, use it.
  SELECT id, org_id, role
    INTO v_invitation_id, v_invitation_org_id, v_invitation_role
  FROM public.organization_members
  WHERE status = 'pending'
    AND invited_email IS NOT NULL
    AND lower(invited_email) = lower(NEW.email)
  ORDER BY created_at DESC
  LIMIT 1;

  v_target_org_id := COALESCE(v_invitation_org_id, v_default_org_id);

  IF v_invitation_id IS NOT NULL THEN
    v_target_role := v_invitation_role;
  ELSE
    -- First user in org may become owner; later self-signups default to agent.
    SELECT EXISTS (
      SELECT 1 FROM public.organization_members
      WHERE org_id = v_target_org_id
        AND role = 'owner'
        AND status = 'active'
    ) INTO v_has_owner;

    v_target_role := CASE WHEN COALESCE(v_has_owner, FALSE) THEN 'agent' ELSE 'owner' END;
  END IF;

  -- Upsert profile with role derived from invitation/default logic.
  INSERT INTO public.user_profiles (id, email, full_name, role, org_id)
  VALUES (
    NEW.id,
    NEW.email,
    NEW.raw_user_meta_data->>'full_name',
    COALESCE(v_target_role, 'agent'),
    COALESCE(v_target_org_id, '00000000-0000-0000-0000-000000000000')
  )
  ON CONFLICT (id) DO UPDATE SET
    email = EXCLUDED.email,
    role = EXCLUDED.role,
    org_id = EXCLUDED.org_id;

  IF v_target_org_id IS NOT NULL THEN
    IF v_invitation_id IS NOT NULL THEN
      -- Activate existing invitation row instead of creating a new owner row.
      UPDATE public.organization_members
      SET user_id = NEW.id,
          status = 'active',
          invitation_accepted_at = NOW(),
          updated_at = NOW()
      WHERE id = v_invitation_id;
    ELSE
      INSERT INTO public.organization_members (org_id, user_id, role, status)
      VALUES (v_target_org_id, NEW.id, v_target_role, 'active')
      ON CONFLICT (org_id, user_id) DO NOTHING;
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Cleanup existing duplicates:
-- if a pending invited_email row exists and same email already has an active membership in same org,
-- promote the active role to the invited role and remove pending duplicate.
WITH duplicate_pairs AS (
  SELECT
    p.id AS pending_id,
    a.id AS active_id,
    p.role AS pending_role
  FROM public.organization_members p
  JOIN public.organization_members a
    ON a.org_id = p.org_id
   AND a.status = 'active'
  JOIN public.user_profiles up
    ON up.id = a.user_id
  WHERE p.status = 'pending'
    AND p.user_id IS NULL
    AND p.invited_email IS NOT NULL
    AND lower(up.email) = lower(p.invited_email)
)
UPDATE public.organization_members a
SET role = dp.pending_role,
    updated_at = NOW()
FROM duplicate_pairs dp
WHERE a.id = dp.active_id;

DELETE FROM public.organization_members p
USING (
  SELECT p.id
  FROM public.organization_members p
  JOIN public.organization_members a
    ON a.org_id = p.org_id
   AND a.status = 'active'
  JOIN public.user_profiles up
    ON up.id = a.user_id
  WHERE p.status = 'pending'
    AND p.user_id IS NULL
    AND p.invited_email IS NOT NULL
    AND lower(up.email) = lower(p.invited_email)
) d
WHERE p.id = d.id;

COMMIT;
