CREATE TABLE IF NOT EXISTS intelligence_packs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  pack_key TEXT NOT NULL,
  pack_label TEXT NOT NULL,
  notebook_id TEXT NOT NULL,
  notebook_name TEXT NOT NULL,
  market_scope TEXT NOT NULL DEFAULT 'seller'
    CHECK (market_scope IN ('seller', 'buyer', 'mixed')),
  zone_scope TEXT[] NOT NULL DEFAULT '{}',
  language_code TEXT NOT NULL DEFAULT 'es'
    CHECK (language_code IN ('es', 'en', 'de', 'ru')),
  source_mode TEXT NOT NULL DEFAULT 'notebooklm_manual'
    CHECK (source_mode IN ('notebooklm_manual', 'live_sync_pack', 'imported_rag')),
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('draft', 'active', 'archived')),
  is_default BOOLEAN NOT NULL DEFAULT FALSE,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  last_synced_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
  UNIQUE (org_id, pack_key)
);

CREATE INDEX IF NOT EXISTS idx_intelligence_packs_org_id
  ON intelligence_packs(org_id);

CREATE INDEX IF NOT EXISTS idx_intelligence_packs_org_default
  ON intelligence_packs(org_id, is_default);

CREATE INDEX IF NOT EXISTS idx_intelligence_packs_org_status
  ON intelligence_packs(org_id, status);

CREATE UNIQUE INDEX IF NOT EXISTS idx_intelligence_packs_single_default
  ON intelligence_packs(org_id)
  WHERE is_default = TRUE;

ALTER TABLE intelligence_packs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "org_isolation_intelligence_packs"
  ON intelligence_packs
  FOR ALL
  USING (org_id::text = auth.jwt() ->> 'org_id')
  WITH CHECK (org_id::text = auth.jwt() ->> 'org_id');

CREATE OR REPLACE FUNCTION set_intelligence_pack_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = timezone('utc', now());
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_intelligence_packs_updated_at ON intelligence_packs;

CREATE TRIGGER trg_intelligence_packs_updated_at
  BEFORE UPDATE ON intelligence_packs
  FOR EACH ROW
  EXECUTE FUNCTION set_intelligence_pack_updated_at();

COMMENT ON TABLE intelligence_packs IS
  'Catalogo multi-pack de inteligencia territorial/comercial por tenant.';

COMMENT ON COLUMN intelligence_packs.pack_key IS
  'Clave estable por tenant para identificar un pack de inteligencia.';

COMMENT ON COLUMN intelligence_packs.market_scope IS
  'seller=capta vendedores, buyer=demanda compradores, mixed=uso mixto.';
