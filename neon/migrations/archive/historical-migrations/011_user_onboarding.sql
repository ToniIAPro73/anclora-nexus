-- Migration 011: User Onboarding Trigger
-- Feature: ANCLORA-MTM-001 Multi-Tenant Memberships v1
-- Purpose: Automatically create user_profile and organization_member for new users.

BEGIN;

-- 1. Create function to handle new user
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
  v_org_id UUID;
BEGIN
  -- Get default organization (Anclora Private Estates)
  SELECT id INTO v_org_id FROM public.organizations LIMIT 1;

  -- 1. Create User Profile
  INSERT INTO public.user_profiles (id, email, full_name, role, org_id)
  VALUES (
    NEW.id,
    NEW.email,
    NEW.raw_user_meta_data->>'full_name',
    'owner', -- Default to owner for v0 single-tenant
    COALESCE(v_org_id, '00000000-0000-0000-0000-000000000000') -- Fallback uuid if no org
  )
  ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email;

  -- 2. Create Organization Member
  IF v_org_id IS NOT NULL THEN
    INSERT INTO public.organization_members (org_id, user_id, role, status)
    VALUES (v_org_id, NEW.id, 'owner', 'active')
    ON CONFLICT (org_id, user_id) DO NOTHING;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 2. Create Trigger on auth.users
-- Drop if exists to be safe
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

COMMIT;
