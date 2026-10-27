alter table public.synergi_partner_workspaces
    add column if not exists preferred_opportunity_types text[] not null default array[]::text[],
    add column if not exists priority_zones text[] not null default array[]::text[],
    add column if not exists contact_preferences text[] not null default array[]::text[],
    add column if not exists response_commitment_hours integer,
    add column if not exists profile_notes text,
    add column if not exists last_profile_update_at timestamptz;

create table if not exists public.synergi_partner_activity (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references public.organizations(id) on delete cascade,
    workspace_id uuid not null references public.synergi_partner_workspaces(id) on delete cascade,
    event_type text not null,
    title text not null,
    description text,
    related_opportunity_id uuid references public.synergi_partner_opportunities(id) on delete set null,
    created_at timestamptz not null default timezone('utc'::text, now())
);

create index if not exists idx_synergi_partner_activity_workspace_created
    on public.synergi_partner_activity (workspace_id, created_at desc);

alter table public.synergi_partner_activity enable row level security;

drop policy if exists "org_isolation_synergi_partner_activity" on public.synergi_partner_activity;
create policy "org_isolation_synergi_partner_activity"
    on public.synergi_partner_activity
    using (org_id = current_setting('app.org_id', true)::uuid);

comment on table public.synergi_partner_activity is
    'Partner-side activity feed for Synergi workspace v2.';
