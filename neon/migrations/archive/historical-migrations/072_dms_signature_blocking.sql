-- 072_dms_signature_blocking.sql
-- Adds signature blocking columns to generated_documents for Advisor AI integration.
-- Supports the signature block propagation service (Requirement 12).

ALTER TABLE public.generated_documents
    ADD COLUMN IF NOT EXISTS signature_status TEXT
        DEFAULT 'ready_for_signature'
        CHECK (signature_status IN ('ready_for_signature', 'signature_blocked', 'signed'));

ALTER TABLE public.generated_documents
    ADD COLUMN IF NOT EXISTS block_reason TEXT;

ALTER TABLE public.generated_documents
    ADD COLUMN IF NOT EXISTS block_source TEXT;

CREATE INDEX IF NOT EXISTS idx_generated_documents_signature_status
    ON public.generated_documents(org_id, signature_status)
    WHERE signature_status = 'signature_blocked';
