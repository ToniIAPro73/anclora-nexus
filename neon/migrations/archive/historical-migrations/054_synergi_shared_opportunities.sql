create table if not exists public.synergi_partner_shared_opportunities (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references public.organizations(id) on delete cascade,
    workspace_id uuid not null references public.synergi_partner_workspaces(id) on delete cascade,
    title text not null,
    summary text not null,
    opportunity_type text not null,
    target_zone text,
    budget_context text,
    next_step text,
    status text not null default 'shared' check (status = any (array['shared'::text, 'interested'::text, 'declined'::text, 'archived'::text])),
    created_by_user_id uuid,
    created_at timestamptz not null default timezone('utc'::text, now()),
    updated_at timestamptz not null default timezone('utc'::text, now())
);

create index if not exists idx_synergi_partner_shared_opportunities_workspace
    on public.synergi_partner_shared_opportunities (workspace_id, created_at desc);

alter table public.synergi_partner_shared_opportunities enable row level security;

drop policy if exists "org_isolation_synergi_partner_shared_opportunities" on public.synergi_partner_shared_opportunities;
create policy "org_isolation_synergi_partner_shared_opportunities"
    on public.synergi_partner_shared_opportunities
    using (org_id = current_setting('app.org_id', true)::uuid);

comment on table public.synergi_partner_shared_opportunities is
    'Opportunities explicitly shared from Anclora to approved Synergi partners.';
