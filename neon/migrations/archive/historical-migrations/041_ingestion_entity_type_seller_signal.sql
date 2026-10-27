-- Migration 041: Extend unified ingestion to seller-side signals
-- Feature ID: ANCLORA-SCUI-001 v1.0 implementation hardening

ALTER TABLE IF EXISTS public.ingestion_connectors
    DROP CONSTRAINT IF EXISTS ingestion_connectors_entity_type_check;

ALTER TABLE IF EXISTS public.ingestion_connectors
    ADD CONSTRAINT ingestion_connectors_entity_type_check
    CHECK (entity_type IN ('lead', 'property', 'seller_signal'));

ALTER TABLE IF EXISTS public.ingestion_events
    DROP CONSTRAINT IF EXISTS ingestion_events_entity_type_check;

ALTER TABLE IF EXISTS public.ingestion_events
    ADD CONSTRAINT ingestion_events_entity_type_check
    CHECK (entity_type IN ('lead', 'property', 'seller_signal'));
