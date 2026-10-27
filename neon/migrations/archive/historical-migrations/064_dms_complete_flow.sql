-- 064_dms_complete_flow.sql
-- Complete DMS user flow schema.
-- Safe to run from Supabase SQL Editor after 063_dms_tables.sql.

create table if not exists public.document_templates (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null,
    name text not null,
    template_document_type text not null check (template_document_type in (
        'arras_penitenciales','contrato_compraventa','contrato_temporada',
        'contrato_alquiler_turistico','kyc_cliente','mandato_exclusiva',
        'oferta_compra','generico'
    )),
    description text,
    jurisdiction text not null default 'España',
    language text not null default 'es',
    is_global boolean not null default false,
    status text not null default 'draft' check (status in ('draft','published','deprecated')),
    created_by uuid,
    published_at timestamptz,
    deprecated_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.document_template_versions (
    id uuid primary key default gen_random_uuid(),
    template_id uuid not null references public.document_templates(id) on delete cascade,
    org_id uuid not null,
    version_number integer not null,
    storage_path text,
    source_storage_path text,
    preview_storage_path text,
    sha256_hash text,
    encryption_iv text,
    encryption_auth_tag text,
    canonical_text text,
    change_summary text,
    status text not null default 'draft' check (status in ('draft','published','deprecated')),
    published_by uuid,
    published_at timestamptz,
    immutable boolean not null default false,
    effective_from date,
    effective_until date,
    legal_reviewed_by uuid,
    legal_reviewed_at timestamptz,
    jurisdiction text not null default 'España',
    language text not null default 'es',
    created_at timestamptz not null default now(),
    unique (template_id, version_number)
);

create table if not exists public.document_template_fields (
    id uuid primary key default gen_random_uuid(),
    template_version_id uuid not null references public.document_template_versions(id) on delete cascade,
    org_id uuid not null,
    field_key text not null,
    label text not null,
    field_type text not null default 'text' check (field_type in (
        'text','number','date','amount','boolean','select'
    )),
    required boolean not null default true,
    default_value text,
    validation_rule text,
    source_path text,
    created_at timestamptz not null default now(),
    unique (template_version_id, field_key)
);

create table if not exists public.deal_folder_parties (
    id uuid primary key default gen_random_uuid(),
    folder_id uuid not null references public.real_estate_deal_folders(id) on delete cascade,
    org_id uuid not null,
    party_role text not null check (party_role in (
        'buyer','seller','agent','guarantor','co_buyer','co_seller','notary'
    )),
    full_name text not null,
    lead_id uuid,
    seller_id uuid,
    company_id uuid,
    contact_id uuid,
    source_entity text,
    source_id uuid,
    is_primary boolean not null default false,
    signing_order integer,
    representation_capacity text,
    dni_nie_passport text,
    email text,
    phone text,
    address text,
    nationality text,
    is_company boolean not null default false,
    company_name text,
    company_cif text,
    kyc_verified boolean not null default false,
    kyc_verified_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.generated_documents (
    id uuid primary key default gen_random_uuid(),
    folder_id uuid not null references public.real_estate_deal_folders(id) on delete cascade,
    org_id uuid not null,
    template_version_id uuid not null references public.document_template_versions(id),
    title text not null,
    status text not null default 'draft' check (status in (
        'draft','review_required','approved','rejected','signed','archived'
    )),
    generation_payload jsonb not null default '{}'::jsonb,
    variable_snapshot jsonb not null default '{}'::jsonb,
    storage_path text,
    docx_storage_path text,
    pdf_storage_path text,
    preview_storage_path text,
    current_version_id uuid,
    sha256_hash text,
    encryption_iv text,
    encryption_auth_tag text,
    generated_by uuid,
    generated_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.document_versions (
    id uuid primary key default gen_random_uuid(),
    generated_document_id uuid not null references public.generated_documents(id) on delete cascade,
    org_id uuid not null,
    version_number integer not null,
    storage_path text,
    docx_storage_path text,
    pdf_storage_path text,
    canonical_text text,
    sha256_hash text,
    encryption_iv text,
    encryption_auth_tag text,
    change_summary text,
    immutable boolean not null default false,
    validation_status text not null default 'pending',
    advisor_validation jsonb not null default '{}'::jsonb,
    signature_status text not null default 'not_sent',
    signed_at timestamptz,
    signed_storage_path text,
    is_signed_immutable boolean not null default false,
    created_by uuid,
    created_at timestamptz not null default now(),
    unique (generated_document_id, version_number)
);

create table if not exists public.document_change_sets (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null,
    from_version_id uuid references public.document_versions(id) on delete set null,
    to_version_id uuid not null references public.document_versions(id) on delete cascade,
    diff_payload jsonb not null default '[]'::jsonb,
    risk_level text not null default 'low' check (risk_level in ('low','medium','high','critical')),
    computed_at timestamptz not null default now()
);

create table if not exists public.legal_review_decisions (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null,
    generated_document_id uuid references public.generated_documents(id) on delete cascade,
    document_version_id uuid references public.document_versions(id) on delete set null,
    review_type text not null default 'manual' check (review_type in ('auto','manual')),
    status text not null default 'pending' check (status in ('pending','approved','review_required','rejected','escalated')),
    decision text,
    risk_level text not null default 'low' check (risk_level in ('low','medium','high','critical')),
    block_signing boolean not null default false,
    reviewer_id uuid,
    advisor_ai_request_id text,
    advisor_ai_response jsonb default '{}'::jsonb,
    notes text,
    decided_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.generated_document_signature_flows (
    id uuid primary key default gen_random_uuid(),
    generated_document_id uuid not null references public.generated_documents(id) on delete cascade,
    document_version_id uuid references public.document_versions(id) on delete set null,
    org_id uuid not null,
    external_provider text not null default 'docuseal',
    external_envelope_id text,
    signer_email text not null,
    signer_name text not null,
    signer_role text not null check (signer_role in ('buyer','seller','agent','witness')),
    flow_status text not null default 'pending' check (flow_status in ('pending','sent','opened','signed','declined')),
    signing_timestamp timestamptz,
    ip_address text,
    signed_document_path text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.document_retention_policies (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null,
    template_document_type text,
    retention_days integer not null default 2555,
    auto_archive boolean not null default true,
    auto_delete boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.real_estate_deal_folders
  add column if not exists primary_party_id uuid,
  add column if not exists completed_at timestamptz;

alter table public.deal_folder_parties
  add column if not exists lead_id uuid,
  add column if not exists seller_id uuid,
  add column if not exists company_id uuid,
  add column if not exists contact_id uuid,
  add column if not exists source_entity text,
  add column if not exists source_id uuid,
  add column if not exists is_primary boolean not null default false,
  add column if not exists signing_order integer,
  add column if not exists representation_capacity text;

alter table public.document_template_versions
  add column if not exists status text not null default 'draft',
  add column if not exists source_storage_path text,
  add column if not exists preview_storage_path text,
  add column if not exists effective_from date,
  add column if not exists effective_until date,
  add column if not exists legal_reviewed_by uuid,
  add column if not exists legal_reviewed_at timestamptz,
  add column if not exists jurisdiction text not null default 'España',
  add column if not exists language text not null default 'es';

alter table public.document_template_versions
  alter column storage_path drop not null,
  alter column sha256_hash drop not null,
  alter column encryption_iv drop not null,
  alter column encryption_auth_tag drop not null;

alter table public.generated_documents
  add column if not exists docx_storage_path text,
  add column if not exists pdf_storage_path text,
  add column if not exists preview_storage_path text,
  add column if not exists variable_snapshot jsonb not null default '{}'::jsonb,
  add column if not exists current_version_id uuid;

alter table public.document_versions
  add column if not exists docx_storage_path text,
  add column if not exists pdf_storage_path text,
  add column if not exists canonical_text text,
  add column if not exists validation_status text not null default 'pending',
  add column if not exists advisor_validation jsonb not null default '{}'::jsonb,
  add column if not exists signature_status text not null default 'not_sent',
  add column if not exists signed_at timestamptz,
  add column if not exists signed_storage_path text,
  add column if not exists is_signed_immutable boolean not null default false;

alter table public.document_versions
  alter column storage_path drop not null,
  alter column sha256_hash drop not null,
  alter column encryption_iv drop not null,
  alter column encryption_auth_tag drop not null;

alter table public.legal_review_decisions
  add column if not exists generated_document_id uuid,
  add column if not exists document_version_id uuid,
  add column if not exists decision text,
  add column if not exists block_signing boolean not null default false;

create unique index if not exists idx_deal_folder_parties_one_primary
  on public.deal_folder_parties(folder_id)
  where is_primary = true;

create index if not exists idx_document_templates_org on public.document_templates(org_id);
create index if not exists idx_document_templates_type on public.document_templates(template_document_type);
create index if not exists idx_template_versions_template on public.document_template_versions(template_id);
create index if not exists idx_template_fields_version on public.document_template_fields(template_version_id);
create index if not exists idx_folder_parties_folder on public.deal_folder_parties(folder_id);
create index if not exists idx_generated_documents_folder_status on public.generated_documents(folder_id, status);
create index if not exists idx_document_versions_generated_document_id on public.document_versions(generated_document_id);
create index if not exists idx_generated_signature_flows_document on public.generated_document_signature_flows(generated_document_id);
create index if not exists idx_legal_review_generated on public.legal_review_decisions(generated_document_id);
create index if not exists idx_retention_policies_org on public.document_retention_policies(org_id);
