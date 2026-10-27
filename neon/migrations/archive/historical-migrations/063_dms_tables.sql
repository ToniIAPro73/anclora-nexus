-- 063_dms_tables.sql
-- Real estate document management: deal folders, encrypted documents, signature flows.

create table if not exists public.real_estate_deal_folders (
    id              uuid primary key default gen_random_uuid(),
    org_id          uuid not null,
    property_id     uuid,
    client_lead_id  uuid,
    seller_id       uuid,
    operation_type  text not null check (operation_type in ('compraventa', 'alquiler_temporada', 'alquiler_turistico')),
    folder_status   text not null default 'active' check (folder_status in ('active', 'completed', 'archived')),
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

create index if not exists real_estate_deal_folders_org_id_idx on public.real_estate_deal_folders (org_id);

create table if not exists public.deal_documents (
    id                  uuid primary key default gen_random_uuid(),
    folder_id           uuid not null references public.real_estate_deal_folders (id) on delete cascade,
    org_id              uuid not null,
    title               text not null,
    document_category   text not null,
    storage_path        text not null,
    file_mime_type      text not null,
    file_size_bytes     bigint not null default 0,
    sha256_hash         text,
    encryption_iv       text not null,
    encryption_auth_tag text not null,
    uploaded_by         uuid,
    compliance_status   text not null default 'pending' check (compliance_status in ('pending', 'approved', 'rejected', 'expired')),
    legal_metadata      jsonb not null default '{}',
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);

create index if not exists deal_documents_folder_id_idx on public.deal_documents (folder_id);
create index if not exists deal_documents_org_id_idx    on public.deal_documents (org_id);

create table if not exists public.document_signature_flows (
    id                      uuid primary key default gen_random_uuid(),
    document_id             uuid not null references public.deal_documents (id) on delete cascade,
    org_id                  uuid not null,
    external_provider       text not null default 'docuseal',
    external_envelope_id    text,
    signer_email            text not null,
    signer_name             text not null,
    signer_role             text not null check (signer_role in ('buyer', 'seller', 'agent', 'witness')),
    flow_status             text not null default 'pending' check (flow_status in ('pending', 'sent', 'opened', 'signed', 'declined')),
    signing_timestamp       timestamptz,
    ip_address              text,
    signed_document_path    text,
    created_at              timestamptz not null default now(),
    updated_at              timestamptz not null default now()
);

create index if not exists document_signature_flows_document_id_idx on public.document_signature_flows (document_id);
create index if not exists document_signature_flows_org_id_idx      on public.document_signature_flows (org_id);
