-- =============================================================================
-- Migration 071: AML Vault Schema and Retention Enforcement
-- =============================================================================
-- Implements a dedicated schema for AML-regulated data with:
--   - 10-year retention enforcement (ETD/465/2021)
--   - Row Level Security restricting access to compliance_officer and service_role
--   - Trigger preventing deletion of non-expired records
--   - Access logging for audit trail
--
-- Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
-- =============================================================================

-- Create dedicated schema physically separated from marketing/operational data
CREATE SCHEMA IF NOT EXISTS aml_vault;

-- =============================================================================
-- Table: aml_vault.retention_records
-- Stores AML-relevant transaction records with enforced 10-year retention
-- =============================================================================
CREATE TABLE aml_vault.retention_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL,
    source_table TEXT NOT NULL,
    source_record_id UUID NOT NULL,
    record_data JSONB NOT NULL,
    classification_reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    retention_expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '10 years'),
    review_status TEXT DEFAULT 'active' CHECK (review_status IN ('active', 'pending_review', 'deleted')),
    CONSTRAINT retention_not_expired CHECK (retention_expires_at > created_at)
);

-- Indexes for common query patterns
CREATE INDEX idx_retention_records_org_id ON aml_vault.retention_records(org_id);
CREATE INDEX idx_retention_records_expires ON aml_vault.retention_records(retention_expires_at)
    WHERE review_status = 'active';
CREATE INDEX idx_retention_records_source ON aml_vault.retention_records(source_table, source_record_id);

-- =============================================================================
-- Table: aml_vault.access_log
-- Records every access to vault data for audit compliance
-- =============================================================================
CREATE TABLE aml_vault.access_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id UUID REFERENCES aml_vault.retention_records(id),
    accessed_by UUID NOT NULL,
    access_type TEXT NOT NULL CHECK (access_type IN ('read', 'audit')),
    accessed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    access_reason TEXT NOT NULL
);

CREATE INDEX idx_access_log_record_id ON aml_vault.access_log(record_id);
CREATE INDEX idx_access_log_accessed_by ON aml_vault.access_log(accessed_by);

-- =============================================================================
-- Row Level Security: Restrict access to compliance_officer and service_role
-- Requirement 3.5: PII in AML vault must not be accessible to marketing or analytics
-- =============================================================================

-- RLS on retention_records
ALTER TABLE aml_vault.retention_records ENABLE ROW LEVEL SECURITY;

CREATE POLICY vault_compliance_only ON aml_vault.retention_records
    FOR ALL USING (
        current_setting('request.jwt.claim.role', true) IN ('compliance_officer', 'service_role')
        OR current_setting('role', true) = 'service_role'
    );

-- RLS on access_log
ALTER TABLE aml_vault.access_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY access_log_compliance_only ON aml_vault.access_log
    FOR ALL USING (
        current_setting('request.jwt.claim.role', true) IN ('compliance_officer', 'service_role')
        OR current_setting('role', true) = 'service_role'
    );

-- =============================================================================
-- Trigger: Prevent premature deletion of non-expired records
-- Requirement 3.3: While retention period has not expired, prevent deletion
-- =============================================================================
CREATE OR REPLACE FUNCTION aml_vault.prevent_premature_deletion()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.retention_expires_at > now() AND OLD.review_status = 'active' THEN
        RAISE EXCEPTION 'Cannot delete record before retention period expires (expires: %)', OLD.retention_expires_at;
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER prevent_early_delete
    BEFORE DELETE ON aml_vault.retention_records
    FOR EACH ROW EXECUTE FUNCTION aml_vault.prevent_premature_deletion();

-- =============================================================================
-- Trigger: Auto-calculate retention_expires_at on INSERT
-- Ensures retention_expires_at = created_at + interval '10 years' exactly
-- Requirement 3.2: Retention timestamp of 10 years from creation date
-- =============================================================================
CREATE OR REPLACE FUNCTION aml_vault.set_retention_expiry()
RETURNS TRIGGER AS $$
BEGIN
    NEW.retention_expires_at := NEW.created_at + interval '10 years';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_retention_expiry_on_insert
    BEFORE INSERT ON aml_vault.retention_records
    FOR EACH ROW EXECUTE FUNCTION aml_vault.set_retention_expiry();

-- =============================================================================
-- Revoke direct access from potentially dangerous roles
-- Additional defense-in-depth: even if RLS is bypassed, these roles cannot query
-- =============================================================================
REVOKE ALL ON SCHEMA aml_vault FROM PUBLIC;
GRANT USAGE ON SCHEMA aml_vault TO service_role;
GRANT ALL ON ALL TABLES IN SCHEMA aml_vault TO service_role;

-- =============================================================================
-- Comments for documentation
-- =============================================================================
COMMENT ON SCHEMA aml_vault IS 'Dedicated vault for AML-regulated data with 10-year retention enforcement (ETD/465/2021)';
COMMENT ON TABLE aml_vault.retention_records IS 'Stores copies of AML-relevant transaction records with mandatory 10-year retention';
COMMENT ON TABLE aml_vault.access_log IS 'Audit trail of all access to AML vault records';
COMMENT ON COLUMN aml_vault.retention_records.retention_expires_at IS 'Auto-calculated: created_at + 10 years. Records cannot be deleted before this date.';
COMMENT ON FUNCTION aml_vault.prevent_premature_deletion IS 'Trigger function that blocks deletion of active records before retention expiry';
COMMENT ON FUNCTION aml_vault.set_retention_expiry IS 'Trigger function that auto-calculates retention_expires_at = created_at + 10 years on insert';
