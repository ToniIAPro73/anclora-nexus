import os
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from route_helpers import flatten_routes

os.environ.setdefault("AI_RUNTIME_PROFILE", "groq-cloudflare")
os.environ.setdefault("GROQ_API_KEY", "groq-test")
os.environ.setdefault("CLOUDFLARE_ACCOUNT_ID", "cf-account-test")
os.environ.setdefault("CLOUDFLARE_API_TOKEN", "cf-token-test")
os.environ.setdefault("INTERNAL_AUDIT_SECRET", "test-secret")

from backend.api.routes.ingestion import router
from backend.api.deps import get_org_id


app = FastAPI()
app.include_router(router, prefix="/api")
app.dependency_overrides[get_org_id] = lambda: "org-1"
client = TestClient(app)


class TestIngestionRouteRegistration:
    def test_ingestion_events_endpoint_exists(self) -> None:
        routes = flatten_routes(app.routes)
        matching = [
            r for r in routes
            if hasattr(r, "path") and r.path == "/api/ingestion/events" and "GET" in r.methods
        ]
        assert len(matching) == 1

    def test_seller_signals_endpoint_exists(self) -> None:
        routes = flatten_routes(app.routes)
        matching = [
            r for r in routes
            if hasattr(r, "path") and r.path == "/api/ingestion/seller-signals" and "POST" in r.methods
        ]
        assert len(matching) == 1


class TestIngestionRouteContracts:
    @patch("backend.api.routes.ingestion.ingestion_service.get_events", new_callable=AsyncMock)
    def test_events_route_returns_filtered_payload(self, mock_get_events: AsyncMock) -> None:
        mock_get_events.return_value = [
            {
                "id": "event-1",
                "org_id": "org-1",
                "entity_type": "seller_signal",
                "external_id": "ad-1",
                "connector_name": "statefox:bridge",
                "status": "processed",
                "payload": {},
                "dedupe_key": "key-1",
            }
        ]

        response = client.get(
            "/api/ingestion/events?entity_type=seller_signal&connector_name=statefox:bridge",
        )

        assert response.status_code == 200
        assert response.json()[0]["entity_type"] == "seller_signal"

    @patch("backend.api.routes.ingestion.ingestion_service.ingest_seller_signals", new_callable=AsyncMock)
    def test_seller_signal_route_returns_payload(self, mock_ingest: AsyncMock) -> None:
        mock_ingest.return_value = {
            "status": "processed",
            "trace_id": "trace-1",
            "created": 1,
            "duplicates": 0,
            "rejected": 0,
            "failed": 0,
        }

        response = client.post(
            "/api/ingestion/seller-signals",
            json={
                "org_id": "org-1",
                "connector_name": "statefox:bridge",
                "signals": [{"direccion": "Andratx", "anuncio_url": "https://example.com/ad/1"}],
            },
        )

        assert response.status_code == 200
        assert response.json()["created"] == 1

    @patch("backend.api.routes.ingestion.ingestion_service.ingest_lead", new_callable=AsyncMock)
    def test_ingestion_leads_returns_standard_response(self, mock_ingest_lead: AsyncMock) -> None:
        mock_ingest_lead.return_value = {
            "id": "lead-123",
            "status": "processed",
            "message": "Lead ingested successfully",
            "event_id": "event-123",
            "lead_id": "lead-123",
            "trace_id": "trace-123",
        }

        response = client.post(
            "/api/ingestion/leads",
            json={
                "org_id": "org-1",
                "external_id": "ext-1",
                "source_system": "cta_web",
                "source_channel": "website",
                "name": "Lead Test",
                "email": "lead@example.com",
                "gdpr_consent": True,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "processed"
        assert body["message"] == "Lead ingested successfully"
        assert body["id"] == "lead-123"

    @patch("backend.api.routes.ingestion.ingestion_service.ingest_lead", new_callable=AsyncMock)
    def test_ingestion_leads_rejects_missing_gdpr_consent(self, mock_ingest_lead: AsyncMock) -> None:
        mock_ingest_lead.side_effect = ValueError("gdpr_consent is required for web lead ingestion")

        response = client.post(
            "/api/ingestion/leads",
            json={
                "org_id": "org-1",
                "external_id": "ext-2",
                "source_system": "cta_web",
                "source_channel": "website",
                "name": "Lead Test",
                "email": "lead@example.com",
                "gdpr_consent": False,
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "gdpr_consent is required for web lead ingestion"
