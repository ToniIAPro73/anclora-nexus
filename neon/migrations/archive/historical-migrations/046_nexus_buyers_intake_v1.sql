ALTER TABLE buyer_profiles
  ADD COLUMN IF NOT EXISTS source_type TEXT NOT NULL DEFAULT 'manual'
    CHECK (source_type IN ('partner_referral', 'crm_reactivation', 'web_inbound', 'paid_lead', 'manual', 'portal_signal'));

ALTER TABLE buyer_profiles
  ADD COLUMN IF NOT EXISTS source_platform TEXT NOT NULL DEFAULT 'manual'
    CHECK (source_platform IN ('exp_agent', 'external_agent', 'crm', 'web', 'meta', 'google', 'whatsapp', 'email', 'idealista', 'manual', 'other'));

ALTER TABLE buyer_profiles
  ADD COLUMN IF NOT EXISTS referral_partner_name TEXT;

ALTER TABLE buyer_profiles
  ADD COLUMN IF NOT EXISTS referral_partner_contact TEXT;

ALTER TABLE buyer_profiles
  ADD COLUMN IF NOT EXISTS referral_partner_type TEXT
    CHECK (referral_partner_type IN ('exp_agent', 'external_agent', 'broker', 'partner', 'family_office', 'relocation'));

ALTER TABLE buyer_profiles
  ADD COLUMN IF NOT EXISTS referral_terms TEXT;

ALTER TABLE buyer_profiles
  ADD COLUMN IF NOT EXISTS buyer_intro_status TEXT NOT NULL DEFAULT 'new'
    CHECK (buyer_intro_status IN ('new', 'introduced', 'qualified', 'viewing', 'closed'));

ALTER TABLE buyer_profiles
  ADD COLUMN IF NOT EXISTS trust_score NUMERIC(5,2);

ALTER TABLE buyer_profiles
  ADD COLUMN IF NOT EXISTS intent_score NUMERIC(5,2);

ALTER TABLE buyer_profiles
  ADD COLUMN IF NOT EXISTS capacity_score NUMERIC(5,2);

ALTER TABLE buyer_profiles
  ADD COLUMN IF NOT EXISTS intelligence_pack_id UUID REFERENCES intelligence_packs(id) ON DELETE SET NULL;

ALTER TABLE buyer_profiles
  ADD COLUMN IF NOT EXISTS source_details JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE buyer_profiles
  ADD COLUMN IF NOT EXISTS last_partner_touch_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_buyer_profiles_org_source_type
  ON buyer_profiles(org_id, source_type);

CREATE INDEX IF NOT EXISTS idx_buyer_profiles_org_source_platform
  ON buyer_profiles(org_id, source_platform);

CREATE INDEX IF NOT EXISTS idx_buyer_profiles_pack
  ON buyer_profiles(intelligence_pack_id);

COMMENT ON COLUMN buyer_profiles.source_type IS
  'Fuente principal del buyer: referral, reactivacion CRM, inbound web, paid, manual o portal signal.';

COMMENT ON COLUMN buyer_profiles.source_platform IS
  'Plataforma u origen operativo del buyer.';
