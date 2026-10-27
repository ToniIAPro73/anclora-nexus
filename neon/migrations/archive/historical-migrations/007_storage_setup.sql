-- ============================================================
-- 007_storage_setup.sql — Storage buckets and RLS for local dev
-- ============================================================

-- Ensure buckets exist
DO $$
BEGIN
    BEGIN
        INSERT INTO storage.buckets (id, name, public)
        VALUES ('avatars', 'avatars', true), ('logos', 'logos', true)
        ON CONFLICT (id) DO UPDATE SET public = true;
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE 'Cannot modify storage.buckets - run manually in Supabase Dashboard';
    END;

    BEGIN
        ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;

        -- Clean up old policies to avoid conflicts
        DROP POLICY IF EXISTS "Public Read Avatars" ON storage.objects;
        DROP POLICY IF EXISTS "Auth Upload Avatars" ON storage.objects;
        DROP POLICY IF EXISTS "Auth Update Avatars" ON storage.objects;
        DROP POLICY IF EXISTS "Public Read Logos" ON storage.objects;
        DROP POLICY IF EXISTS "Auth Upload Logos" ON storage.objects;
        DROP POLICY IF EXISTS "Auth Update Logos" ON storage.objects;
        DROP POLICY IF EXISTS "local_avatars_access" ON storage.objects;
        DROP POLICY IF EXISTS "local_logos_access" ON storage.objects;
        DROP POLICY IF EXISTS "Public Access" ON storage.objects;
        DROP POLICY IF EXISTS "Avatar Upload" ON storage.objects;
        DROP POLICY IF EXISTS "Avatar Update" ON storage.objects;

        -- Permissive policies for local dev
        CREATE POLICY "local_avatars_access" ON storage.objects
        FOR ALL TO public
        USING (bucket_id = 'avatars')
        WITH CHECK (bucket_id = 'avatars');

        CREATE POLICY "local_logos_access" ON storage.objects
        FOR ALL TO public
        USING (bucket_id = 'logos')
        WITH CHECK (bucket_id = 'logos');
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE 'Cannot modify storage.objects policies - run manually in Supabase Dashboard';
    END;
END $$;
