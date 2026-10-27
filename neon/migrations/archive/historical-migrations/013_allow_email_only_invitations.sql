-- ============================================================
-- 013_allow_email_only_invitations.sql
-- Purpose: Allow inviting users by email before they register.
-- ============================================================

BEGIN;

ALTER TABLE organization_members
  ALTER COLUMN user_id DROP NOT NULL;

ALTER TABLE organization_members
  ADD COLUMN IF NOT EXISTS invited_email TEXT;

CREATE INDEX IF NOT EXISTS idx_org_members_invited_email
  ON organization_members(org_id, invited_email);

-- Avoid duplicate pending invitations per organization+email.
CREATE UNIQUE INDEX IF NOT EXISTS uq_org_members_pending_invited_email
  ON organization_members(org_id, invited_email)
  WHERE invited_email IS NOT NULL AND status = 'pending';

COMMIT;
