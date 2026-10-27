-- 065_dms_folder_field_vault.sql
-- Adds a JSONB field vault to each DMS folder so template variables can be
-- stored once per expediente and reused across all document generations.

alter table public.real_estate_deal_folders
    add column if not exists field_vault jsonb not null default '{}';
