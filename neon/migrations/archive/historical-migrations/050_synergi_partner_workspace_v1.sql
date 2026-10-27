CREATE TABLE IF NOT EXISTS synergi_partner_workspaces (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL,
  admission_id UUID NOT NULL UNIQUE REFERENCES partner_admissions(id) ON DELETE CASCADE,
  access_token TEXT NOT NULL UNIQUE,
  workspace_status TEXT NOT NULL DEFAULT 'invited'
    CHECK (workspace_status IN ('invited', 'active', 'paused')),
  partner_tier TEXT NOT NULL DEFAULT 'approved'
    CHECK (partner_tier IN ('approved', 'preferred', 'strategic')),
  headline TEXT,
  collaboration_focus TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  next_steps TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  resources JSONB NOT NULL DEFAULT '[]'::JSONB,
  last_seen_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE TABLE IF NOT EXISTS synergi_partner_opportunities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL,
  workspace_id UUID NOT NULL REFERENCES synergi_partner_workspaces(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  opportunity_type TEXT NOT NULL
    CHECK (opportunity_type IN ('buyer_referral', 'seller_referral', 'service_offer', 'collaboration_request')),
  summary TEXT NOT NULL,
  target_zone TEXT,
  budget_range TEXT,
  next_step TEXT,
  status TEXT NOT NULL DEFAULT 'submitted'
    CHECK (status IN ('submitted', 'in_review', 'accepted', 'archived')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_synergi_partner_workspaces_org_admission
  ON synergi_partner_workspaces(org_id, admission_id);

CREATE INDEX IF NOT EXISTS idx_synergi_partner_workspaces_status
  ON synergi_partner_workspaces(org_id, workspace_status);

CREATE INDEX IF NOT EXISTS idx_synergi_partner_workspaces_focus
  ON synergi_partner_workspaces USING GIN (collaboration_focus);

CREATE INDEX IF NOT EXISTS idx_synergi_partner_opportunities_workspace
  ON synergi_partner_opportunities(workspace_id, created_at DESC);

ALTER TABLE synergi_partner_workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE synergi_partner_opportunities ENABLE ROW LEVEL SECURITY;

CREATE POLICY "org_isolation_synergi_partner_workspaces"
  ON synergi_partner_workspaces
  USING (org_id = current_setting('app.org_id', true)::UUID);

CREATE POLICY "org_isolation_synergi_partner_opportunities"
  ON synergi_partner_opportunities
  USING (org_id = current_setting('app.org_id', true)::UUID);

COMMENT ON TABLE synergi_partner_workspaces IS
  'Controlled-access partner workspace for approved Synergi collaborators.';

COMMENT ON TABLE synergi_partner_opportunities IS
  'Partner-submitted opportunities and referrals from the Synergi workspace.';
