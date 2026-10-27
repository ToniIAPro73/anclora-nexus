create table if not exists public.data_lab_access_requests (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references public.organizations(id) on delete cascade,
    full_name text not null,
    email text not null,
    company_name text,
    profile_type text not null check (profile_type = any (array['partner'::text, 'client'::text, 'investor'::text, 'other'::text])),
    requested_scope text not null check (requested_scope = any (array['market_brief'::text, 'partner_intelligence'::text, 'client_pack'::text, 'strategic_overview'::text])),
    intended_use text not null,
    geography_focus text[] not null default array[]::text[],
    languages text[] not null default array[]::text[],
    website_url text,
    notes text,
    submission_source text not null default 'private_estates',
    status text not null default 'submitted' check (status = any (array['submitted'::text, 'under_review'::text, 'approved'::text, 'rejected'::text])),
    approved_scope text,
    review_notes text,
    reviewed_by_user_id uuid,
    reviewed_at timestamptz,
    decision_email_sent_at timestamptz,
    created_at timestamptz not null default timezone('utc'::text, now()),
    updated_at timestamptz not null default timezone('utc'::text, now())
);

create index if not exists idx_data_lab_access_requests_org_created
    on public.data_lab_access_requests (org_id, created_at desc);

create index if not exists idx_data_lab_access_requests_status
    on public.data_lab_access_requests (org_id, status);

create table if not exists public.data_lab_access_workspaces (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references public.organizations(id) on delete cascade,
    request_id uuid not null unique references public.data_lab_access_requests(id) on delete cascade,
    access_token text not null unique,
    workspace_status text not null default 'invited' check (workspace_status = any (array['invited'::text, 'active'::text, 'paused'::text])),
    access_tier text not null default 'limited' check (access_tier = any (array['limited'::text, 'standard'::text, 'strategic'::text])),
    approved_scope text not null check (approved_scope = any (array['market_brief'::text, 'partner_intelligence'::text, 'client_pack'::text, 'strategic_overview'::text])),
    headline text,
    next_steps jsonb not null default '[]'::jsonb,
    resources jsonb not null default '[]'::jsonb,
    last_seen_at timestamptz,
    created_at timestamptz not null default timezone('utc'::text, now()),
    updated_at timestamptz not null default timezone('utc'::text, now())
);

create index if not exists idx_data_lab_access_workspaces_org
    on public.data_lab_access_workspaces (org_id, created_at desc);

create index if not exists idx_data_lab_access_workspaces_token
    on public.data_lab_access_workspaces (access_token);

alter table public.data_lab_access_requests enable row level security;
alter table public.data_lab_access_workspaces enable row level security;

drop policy if exists "org_isolation_data_lab_access_requests" on public.data_lab_access_requests;
create policy "org_isolation_data_lab_access_requests"
    on public.data_lab_access_requests
    using (org_id = current_setting('app.org_id', true)::uuid);

drop policy if exists "org_isolation_data_lab_access_workspaces" on public.data_lab_access_workspaces;
create policy "org_isolation_data_lab_access_workspaces"
    on public.data_lab_access_workspaces
    using (org_id = current_setting('app.org_id', true)::uuid);

comment on table public.data_lab_access_requests is
    'Controlled admission queue for Anclora Data Lab external access.';

comment on table public.data_lab_access_workspaces is
    'Tokenized selective Data Lab workspaces for approved external profiles.';
