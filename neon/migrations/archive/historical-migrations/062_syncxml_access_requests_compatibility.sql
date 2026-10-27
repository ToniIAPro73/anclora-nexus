-- 062_syncxml_access_requests_compatibility.sql
-- Production compatibility for the unified access request queue used by SyncXML.

create table if not exists public.access_requests (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null,
    product text not null default 'syncxml',
    source text not null default 'syncxml_landing',
    status text not null default 'pending',
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
    privacy_accepted boolean not null default false,
    gdpr_consent boolean not null default false,
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
    metadata jsonb not null default '{}'::jsonb,
    decision_email jsonb not null default '{}'::jsonb,
    lifecycle jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.access_requests add column if not exists product text not null default 'syncxml';
alter table public.access_requests add column if not exists source text not null default 'syncxml_landing';
alter table public.access_requests add column if not exists status text not null default 'pending';
alter table public.access_requests add column if not exists full_name text;
alter table public.access_requests add column if not exists email text;
alter table public.access_requests add column if not exists phone text;
alter table public.access_requests add column if not exists company text;
alter table public.access_requests add column if not exists profile_type text;
alter table public.access_requests add column if not exists service_category text;
alter table public.access_requests add column if not exists service_summary text;
alter table public.access_requests add column if not exists intended_use text;
alter table public.access_requests add column if not exists requested_scope text;
alter table public.access_requests add column if not exists message text;
alter table public.access_requests add column if not exists privacy_accepted boolean not null default false;
alter table public.access_requests add column if not exists gdpr_consent boolean not null default false;
alter table public.access_requests add column if not exists submission_language text not null default 'es';
alter table public.access_requests add column if not exists external_id text;
alter table public.access_requests add column if not exists captcha_provider text;
alter table public.access_requests add column if not exists captcha_verified boolean not null default false;
alter table public.access_requests add column if not exists captcha_hostname text;
alter table public.access_requests add column if not exists reviewed_at timestamptz;
alter table public.access_requests add column if not exists reviewed_by text;
alter table public.access_requests add column if not exists admin_notes text;
alter table public.access_requests add column if not exists rejection_reason text;
alter table public.access_requests add column if not exists invite_token text;
alter table public.access_requests add column if not exists invite_expires_at timestamptz;
alter table public.access_requests add column if not exists metadata jsonb not null default '{}'::jsonb;
alter table public.access_requests add column if not exists decision_email jsonb not null default '{}'::jsonb;
alter table public.access_requests add column if not exists lifecycle jsonb not null default '{}'::jsonb;
alter table public.access_requests add column if not exists created_at timestamptz not null default now();
alter table public.access_requests add column if not exists updated_at timestamptz not null default now();

alter table public.access_requests drop constraint if exists access_requests_product_check;
alter table public.access_requests
    add constraint access_requests_product_check
    check (product in ('synergi', 'data_lab', 'syncxml'));

alter table public.access_requests drop constraint if exists access_requests_source_check;
alter table public.access_requests
    add constraint access_requests_source_check
    check (source in ('landing', 'synergi_app', 'data_lab_app', 'syncxml_landing'));

alter table public.access_requests drop constraint if exists access_requests_status_check;
alter table public.access_requests
    add constraint access_requests_status_check
    check (status in ('pending', 'approved', 'rejected', 'cancelled'));

alter table public.access_requests drop constraint if exists check_source_product_coherence;
alter table public.access_requests
    add constraint check_source_product_coherence
    check (
        (source = 'synergi_app' and product = 'synergi') or
        (source = 'data_lab_app' and product = 'data_lab') or
        (source = 'syncxml_landing' and product = 'syncxml') or
        (source = 'landing')
    );

create index if not exists idx_access_requests_status_created_at
    on public.access_requests(status, created_at desc);
create index if not exists idx_access_requests_product_status
    on public.access_requests(product, status);
create index if not exists idx_access_requests_email
    on public.access_requests(lower(email));
create unique index if not exists idx_access_requests_external_id
    on public.access_requests(external_id)
    where external_id is not null;

alter table public.access_requests enable row level security;

drop policy if exists "Service role and internal admins full access" on public.access_requests;
create policy "Service role and internal admins full access"
    on public.access_requests
    for all
    to service_role
    using (true)
    with check (true);

alter table public.tasks add column if not exists task_type text;
alter table public.tasks add column if not exists origin text;
alter table public.tasks add column if not exists entity_type text;
alter table public.tasks add column if not exists entity_id text;
alter table public.tasks add column if not exists metadata jsonb not null default '{}'::jsonb;

create index if not exists idx_tasks_syncxml_review
    on public.tasks(org_id, task_type, status, created_at desc)
    where task_type = 'syncxml_pilot_review';
