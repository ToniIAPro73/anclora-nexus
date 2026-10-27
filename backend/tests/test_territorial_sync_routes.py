import os
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from route_helpers import flatten_routes

os.environ.setdefault("AI_RUNTIME_PROFILE", "groq-cloudflare")
os.environ.setdefault("GROQ_API_KEY", "groq-test")
os.environ.setdefault("CLOUDFLARE_ACCOUNT_ID", "cf-account-test")
os.environ.setdefault("CLOUDFLARE_API_TOKEN", "cf-token-test")
os.environ.setdefault("INTERNAL_AUDIT_SECRET", "test-secret")

from backend.api.routes.intelligence import router


app = FastAPI()
app.include_router(router, prefix="/api/intelligence")
client = TestClient(app)


class TestTerritorialSyncRouteRegistration:
    def test_territorial_sync_status_endpoint_exists(self) -> None:
        routes = flatten_routes(app.routes)
        matching = [
            r for r in routes
            if hasattr(r, "path") and r.path == "/api/intelligence/territorial-sync-status" and "GET" in r.methods
        ]
        assert len(matching) == 1


class TestTerritorialSyncRouteContract:
    @patch("backend.api.routes.intelligence.get_territorial_sync_status")
    def test_territorial_sync_status_returns_payload(self, mock_status) -> None:
        mock_status.return_value = {
            "feature_id": "ANCLORA-TSCP-001.v1",
            "status": "ready",
            "generated_at": "2026-03-09T00:00:00Z",
            "notebook_name": "Inteligencia Territorial Suroeste Mallorca 2026",
            "freshness_state": "fresh",
            "next_refresh_due_at": "2026-03-13T00:00:00Z",
            "next_action": "Mantener la cadencia operativa y revalidar el sync pack en la siguiente ventana planificada.",
            "operational_contract": {
                "owner_display": "Owner / Ops (Toni)",
                "schedule": {"cadence": "twice_weekly", "timezone": "Europe/Madrid"},
            },
            "coverage": {"query_count": 4, "zones": ["general", "calvia"]},
            "source_refs": ["ops/notebooklm-territorial-sync-raw.json"],
            "warnings": [],
            "errors": [],
        }

        with patch("backend.api.routes.intelligence.get_territorial_pipeline_status") as mock_pipeline:
            mock_pipeline.return_value = {
                "feature_id": "ANCLORA-TSCP-001.pipeline.v1",
                "status": "success",
                "finished_at": "2026-03-10T00:30:00Z",
                "stats": {
                    "sellers_created": 2,
                    "signals_received": 4,
                    "queries_synced": 4,
                    "outreach_processed": 1,
                },
            }
            response = client.get("/api/intelligence/territorial-sync-status")

        assert response.status_code == 200
        body = response.json()
        assert body["sync_status"]["status"] == "ready"
        assert body["sync_status"]["coverage"]["query_count"] == 4
        assert body["sync_status"]["freshness_state"] == "fresh"
        assert body["sync_status"]["operational_contract"]["owner_display"] == "Owner / Ops (Toni)"
        assert body["pipeline_status"]["status"] == "success"
        assert body["pipeline_status"]["stats"]["queries_synced"] == 4
