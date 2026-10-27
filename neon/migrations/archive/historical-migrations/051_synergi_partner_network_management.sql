ALTER TABLE synergi_partner_workspaces
  ADD COLUMN IF NOT EXISTS relationship_status TEXT NOT NULL DEFAULT 'active'
    CHECK (relationship_status IN ('active', 'watchlist', 'paused')),
  ADD COLUMN IF NOT EXISTS trust_score NUMERIC(5,2) NOT NULL DEFAULT 70,
  ADD COLUMN IF NOT EXISTS preferred_for_buyers BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS preferred_for_sellers BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS strategic_notes TEXT,
  ADD COLUMN IF NOT EXISTS network_tags TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[];

CREATE INDEX IF NOT EXISTS idx_synergi_partner_workspaces_relationship
  ON synergi_partner_workspaces(org_id, relationship_status);

CREATE INDEX IF NOT EXISTS idx_synergi_partner_workspaces_network_tags
  ON synergi_partner_workspaces USING GIN (network_tags);

COMMENT ON COLUMN synergi_partner_workspaces.relationship_status IS
  'Internal relationship state for Synergi partner management.';
