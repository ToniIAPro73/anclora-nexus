-- Migration 036: NotebookLM Intelligence Cache
-- Stores insights queried from NotebookLM via MCP for backend consumption.
-- NotebookLM MCP is not callable from the production backend (uses browser session),
-- so Claude Code queries it and writes results here for the API to serve.

CREATE TABLE IF NOT EXISTS notebooklm_insights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- NotebookLM reference
    notebook_id TEXT NOT NULL,
    notebook_name TEXT NOT NULL DEFAULT 'Anclora Nexus Territorial Brain',

    -- Query and response
    query TEXT NOT NULL,
    response TEXT NOT NULL,

    -- Classification
    insight_type TEXT NOT NULL CHECK (insight_type IN (
        'territorial',      -- Oportunidades/vulnerabilidades de zona
        'cma',              -- Análisis Comparativo de Mercado
        'competitive',      -- Benchmarking competitivo
        'whale_audit',      -- Auditoría privada por seller VIP
        'buyer_profile',    -- Perfil de comprador internacional
        'market_signal'     -- Señal puntual de mercado
    )),

    -- Geographic context
    zona TEXT CHECK (zona IN (
        'andratx', 'calvia', 'son_ferrer', 'santa_ponca',
        'paguera', 'portals_nous', 'bendinat', 'punta_negra',
        'costa_den_blanes', 'port_adriano', 'palma', 'general'
    )),

    -- Additional metadata (urgency level, related seller_id, etc.)
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_notebooklm_insights_org_type
    ON notebooklm_insights(org_id, insight_type);

CREATE INDEX IF NOT EXISTS idx_notebooklm_insights_org_zona
    ON notebooklm_insights(org_id, zona);

CREATE INDEX IF NOT EXISTS idx_notebooklm_insights_created
    ON notebooklm_insights(created_at DESC);

-- Row Level Security
ALTER TABLE notebooklm_insights ENABLE ROW LEVEL SECURITY;

CREATE POLICY "org_isolation_notebooklm_insights"
    ON notebooklm_insights
    USING (org_id = current_setting('app.org_id', true)::UUID);

-- Comments
COMMENT ON TABLE notebooklm_insights IS
    'Cache of intelligence insights queried from NotebookLM via MCP. '
    'NotebookLM is not directly accessible from the backend — '
    'Claude Code queries it and writes results here for API consumption.';

COMMENT ON COLUMN notebooklm_insights.insight_type IS
    'Classification: territorial=zone opportunities, cma=market analysis, '
    'competitive=benchmarking, whale_audit=per-seller private notebook, '
    'buyer_profile=international buyer intel, market_signal=point-in-time signal';

COMMENT ON COLUMN notebooklm_insights.zona IS
    'Geographic zone of Suroeste Mallorca this insight refers to. '
    'NULL or general for cross-zone insights.';
