-- Verification: Data Quality and Entity Resolution
-- Feature ID: ANCLORA-DQER-001

BEGIN;

-- 1. Get a valid org_id
DO $$
DECLARE
    v_org_id uuid;
    v_lead_id uuid := '00000000-0000-0000-0000-000000000001';
    v_candidate_id uuid;
BEGIN
    SELECT id INTO v_org_id FROM public.organizations LIMIT 1;
    
    IF v_org_id IS NULL THEN
        RAISE EXCEPTION 'No organization found to run verification';
    END IF;

    -- 2. Test dq_quality_issues insertion
    INSERT INTO public.dq_quality_issues (org_id, entity_type, entity_id, issue_type, severity, status)
    VALUES (v_org_id, 'lead', v_lead_id, 'missing_field', 'high', 'open');

    -- 3. Test dq_entity_candidates insertion
    INSERT INTO public.dq_entity_candidates (org_id, entity_type, left_entity_id, right_entity_id, similarity_score, status)
    VALUES (v_org_id, 'lead', v_lead_id, '00000000-0000-0000-0000-000000000002', 85.50, 'suggested_merge')
    RETURNING id INTO v_candidate_id;

    -- 4. Test dq_resolution_log insertion
    INSERT INTO public.dq_resolution_log (org_id, entity_type, candidate_id, action)
    VALUES (v_org_id, 'lead', v_candidate_id, 'approve_merge');

    -- 5. Verify constraints (Self-match should fail)
    BEGIN
        INSERT INTO public.dq_entity_candidates (org_id, entity_type, left_entity_id, right_entity_id, similarity_score)
        VALUES (v_org_id, 'lead', v_lead_id, v_lead_id, 100);
        RAISE EXCEPTION 'Constraint check failed: left_entity_id <> right_entity_id not enforced';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'Constraint check passed: self-match prevented';
    END;

    -- 6. Verify constraints (Similarity score out of range should fail)
    BEGIN
        INSERT INTO public.dq_entity_candidates (org_id, entity_type, left_entity_id, right_entity_id, similarity_score)
        VALUES (v_org_id, 'lead', v_lead_id, '00000000-0000-0000-0000-000000000003', 101);
        RAISE EXCEPTION 'Constraint check failed: similarity_score <= 100 not enforced';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'Constraint check passed: similarity score range enforced';
    END;

    RAISE NOTICE 'DQER DB Verification passed successfully.';
END $$;

ROLLBACK;
