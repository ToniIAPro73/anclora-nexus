-- Migration 044: Seller Memory Vector Embeddings
-- Adds real embedding persistence to seller_memory_records without requiring
-- a hard dependency on pgvector extension in the current release.

ALTER TABLE IF EXISTS public.seller_memory_records
    ADD COLUMN IF NOT EXISTS embedding DOUBLE PRECISION[],
    ADD COLUMN IF NOT EXISTS embedding_dimensions INTEGER,
    ADD COLUMN IF NOT EXISTS embedding_provider TEXT,
    ADD COLUMN IF NOT EXISTS embedding_model TEXT,
    ADD COLUMN IF NOT EXISTS embedding_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (embedding_status IN ('pending', 'ready', 'provider_unavailable', 'error')),
    ADD COLUMN IF NOT EXISTS embedding_generated_at TIMESTAMPTZ;

COMMENT ON COLUMN public.seller_memory_records.embedding IS
    'Real embedding vector generated from PII-redacted seller memory content.';

COMMENT ON COLUMN public.seller_memory_records.embedding_status IS
    'Embedding lifecycle: pending, ready, provider_unavailable or error.';
