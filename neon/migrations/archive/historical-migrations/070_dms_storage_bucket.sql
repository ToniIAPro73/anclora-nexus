-- 070_dms_storage_bucket.sql
-- Creates the 'dms' storage bucket used by the document generation service.
-- The backend uses the service-role key so RLS is bypassed server-side.
-- Policies below cover direct client-side access if ever needed.

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'dms',
  'dms',
  false,
  52428800,
  ARRAY[
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain',
    'application/octet-stream'
  ]
)
ON CONFLICT (id) DO NOTHING;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'storage' AND tablename = 'objects' AND policyname = 'dms_upload_authenticated'
  ) THEN
    EXECUTE 'CREATE POLICY dms_upload_authenticated ON storage.objects FOR INSERT TO authenticated WITH CHECK (bucket_id = ''dms'')';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'storage' AND tablename = 'objects' AND policyname = 'dms_read_authenticated'
  ) THEN
    EXECUTE 'CREATE POLICY dms_read_authenticated ON storage.objects FOR SELECT TO authenticated USING (bucket_id = ''dms'')';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'storage' AND tablename = 'objects' AND policyname = 'dms_update_authenticated'
  ) THEN
    EXECUTE 'CREATE POLICY dms_update_authenticated ON storage.objects FOR UPDATE TO authenticated USING (bucket_id = ''dms'')';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'storage' AND tablename = 'objects' AND policyname = 'dms_delete_authenticated'
  ) THEN
    EXECUTE 'CREATE POLICY dms_delete_authenticated ON storage.objects FOR DELETE TO authenticated USING (bucket_id = ''dms'')';
  END IF;
END $$;
