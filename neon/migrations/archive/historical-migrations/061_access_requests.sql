-- supabase/migrations/061_access_requests.sql
create table if not exists access_requests (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null,
    product text not null check (product in ('synergi', 'data_lab')),
    source text not null check (source in ('landing', 'synergi_app', 'data_lab_app')),
    status text not null default 'pending' check (status in ('pending', 'approved', 'rejected', 'cancelled')),
    full_name text not null,
    email text not null,
    phone text,
    company text,
    profile_type text,
    service_category text,
    service_summary text,
    intended_use text,
    requested_scope text,
    message text,
    privacy_accepted boolean not null default false check (privacy_accepted = true),
    gdpr_consent boolean not null default false check (gdpr_consent = true),
    submission_language text not null default 'es',
    external_id text,
    captcha_provider text,
    captcha_verified boolean not null default false,
    captcha_hostname text,
    reviewed_at timestamptz,
    reviewed_by text,
    admin_notes text,
    rejection_reason text,
    invite_token text,
    invite_expires_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    -- Consistency constraints
    constraint check_source_product_coherence check (
        (source = 'synergi_app' and product = 'synergi') or
        (source = 'data_lab_app' and product = 'data_lab') or
        (source = 'landing')
    )
);

create index idx_access_requests_status_created_at on access_requests(status, created_at desc);
create index idx_access_requests_product_status on access_requests(product, status);
create index idx_access_requests_email on access_requests(lower(email));
create unique index idx_access_requests_external_id on access_requests(external_id) where external_id is not null;

-- RLS
alter table access_requests enable row level security;

-- Policy for service role and internal admins
create policy "Service role and internal admins full access"
    on access_requests
    for all
    to service_role
    using (true)
    with check (true);
