-- Migration 043: Seller Memory Semantic Recall
-- Derives semantic memory records from seller_interactions with PII-redacted content.

CREATE TABLE IF NOT EXISTS public.seller_memory_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    seller_id UUID NOT NULL REFERENCES public.nexus_sellers(id) ON DELETE CASCADE,
    interaction_id UUID REFERENCES public.seller_interactions(id) ON DELETE SET NULL,
    memory_kind TEXT NOT NULL CHECK (memory_kind IN ('interaction', 'outreach', 'artifact', 'followup')),
    source_type TEXT NOT NULL,
    source_artifact TEXT,
    summary TEXT NOT NULL,
    redacted_content TEXT NOT NULL,
    semantic_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    keywords TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    salience_score INTEGER NOT NULL DEFAULT 50 CHECK (salience_score >= 0 AND salience_score <= 100),
    source_created_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_seller_memory_records_org_interaction
    ON public.seller_memory_records (org_id, interaction_id)
    WHERE interaction_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_seller_memory_records_seller_created
    ON public.seller_memory_records (org_id, seller_id, source_created_at DESC);

CREATE INDEX IF NOT EXISTS idx_seller_memory_records_kind
    ON public.seller_memory_records (org_id, seller_id, memory_kind, source_created_at DESC);

CREATE INDEX IF NOT EXISTS idx_seller_memory_records_keywords
    ON public.seller_memory_records USING GIN (keywords);

ALTER TABLE public.seller_memory_records ENABLE ROW LEVEL SECURITY;

CREATE POLICY "org_isolation_seller_memory_records"
    ON public.seller_memory_records
    USING (org_id = current_setting('app.org_id', true)::UUID);

COMMENT ON TABLE public.seller_memory_records IS
    'Derived seller-side semantic memory built from seller_interactions with PII-redacted content.';
