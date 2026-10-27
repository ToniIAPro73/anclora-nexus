-- Verification: Source Connectors Unified Ingestion
-- Feature ID: ANCLORA-SCUI-001

DO $$
DECLARE
    v_org_id uuid;
    v_dedupe_key text := 'test_dedupe_key_001';
BEGIN
    -- 1. Get a valid org_id
    SELECT id INTO v_org_id FROM public.organizations LIMIT 1;
    
    IF v_org_id IS NULL THEN
        RAISE EXCEPTION 'No organization found for testing';
    END IF;

    -- 2. Insert connector
    INSERT INTO public.ingestion_connectors (org_id, connector_name, entity_type, source_system)
    VALUES (v_org_id, 'test-connector', 'lead', 'cta_web')
    ON CONFLICT (org_id, connector_name, entity_type) DO NOTHING;

    -- 3. Insert event
    INSERT INTO public.ingestion_events (org_id, connector_name, entity_type, external_id, dedupe_key, status, payload)
    VALUES (v_org_id, 'test-connector', 'lead', 'ext_001', v_dedupe_key, 'received', '{"test": true}'::jsonb);

    -- 4. Verify idempotency (should fail)
    BEGIN
        INSERT INTO public.ingestion_events (org_id, connector_name, entity_type, external_id, dedupe_key, status, payload)
        VALUES (v_org_id, 'test-connector', 'lead', 'ext_001', v_dedupe_key, 'received', '{"test": true}'::jsonb);
        RAISE EXCEPTION 'Idempotency check failed: unique constraint not triggered';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'Success: Unique constraint triggered as expected';
    END;

    -- 5. Final check
    IF EXISTS (SELECT 1 FROM public.ingestion_events WHERE dedupe_key = v_dedupe_key) THEN
        RAISE NOTICE 'Verification completed successfully';
    ELSE
        RAISE EXCEPTION 'Verification failed: event not found';
    END IF;

    -- Cleanup test data
    DELETE FROM public.ingestion_events WHERE dedupe_key = v_dedupe_key;
END $$;
