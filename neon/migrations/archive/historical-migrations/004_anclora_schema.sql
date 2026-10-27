-- leads: contactos entrantes
CREATE TABLE IF NOT EXISTS leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES organizations(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),

  -- Datos del contacto
  name TEXT NOT NULL,
  email TEXT,
  phone TEXT,
  source TEXT NOT NULL, -- web, exp, referral, linkedin, cold
  property_interest TEXT,
  budget_range TEXT,
  urgency TEXT DEFAULT 'medium', -- low, medium, high, immediate

  -- Campos IA (generados por lead_intake skill)
  ai_summary TEXT,
  ai_priority INTEGER CHECK (ai_priority BETWEEN 1 AND 5),
  priority_score NUMERIC(3,2) CHECK (priority_score BETWEEN 0.0 AND 1.0),
  next_action TEXT,
  copy_email TEXT,
  copy_whatsapp TEXT,

  -- Pipeline
  status TEXT DEFAULT 'new', -- new, contacted, qualified, negotiating, won, lost
  last_contact_at TIMESTAMPTZ,
  processed_at TIMESTAMPTZ,

  notes JSONB
);

CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(org_id, status);
CREATE INDEX IF NOT EXISTS idx_leads_priority ON leads(priority_score DESC);

-- properties: propiedades captadas o prospectadas
CREATE TABLE IF NOT EXISTS properties (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES organizations(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),

  -- Ubicación
  address TEXT NOT NULL,
  city TEXT,
  postal_code TEXT,
  latitude NUMERIC(10,8),
  longitude NUMERIC(11,8),

  -- Características
  property_type TEXT, -- villa, apartment, penthouse, land, finca
  price NUMERIC,
  surface_m2 NUMERIC,
  bedrooms INTEGER,
  bathrooms INTEGER,
  features JSONB, -- {sea_view, pool, garden, garage, etc.}

  -- Estado pipeline
  status TEXT DEFAULT 'prospect', -- prospect, contacted, listed, under_offer, sold
  owner_contact JSONB,
  catastro_ref TEXT,

  -- IA
  ai_valuation NUMERIC,
  ai_valuation_confidence NUMERIC(3,2),
  prospection_score NUMERIC(3,2),

  notes JSONB,
  dossier_pdf_url TEXT
);

CREATE INDEX IF NOT EXISTS idx_properties_postal ON properties(postal_code);
CREATE INDEX IF NOT EXISTS idx_properties_status ON properties(org_id, status);

-- weekly_recaps: histórico de recaps
CREATE TABLE IF NOT EXISTS weekly_recaps (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES organizations(id),
  week_start DATE NOT NULL,
  week_end DATE NOT NULL,
  metrics JSONB NOT NULL,
  gaps JSONB,
  top_actions JSONB,
  insights TEXT,
  email_html TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
