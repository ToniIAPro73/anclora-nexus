-- 074_lead_pipeline_alert_scope.sql
-- Extends automation_alerts alert_scope constraint to include lead_pipeline and advisor_ai scopes.
-- Required for Command Center event emission on temperature/owner changes (Requirement 14.2)
-- and staleness alerts (Requirement 14.4).

-- Drop the existing check constraint on alert_scope and replace with an expanded one.
-- The column-level CHECK from migration 042 is unnamed, so we drop all checks on the column.
ALTER TABLE IF EXISTS public.automation_alerts
  DROP CONSTRAINT IF EXISTS automation_alerts_alert_scope_check;

-- Re-add with expanded scope list
ALTER TABLE IF EXISTS public.automation_alerts
  ADD CONSTRAINT automation_alerts_alert_scope_check
    CHECK (alert_scope IN (
      'rule',
      'territorial_sync',
      'territorial_pipeline',
      'source_connector',
      'advisor_ai',
      'lead_pipeline'
    ));
