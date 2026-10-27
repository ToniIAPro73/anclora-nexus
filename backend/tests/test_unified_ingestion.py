import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError

from backend.models.ingestion import (
    EntityType,
    HNWISourceChannel,
    IngestionStatus,
    LeadIngestionPayload,
    LeadSourceChannel,
    LeadSourceSystem,
    PropertyIngestionPayload,
    PropertySourcePortal,
    PropertySourceSystem,
    SellerSignalIngestionPayload,
)
from backend.services.ingestion_service import IngestionService
from backend.services.hnwi_scoring_service import hnwi_scoring_service


def test_lead_payload_validation() -> None:
    payload = LeadIngestionPayload(
        org_id="org-1",
        external_id="ext-lead-1",
        source_system=LeadSourceSystem.CTA_WEB,
        source_channel=LeadSourceChannel.WEBSITE,
        name="Test User",
        email="test@example.com",
        gdpr_consent=True,
    )
    assert payload.source_system == LeadSourceSystem.CTA_WEB
    assert payload.connector_name is None

    with pytest.raises(ValidationError):
        LeadIngestionPayload(
            org_id="org-1",
            external_id="ext-lead-1",
            source_system=LeadSourceSystem.CTA_WEB,
            source_channel=LeadSourceChannel.WEBSITE,
            name="Test User",
            email="not-an-email",
            gdpr_consent=True,
        )


def test_property_payload_validation() -> None:
    payload = PropertyIngestionPayload(
        org_id="org-1",
        external_id="ext-prop-1",
        source_system=PropertySourceSystem.MANUAL,
        source_portal=PropertySourcePortal.IDEALISTA,
        title="Luxury Villa",
        address="Andratx, Mallorca",
        price_eur=1500000.0,
    )
    assert payload.source_portal == PropertySourcePortal.IDEALISTA


def test_seller_signal_payload_validation() -> None:
    payload = SellerSignalIngestionPayload(
        org_id="org-1",
        connector_name="firecrawl:idealista",
        snapshot_id="snapshot-1",
        signals=[{"direccion": "Andratx", "fuente": "idealista"}],
    )
    assert payload.connector_name == "firecrawl:idealista"
    assert len(payload.signals) == 1


def test_generate_dedupe_key_uses_connector_name() -> None:
    service = IngestionService()
    a = service._generate_dedupe_key("org-1", "cta:web", EntityType.LEAD, "x")
    b = service._generate_dedupe_key("org-1", "import:web", EntityType.LEAD, "x")
    assert a != b


def test_ingestion_service_duplicate_short_circuit() -> None:
    service = IngestionService()
    payload = LeadIngestionPayload(
        org_id="org-1",
        external_id="ext-lead-dup",
        source_system=LeadSourceSystem.CTA_WEB,
        source_channel=LeadSourceChannel.WEBSITE,
        name="Duplicate User",
        gdpr_consent=True,
    )

    with patch.object(service, "_get_existing_event", return_value={"id": "event-1", "trace_id": "trace-1"}):
        result = asyncio.run(service.ingest_lead(payload))

    assert result["status"] == "duplicate"
    assert result["event_id"] == "event-1"


def test_ingestion_service_success_updates_processed_status() -> None:
    service = IngestionService()
    payload = LeadIngestionPayload(
        org_id="org-1",
        external_id="ext-lead-new",
        source_system=LeadSourceSystem.CTA_WEB,
        source_channel=LeadSourceChannel.WEBSITE,
        name="New User",
        gdpr_consent=True,
    )

    mock_table = MagicMock()
    mock_table.insert.return_value.execute.return_value.data = [{"id": "lead-1"}]
    mock_neon = MagicMock()
    mock_neon.client.table.return_value = mock_table
    service.client = mock_neon.client

    with patch("backend.services.ingestion_service.neon_service", mock_neon), \
         patch.object(service, "_get_existing_event", return_value=None), \
         patch.object(service, "_register_received", return_value={"id": "event-1"}), \
         patch.object(service, "_ensure_connector_enabled", return_value=None), \
         patch.object(service, "_update_event") as mock_update:
        result = asyncio.run(service.ingest_lead(payload))

    assert result["status"] == "processed"
    mock_update.assert_any_call("event-1", status=IngestionStatus.VALIDATED)
    mock_update.assert_any_call("event-1", status=IngestionStatus.PROCESSED, processed_entity_id="lead-1")


def test_seller_signal_ingestion_routes_to_skill() -> None:
    service = IngestionService()
    payload = SellerSignalIngestionPayload(
        org_id="org-1",
        connector_name="statefox:bridge",
        snapshot_id="snapshot-1",
        signals=[{"direccion": "Calvia", "anuncio_url": "https://example.com/ad/1"}],
    )

    with patch.object(service, "_get_existing_event", return_value=None), \
         patch.object(service, "_register_received", return_value={"id": "event-1"}), \
         patch.object(service, "_ensure_connector_enabled", return_value=None), \
         patch.object(service, "_update_event"), \
         patch("backend.services.ingestion_service.run_seller_signal_ingest", new_callable=AsyncMock) as mock_skill:
        mock_skill.return_value = {"created_ids": ["seller-1"]}
        result = asyncio.run(service.ingest_seller_signals(payload))

    assert result["status"] == "processed"
    assert result["created"] == 1


def test_hnwi_scoring_marks_hot_lead_with_verified_email() -> None:
    payload = LeadIngestionPayload(
        org_id="org-1",
        external_id="hnwi-1",
        connector_name="hnwi-prospection:linkedin",
        source_system=LeadSourceSystem.SOCIAL,
        source_channel=LeadSourceChannel.LINKEDIN,
        name="Hans Investor",
        email="hans@example.com",
        budget=3_000_000,
        property_interest="Looking for a luxury villa in Andratx",
        nationality="German",
        zone_interest="Andratx",
        email_verified=True,
    )

    result = hnwi_scoring_service.score_lead(payload)

    assert result.score >= 70
    assert result.tier == "hot"
    assert result.outreach_ready is True


def test_ingestion_service_persists_hnwi_fields_and_logs_finops() -> None:
    service = IngestionService()
    payload = LeadIngestionPayload(
        org_id="org-1",
        external_id="hnwi-2",
        connector_name="hnwi-prospection:reddit",
        source_system=LeadSourceSystem.SOCIAL,
        source_channel=LeadSourceChannel.OTHER,
        hnwi_source_channel=HNWISourceChannel.REDDIT,
        name="HNWI Lead",
        email="lead@example.com",
        budget=2_500_000,
        property_interest="Looking for a villa in Calvia",
        nationality="British",
        zone_interest="Calvia",
        email_verified=True,
    )

    mock_table = MagicMock()
    mock_table.insert.return_value.execute.return_value.data = [{"id": "lead-1"}]
    mock_neon = MagicMock()
    mock_neon.client.table.return_value = mock_table
    service.client = mock_neon.client

    with patch("backend.services.ingestion_service.neon_service", mock_neon), \
         patch("backend.services.ingestion_service.finops_service.log_usage_event", new_callable=AsyncMock) as mock_finops, \
         patch.object(service, "_get_existing_event", return_value=None), \
         patch.object(service, "_register_received", return_value={"id": "event-1"}), \
         patch.object(service, "_ensure_connector_enabled", return_value=None), \
         patch.object(service, "_update_event"):
        result = asyncio.run(service.ingest_lead(payload))

    assert result["status"] == "processed"
    lead_insert = next(
        call.args[0]
        for call in mock_table.insert.call_args_list
        if isinstance(call.args[0], dict) and call.args[0].get("name") == "HNWI Lead"
    )
    assert lead_insert["qualification_tier"] == "hot"
    assert lead_insert["email_verified"] is True
    assert lead_insert["hnwi_source_channel"] == "reddit"
    assert lead_insert["source_metadata"]["hnwi"]["outreach_ready"] is True
    mock_finops.assert_awaited_once()


def test_ingestion_service_rejects_web_lead_without_gdpr_consent() -> None:
    service = IngestionService()
    payload = LeadIngestionPayload(
        org_id="org-1",
        external_id="ext-lead-no-consent",
        source_system=LeadSourceSystem.CTA_WEB,
        source_channel=LeadSourceChannel.WEBSITE,
        name="No Consent User",
        gdpr_consent=False,
    )

    with patch.object(service, "_get_existing_event", return_value=None), \
         patch.object(service, "_register_received", return_value={"id": "event-1"}), \
         patch.object(service, "_update_event") as mock_update:
        with pytest.raises(ValueError, match="gdpr_consent is required for web lead ingestion"):
            asyncio.run(service.ingest_lead(payload))

    mock_update.assert_called_with(
        "event-1",
        status=IngestionStatus.REJECTED,
        error_code="gdpr_consent_required",
        error_message="gdpr_consent is required for web lead ingestion",
    )
