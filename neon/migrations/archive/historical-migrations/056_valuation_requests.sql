CREATE TABLE IF NOT EXISTS valuation_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  full_name TEXT NOT NULL,
  email TEXT NOT NULL,
  phone TEXT,
  property_address TEXT,
  message TEXT,
  captcha_provider TEXT,
  captcha_verified_at TIMESTAMPTZ,
  confirmation_email_sent_at TIMESTAMPTZ,
  submission_language TEXT NOT NULL DEFAULT 'es',
  submission_source TEXT NOT NULL DEFAULT 'private_estates_landing',
  status TEXT NOT NULL DEFAULT 'submitted'
    CHECK (status IN ('submitted', 'under_review', 'closed')),
  review_notes TEXT,
  reviewed_by_user_id UUID,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_valuation_requests_org_created
  ON valuation_requests(org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_valuation_requests_org_status
  ON valuation_requests(org_id, status);

ALTER TABLE valuation_requests ENABLE ROW LEVEL SECURITY;

CREATE POLICY "org_isolation_valuation_requests"
  ON valuation_requests
  FOR ALL
  USING (org_id = current_setting('app.org_id', true)::UUID);

COMMENT ON TABLE valuation_requests IS
  'Solicitudes de valoracion de inmuebles recibidas desde la landing page.';
