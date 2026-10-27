CREATE TABLE IF NOT EXISTS public.buyer_memory_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    buyer_id UUID NOT NULL REFERENCES public.buyer_profiles(id) ON DELETE CASCADE,
    source_ref TEXT NOT NULL,
    memory_kind TEXT NOT NULL CHECK (memory_kind IN ('profile', 'match', 'activity', 'followup')),
    source_type TEXT NOT NULL,
    source_artifact TEXT,
    summary TEXT NOT NULL,
    redacted_content TEXT NOT NULL,
    semantic_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    keywords TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    salience_score INTEGER NOT NULL DEFAULT 50 CHECK (salience_score >= 0 AND salience_score <= 100),
    embedding DOUBLE PRECISION[],
    embedding_dimensions INTEGER,
    embedding_provider TEXT,
    embedding_model TEXT,
    embedding_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (embedding_status IN ('pending', 'ready', 'provider_unavailable', 'error')),
    embedding_generated_at TIMESTAMPTZ,
    source_created_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, buyer_id, source_ref)
);

CREATE INDEX IF NOT EXISTS idx_buyer_memory_records_buyer_created
    ON public.buyer_memory_records (org_id, buyer_id, source_created_at DESC);

CREATE INDEX IF NOT EXISTS idx_buyer_memory_records_kind
    ON public.buyer_memory_records (org_id, buyer_id, memory_kind, source_created_at DESC);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'buyer_memory_records'
          AND column_name = 'keywords'
          AND data_type = 'text'
    ) THEN
        ALTER TABLE public.buyer_memory_records
            ALTER COLUMN keywords DROP DEFAULT;

        ALTER TABLE public.buyer_memory_records
            ALTER COLUMN keywords TYPE TEXT[]
            USING CASE
                WHEN keywords IS NULL OR btrim(keywords) = '' THEN ARRAY[]::TEXT[]
                ELSE ARRAY[keywords]
            END;

        ALTER TABLE public.buyer_memory_records
            ALTER COLUMN keywords SET DEFAULT ARRAY[]::TEXT[];
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_buyer_memory_records_keywords
    ON public.buyer_memory_records USING GIN (keywords);

ALTER TABLE public.buyer_memory_records ENABLE ROW LEVEL SECURITY;

CREATE POLICY "org_isolation_buyer_memory_records"
    ON public.buyer_memory_records
    USING (org_id = current_setting('app.org_id', true)::UUID);

COMMENT ON TABLE public.buyer_memory_records IS
    'Buyer-side contextual memory derived from buyer profile, matches and activity log.';
