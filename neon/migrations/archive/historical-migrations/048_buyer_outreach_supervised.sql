CREATE TABLE IF NOT EXISTS public.buyer_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    buyer_id UUID NOT NULL REFERENCES public.buyer_profiles(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL CHECK (tipo IN ('call', 'email', 'whatsapp', 'note', 'buyer_brief', 'email_draft', 'whatsapp_draft')),
    contenido TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'realizado' CHECK (estado IN ('programado', 'realizado')),
    resultado TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_buyer_interactions_buyer_created
    ON public.buyer_interactions (org_id, buyer_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_buyer_interactions_tipo
    ON public.buyer_interactions (org_id, buyer_id, tipo, created_at DESC);

ALTER TABLE public.buyer_interactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "org_isolation_buyer_interactions"
    ON public.buyer_interactions
    USING (org_id = current_setting('app.org_id', true)::UUID);

COMMENT ON TABLE public.buyer_interactions IS
    'Buyer-side supervised outreach interactions, drafts and briefs.';
