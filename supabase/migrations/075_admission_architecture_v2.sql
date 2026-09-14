-- supabase/migrations/075_admission_architecture_v2.sql
-- Forward-only migration: expand access_requests constraints for Anclora Admission Architecture v2
-- Supports:
-- 1. Canonical product 'guesthub' alongside legacy 'syncxml'
-- 2. Direct sources 'private_estates_landing', 'private_estates_web', 'guesthub_app'
-- 3. Identity provisioning fields: identity_subject_id, identity_invitation_id, membership_id, provisioning_status, provisioning_error
-- 4. Source taxonomy fields: source_system, source_channel, source_detail

BEGIN;

-- Add new provisioning and source taxonomy columns
ALTER TABLE public.access_requests
    ADD COLUMN IF NOT EXISTS source_system text,
    ADD COLUMN IF NOT EXISTS source_channel text,
    ADD COLUMN IF NOT EXISTS source_detail text,
    ADD COLUMN IF NOT EXISTS identity_subject_id text,
    ADD COLUMN IF NOT EXISTS identity_invitation_id text,
    ADD COLUMN IF NOT EXISTS membership_id text,
    ADD COLUMN IF NOT EXISTS provisioning_status text NOT NULL DEFAULT 'not_started',
    ADD COLUMN IF NOT EXISTS provisioning_error text;

-- Drop prior constraints safely
ALTER TABLE public.access_requests
    DROP CONSTRAINT IF EXISTS access_requests_product_check,
    DROP CONSTRAINT IF EXISTS access_requests_source_check,
    DROP CONSTRAINT IF EXISTS check_source_product_coherence,
    DROP CONSTRAINT IF EXISTS access_requests_provisioning_status_check;

-- Enforce expanded products (canonical guesthub + legacy syncxml + synergi + data_lab)
ALTER TABLE public.access_requests
    ADD CONSTRAINT access_requests_product_check
    CHECK (product IN ('data_lab', 'synergi', 'guesthub', 'syncxml'));

-- Enforce expanded sources (retaining real origin)
ALTER TABLE public.access_requests
    ADD CONSTRAINT access_requests_source_check
    CHECK (source IN (
        'private_estates_landing',
        'private_estates_web',
        'data_lab_app',
        'synergi_app',
        'guesthub_app',
        'syncxml_landing',
        'nexus_manual',
        'external_api'
    ));

-- Enforce coherent source-product combinations
ALTER TABLE public.access_requests
    ADD CONSTRAINT check_source_product_coherence
    CHECK (
        (source = 'syncxml_landing'  AND product IN ('syncxml', 'guesthub')) OR
        (source = 'guesthub_app'     AND product IN ('syncxml', 'guesthub')) OR
        (source = 'synergi_app'      AND product = 'synergi') OR
        (source = 'data_lab_app'     AND product = 'data_lab') OR
        (source IN ('private_estates_landing', 'private_estates_web', 'nexus_manual', 'external_api')
            AND product IN ('data_lab', 'synergi', 'guesthub', 'syncxml'))
    );

-- Enforce valid provisioning statuses
ALTER TABLE public.access_requests
    ADD CONSTRAINT access_requests_provisioning_status_check
    CHECK (provisioning_status IN (
        'not_started',
        'pending',
        'invite_ready',
        'membership_granted',
        'completed',
        'failed',
        'not_applicable'
    ));

-- Indexes for identity lookup and provisioning monitoring
CREATE INDEX IF NOT EXISTS idx_access_requests_identity_subject_id
    ON public.access_requests(identity_subject_id)
    WHERE identity_subject_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_access_requests_identity_invitation_id
    ON public.access_requests(identity_invitation_id)
    WHERE identity_invitation_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_access_requests_provisioning_status
    ON public.access_requests(provisioning_status, status);

COMMIT;
