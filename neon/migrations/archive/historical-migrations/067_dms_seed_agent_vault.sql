-- 067_dms_seed_agent_vault.sql
-- Adds agent.* fallback fields to the 3 test folders' field_vault.
-- Without this, agent fields are only resolved from the logged-in user's profile,
-- which may be empty in test environments.
-- Safe to re-run (merges into existing vault with jsonb ||).

DO $$
DECLARE
  f_cv UUID := 'd0000000-0000-0000-0000-000000000001';
  f_at UUID := 'd0000000-0000-0000-0000-000000000002';
  f_tu UUID := 'd0000000-0000-0000-0000-000000000003';

  agent_data jsonb := '{
    "agent.full_name": "Carlos Mendoza Ruiz",
    "agent.email":     "c.mendoza@anclora.es",
    "agent.phone":     "+34 971 456 789",
    "agent.license":   "API-IB-2019-0234"
  }';
BEGIN

UPDATE public.real_estate_deal_folders
SET field_vault = field_vault || agent_data, updated_at = now()
WHERE id IN (f_cv, f_at, f_tu);

END $$;
