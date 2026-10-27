CREATE TABLE IF NOT EXISTS partner_admissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  full_name TEXT NOT NULL,
  email TEXT NOT NULL,
  phone TEXT,
  company_name TEXT,
  service_category TEXT NOT NULL DEFAULT 'other'
    CHECK (service_category IN ('real_estate', 'professional', 'luxury', 'eco', 'other')),
  service_summary TEXT NOT NULL,
  collaboration_pitch TEXT,
  coverage_areas TEXT[] NOT NULL DEFAULT '{}',
  languages TEXT[] NOT NULL DEFAULT '{}',
  website_url TEXT,
  linkedin_url TEXT,
  instagram_url TEXT,
  sustainability_focus BOOLEAN NOT NULL DEFAULT FALSE,
  sustainability_notes TEXT,
  submission_source TEXT NOT NULL DEFAULT 'private_estates',
  status TEXT NOT NULL DEFAULT 'submitted'
    CHECK (status IN ('submitted', 'under_review', 'accepted', 'rejected')),
  review_notes TEXT,
  reviewed_by_user_id UUID,
  reviewed_at TIMESTAMPTZ,
  decision_email_sent_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_partner_admissions_org_created
  ON partner_admissions(org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_partner_admissions_org_status
  ON partner_admissions(org_id, status);

CREATE INDEX IF NOT EXISTS idx_partner_admissions_org_category
  ON partner_admissions(org_id, service_category);

CREATE INDEX IF NOT EXISTS idx_partner_admissions_coverage_areas
  ON partner_admissions USING GIN (coverage_areas);

CREATE INDEX IF NOT EXISTS idx_partner_admissions_languages
  ON partner_admissions USING GIN (languages);

ALTER TABLE partner_admissions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "org_isolation_partner_admissions"
  ON partner_admissions
  FOR ALL
  USING (org_id = current_setting('app.org_id', true)::UUID);

COMMENT ON TABLE partner_admissions IS
  'Cola de admision curada para el portal Synergi.';
