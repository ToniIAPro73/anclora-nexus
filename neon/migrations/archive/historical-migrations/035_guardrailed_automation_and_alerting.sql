-- ANCLORA-GAA-001
-- Guardrailed Automation and Alerting v1
-- Additive and reversible schema objects.

create table if not exists public.automation_rules (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organizations(id) on delete cascade,
  name text not null,
  status text not null default 'active' check (status in ('active', 'paused', 'disabled')),
  event_type text not null,
  channel text not null,
  action_type text not null,
  schedule_cron text null,
  max_cost_eur_per_run numeric(12,2) not null default 0 check (max_cost_eur_per_run >= 0),
  requires_human_checkpoint boolean not null default true,
  conditions jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_automation_rules_org_status
  on public.automation_rules (org_id, status);

create index if not exists idx_automation_rules_org_updated
  on public.automation_rules (org_id, updated_at desc);

create table if not exists public.automation_executions (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organizations(id) on delete cascade,
  rule_id uuid not null references public.automation_rules(id) on delete cascade,
  status text not null check (status in ('executed', 'blocked')),
  decision text not null check (decision in ('allow', 'blocked')),
  reasons jsonb not null default '[]'::jsonb,
  cost_estimate_eur numeric(12,2) not null default 0 check (cost_estimate_eur >= 0),
  event_payload jsonb not null default '{}'::jsonb,
  trace_id uuid not null default gen_random_uuid(),
  created_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_automation_exec_org_status
  on public.automation_executions (org_id, status);

create index if not exists idx_automation_exec_org_created
  on public.automation_executions (org_id, created_at desc);

create index if not exists idx_automation_exec_rule_created
  on public.automation_executions (rule_id, created_at desc);

create table if not exists public.automation_alerts (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organizations(id) on delete cascade,
  rule_id uuid not null references public.automation_rules(id) on delete cascade,
  alert_type text not null,
  message text not null,
  is_active boolean not null default true,
  created_at timestamptz not null default timezone('utc', now()),
  resolved_at timestamptz null
);

create index if not exists idx_automation_alerts_org_active
  on public.automation_alerts (org_id, is_active);

create index if not exists idx_automation_alerts_org_created
  on public.automation_alerts (org_id, created_at desc);
