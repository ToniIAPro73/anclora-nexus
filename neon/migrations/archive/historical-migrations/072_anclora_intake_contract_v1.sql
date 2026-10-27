-- supabase/migrations/072_anclora_intake_contract_v1.sql
-- Forward-only migration: add Anclora Intake Contract v1 fields to access_requests
-- and lead_intake tables. All columns are additive — no existing data is removed.
-- Backfill sets sensible defaults from existing column values.

-- ─── access_requests: new contract fields ───────────────────────────────────

alter table public.access_requests
    add column if not exists schema_version text not null default 'anclora-intake-v1',
    add column if not exists intake_domain text not null default 'access_request'
        check (intake_domain in ('access_request', 'commercial_lead')),
    add column if not exists request_type text
        check (request_type in (
            'pilot_request', 'access_request', 'partner_admission', 'workspace_access_request',
            'seller_valuation_request', 'seller_lead', 'buyer_lead',
            'property_inquiry', 'general_commercial_inquiry',
            'vacation_rental_management_interest'
        )),
    add column if not exists service_interest text
        check (service_interest in (
            'property_sale', 'property_purchase', 'property_valuation',
            'vacation_rental_management', 'document_management',
            'energy_assessment', 'other'
        )),
    add column if not exists idempotency_key text,
    add column if not exists routing_target_domain text
        check (routing_target_domain in ('access_requests', 'leads', 'valuations', 'buyers'));

-- Ensure idempotency uniqueness (null-safe: multiple nulls are allowed in PG)
create unique index if not exists idx_access_requests_idempotency_key
    on public.access_requests(idempotency_key)
    where idempotency_key is not null;

-- ─── access_requests: backfill request_type from product ────────────────────

update public.access_requests
set request_type = case
    when product = 'syncxml' then 'pilot_request'
    when product = 'synergi' then 'partner_admission'
    when product = 'data_lab' then 'access_request'
    else null
end
where request_type is null;

-- ─── access_requests: backfill routing_target_domain ───────────────────────

update public.access_requests
set routing_target_domain = 'access_requests'
where routing_target_domain is null
  and intake_domain = 'access_request';

-- ─── access_requests: fix ambiguous source 'landing' ───────────────────────
-- Rows with source='landing' predated the per-product source values.
-- We can infer from product which source they likely came from.
-- We do NOT invent a source we cannot prove; rows that genuinely cannot be
-- determined are left as 'landing' (legacy) and noted in metadata.

update public.access_requests
set source = case
    when product = 'syncxml' and source = 'landing' then 'syncxml_landing'
    when product = 'synergi' and source = 'landing' then 'synergi_app'
    when product = 'data_lab' and source = 'landing' then 'data_lab_app'
    else source
end
where source = 'landing';

-- ─── lead_intake: new contract fields (if table exists) ─────────────────────
-- lead_intake stores commercial leads; add intake_domain for cross-domain clarity.

do $$
begin
    if exists (select 1 from information_schema.tables
               where table_schema = 'public' and table_name = 'lead_intake') then

        alter table public.lead_intake
            add column if not exists schema_version text not null default 'anclora-intake-v1',
            add column if not exists intake_domain text not null default 'commercial_lead'
                check (intake_domain in ('access_request', 'commercial_lead')),
            add column if not exists request_type text,
            add column if not exists service_interest text,
            add column if not exists idempotency_key text,
            add column if not exists routing_target_domain text;

        create unique index if not exists idx_lead_intake_idempotency_key
            on public.lead_intake(idempotency_key)
            where idempotency_key is not null;

    end if;
end $$;

-- ─── Indexes ─────────────────────────────────────────────────────────────────

create index if not exists idx_access_requests_intake_domain
    on public.access_requests(intake_domain, status, created_at desc);

create index if not exists idx_access_requests_request_type
    on public.access_requests(request_type, status, created_at desc);
