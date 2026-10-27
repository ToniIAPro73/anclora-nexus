-- ============================================================
-- 016_invitation_only_onboarding.sql
-- Purpose:
--   1) Require invitation for new users after initial bootstrap.
--   2) Prevent automatic active membership creation for self-signups.
--   3) Keep first-ever user bootstrap as owner for empty environments.
-- ============================================================

BEGIN;

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
  v_default_org_id UUID;
  v_invitation_id UUID;
  v_invitation_org_id UUID;
  v_invitation_role TEXT;
  v_target_org_id UUID;
  v_target_role TEXT;
  v_active_memberships INTEGER;
BEGIN
  SELECT id
    INTO v_default_org_id
  FROM public.organizations
  ORDER BY created_at ASC
  LIMIT 1;

  SELECT id, org_id, role
    INTO v_invitation_id, v_invitation_org_id, v_invitation_role
  FROM public.organization_members
  WHERE status = 'pending'
    AND invited_email IS NOT NULL
    AND lower(invited_email) = lower(NEW.email)
  ORDER BY created_at DESC
  LIMIT 1;

  SELECT COUNT(*)
    INTO v_active_memberships
  FROM public.organization_members
  WHERE status = 'active';

  IF v_invitation_id IS NOT NULL THEN
    v_target_org_id := v_invitation_org_id;
    v_target_role := lower(v_invitation_role);
  ELSIF COALESCE(v_active_memberships, 0) = 0 THEN
    -- Bootstrap only: first user in empty system.
    v_target_org_id := v_default_org_id;
    v_target_role := 'owner';
  ELSE
    -- Invite-only mode once system is initialized.
    RAISE EXCEPTION 'INVITATION_REQUIRED';
  END IF;

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

  IF v_invitation_id IS NOT NULL THEN
    UPDATE public.organization_members
    SET user_id = NEW.id,
        status = 'active',
        invitation_accepted_at = NOW(),
        updated_at = NOW()
    WHERE id = v_invitation_id;
  ELSIF v_target_org_id IS NOT NULL THEN
    INSERT INTO public.organization_members (org_id, user_id, role, status)
    VALUES (v_target_org_id, NEW.id, v_target_role, 'active')
    ON CONFLICT (org_id, user_id) DO NOTHING;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

COMMIT;

