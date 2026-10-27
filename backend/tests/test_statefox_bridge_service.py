import asyncio
import os
from unittest.mock import AsyncMock, patch


from backend.services import statefox_bridge_service


RAW_STATEFOX_SAMPLE = """
1.250.000€ | Piso en Palma | [app] 3 hab 2 baños 120 m2 particular WhatsApp 612 345 678 urgente
https://es.statefox.com/public/ln/property/demo-1
""".strip()


def test_parse_statefox_raw_detects_seller_candidate() -> None:
    parsed = statefox_bridge_service.parse_statefox_raw(RAW_STATEFOX_SAMPLE)

    assert parsed["count"] == 1
    assert parsed["seller_candidate_count"] == 1
    listing = parsed["listings"][0]
    assert listing["routing"]["create_seller"] is True
    assert listing["telefono_contacto"] == "612345678"
    assert "whatsapp_disponible" in listing["seller_signals"]


def test_import_statefox_listings_routes_seller_candidates() -> None:
    with patch.object(statefox_bridge_service, "_property_exists", return_value=False), \
         patch.object(statefox_bridge_service.prospection_service, "create_property", new_callable=AsyncMock) as mock_create_property, \
         patch.object(statefox_bridge_service.ingestion_service, "ingest_seller_signals", new_callable=AsyncMock) as mock_ingest:
        mock_create_property.return_value = {"id": "prop-1"}
        mock_ingest.return_value = {
            "status": "processed",
            "created": 1,
            "duplicates": 0,
            "rejected": 0,
            "failed": 0,
            "event_ids": ["event-1"],
        }

        result = asyncio.run(
            statefox_bridge_service.import_statefox_listings(
                org_id="org-1",
                raw_text=RAW_STATEFOX_SAMPLE,
                zone="palma",
                city="Palma",
            )
        )

    assert result["imported_count"] == 1
    assert result["seller_candidate_count"] == 1
    assert result["sellers_imported_count"] == 1
    payload = mock_ingest.await_args.args[0]
    assert payload.connector_name == "statefox:telegram-bridge"
    assert payload.signals[0].anuncio_url == "https://es.statefox.com/public/ln/property/demo-1"
    assert payload.signals[0].telefono_contacto == "612345678"
