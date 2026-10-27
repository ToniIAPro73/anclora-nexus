-- Migration 057: Seller Intake Pipeline (ANCLORA-SIP-001)
-- Adds priority_score (float 0-1), intake tracking, and outreach drafts reference.

-- ─── nexus_sellers: intake + scoring columns ─────────────────────────────────

ALTER TABLE IF EXISTS public.nexus_sellers
  ADD COLUMN IF NOT EXISTS priority_score FLOAT
    CHECK (priority_score IS NULL OR (priority_score >= 0 AND priority_score <= 1)),
  ADD COLUMN IF NOT EXISTS priority_computed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS intake_raw_data JSONB NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS intake_processed_at TIMESTAMPTZ;

COMMENT ON COLUMN public.nexus_sellers.priority_score IS
  'Computed 0-1 score: budget×0.35 + urgency×0.25 + property_fit×0.25 + source_quality×0.15';
COMMENT ON COLUMN public.nexus_sellers.priority_computed_at IS
  'Timestamp of last priority_score computation.';
COMMENT ON COLUMN public.nexus_sellers.intake_raw_data IS
  'Raw payload received at intake (StateFox, FSBO scraper, web form).';
COMMENT ON COLUMN public.nexus_sellers.intake_processed_at IS
  'Timestamp when raw intake was processed into structured seller record.';

-- Index for efficient pending-approval queries (sellers with pending drafts by tier)
CREATE INDEX IF NOT EXISTS idx_nexus_sellers_org_priority_score
  ON public.nexus_sellers (org_id, priority_score DESC NULLS LAST)
  WHERE estado_contacto != 'descartado';

-- ─── seller_outreach_drafts: HITL approval queue ─────────────────────────────
-- Normalized table for outreach drafts awaiting human approval, linked to
-- seller_interactions. Allows cross-seller pending-approval queries in O(1).

CREATE TABLE IF NOT EXISTS public.seller_outreach_drafts (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           UUID NOT NULL,
  seller_id        UUID NOT NULL REFERENCES public.nexus_sellers(id) ON DELETE CASCADE,
  interaction_id   UUID,                           -- FK to seller_interactions once created
  email_draft      TEXT,
  whatsapp_draft   TEXT,
  status           TEXT NOT NULL DEFAULT 'draft'
                     CHECK (status IN ('draft', 'approved', 'sent', 'rejected')),
  priority_tier    INT CHECK (priority_tier BETWEEN 1 AND 5),
  approved_by      UUID,
  approved_at      TIMESTAMPTZ,
  rejection_reason TEXT,
  agent_comments   TEXT,
  job_id           UUID,                           -- async send job reference
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_seller_outreach_drafts_org_status
  ON public.seller_outreach_drafts (org_id, status, priority_tier DESC NULLS LAST, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_seller_outreach_drafts_seller
  ON public.seller_outreach_drafts (seller_id);

COMMENT ON TABLE public.seller_outreach_drafts IS
  'HITL outreach approval queue. Populated by the seller intake pipeline.';
