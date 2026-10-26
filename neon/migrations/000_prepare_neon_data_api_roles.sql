-- Run on the isolated Neon branch before provisioning Neon Data API.
-- Supabase-imported role names conflict with Neon Data API's managed roles.
-- Existing role grants stay attached to the renamed legacy roles.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon')
     AND NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_legacy_anon') THEN
    ALTER ROLE anon RENAME TO nexus_legacy_anon;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated')
     AND NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_legacy_authenticated') THEN
    ALTER ROLE authenticated RENAME TO nexus_legacy_authenticated;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role')
     AND NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_legacy_service_role') THEN
    ALTER ROLE service_role RENAME TO nexus_legacy_service_role;
  END IF;
END;
$$;
