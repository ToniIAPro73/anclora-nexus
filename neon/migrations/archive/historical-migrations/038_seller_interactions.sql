-- Migration 038: Seller Interactions — Gravity Claw Interaction Memory
-- Stores every interaction with a seller prospect (calls, emails, WhatsApps,
-- meetings, notes, AI-generated email drafts and dossiers).
-- Enables the agent to resume conversations months later with full context.

CREATE TABLE IF NOT EXISTS seller_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    seller_id UUID NOT NULL REFERENCES nexus_sellers(id) ON DELETE CASCADE,

    -- Interaction classification
    tipo TEXT NOT NULL CHECK (tipo IN (
        'llamada',       -- Phone call
        'email',         -- Email sent/received
        'whatsapp',      -- WhatsApp message
        'reunion',       -- In-person or video meeting
        'nota',          -- Manual note by Toni
        'email_draft',   -- AI-generated draft (not yet sent)
        'dossier'        -- AI-generated captation dossier / argumentario
    )),

    estado TEXT NOT NULL DEFAULT 'realizado' CHECK (estado IN (
        'realizado',    -- Completed interaction
        'borrador',     -- Draft (pending review/send)
        'programado'    -- Scheduled (reminder)
    )),

    -- Content
    contenido TEXT NOT NULL,   -- Main content: call notes, email body, dossier text
    resultado TEXT,            -- Outcome: "interesado", "no contesta", "mandato firmado"
    metadata JSONB DEFAULT '{}',  -- Extra data: subject, duration_min, email_subject, etc.

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for common query: all interactions for a seller, most recent first
CREATE INDEX IF NOT EXISTS idx_seller_interactions_seller
    ON seller_interactions(org_id, seller_id, created_at DESC);

-- Index for filtering by type (e.g., fetch only email_drafts)
CREATE INDEX IF NOT EXISTS idx_seller_interactions_tipo
    ON seller_interactions(org_id, tipo, created_at DESC);

-- Row Level Security
ALTER TABLE seller_interactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "org_isolation_seller_interactions"
    ON seller_interactions
    USING (org_id = current_setting('app.org_id', true)::UUID);

-- Comments
COMMENT ON TABLE seller_interactions IS
    'Interaction memory for Nexus Sellers. Stores every touchpoint (calls, emails, '
    'WhatsApp, meetings, notes) plus AI-generated drafts and dossiers. '
    'Used by Gravity Claw to resume seller conversations with full context.';

COMMENT ON COLUMN seller_interactions.tipo IS
    'email_draft: AI-generated, not yet sent — requires Toni validation before sending. '
    'dossier: AI-generated captation argumentario with territorial market data.';
