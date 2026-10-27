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


class TestStatefoxDiscoveryRouteRegistration:
    def test_statefox_discovery_endpoint_exists(self) -> None:
        routes = flatten_routes(app.routes)
        matching = [
            r for r in routes
            if hasattr(r, "path") and r.path == "/api/intelligence/statefox-discovery" and "GET" in r.methods
        ]
        assert len(matching) == 1


class TestStatefoxDiscoveryRouteContract:
    @patch("backend.api.routes.intelligence.get_statefox_discovery")
    def test_statefox_discovery_returns_payload(self, mock_discovery) -> None:
        mock_discovery.return_value = {
            "feature_id": "ANCLORA-STFX-001.v1",
            "status": "discovery_ready",
            "provider": "Telegram Mini App via StateFox bot",
            "decision": {"go": True},
            "import_contract": {"primary_target": "properties", "secondary_target": "nexus_sellers"},
        }

        response = client.get("/api/intelligence/statefox-discovery")

        assert response.status_code == 200
        body = response.json()
        assert body["discovery"]["status"] == "discovery_ready"
        assert body["discovery"]["import_contract"]["primary_target"] == "properties"
