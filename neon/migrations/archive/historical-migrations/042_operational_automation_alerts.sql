-- ANCLORA-GAA-001 v1.1
-- Extend automation_alerts so operational alerts can be persisted without a synthetic rule.

ALTER TABLE IF EXISTS public.automation_alerts
  ALTER COLUMN rule_id DROP NOT NULL;

ALTER TABLE IF EXISTS public.automation_alerts
  ADD COLUMN IF NOT EXISTS alert_scope text NOT NULL DEFAULT 'rule'
    CHECK (alert_scope IN ('rule', 'territorial_sync', 'territorial_pipeline', 'source_connector'));

ALTER TABLE IF EXISTS public.automation_alerts
  ADD COLUMN IF NOT EXISTS severity text NOT NULL DEFAULT 'warning'
    CHECK (severity IN ('warning', 'critical'));

ALTER TABLE IF EXISTS public.automation_alerts
  ADD COLUMN IF NOT EXISTS dedupe_key text NULL;

ALTER TABLE IF EXISTS public.automation_alerts
  ADD COLUMN IF NOT EXISTS metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE IF EXISTS public.automation_alerts
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT timezone('utc', now());

CREATE UNIQUE INDEX IF NOT EXISTS idx_automation_alerts_org_dedupe_active
  ON public.automation_alerts (org_id, dedupe_key)
  WHERE is_active = true AND dedupe_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_automation_alerts_org_scope_active
  ON public.automation_alerts (org_id, alert_scope, is_active);
