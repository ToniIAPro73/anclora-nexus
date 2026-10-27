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


class TestAIRuntimeRouteRegistration:
    def test_runtime_profile_endpoint_exists(self) -> None:
        routes = flatten_routes(app.routes)
        matching = [r for r in routes if hasattr(r, "path") and r.path == "/api/intelligence/runtime-profile" and "GET" in r.methods]
        assert len(matching) == 1


class TestAIRuntimeRouteContract:
    @patch("backend.api.routes.intelligence.get_runtime_summary")
    def test_runtime_profile_returns_summary(self, mock_summary) -> None:
        mock_summary.return_value = {
            "feature_id": "ANCLORA-AIRP-001.v1",
            "profile": "groq-cloudflare",
            "status": "ready",
            "routes": {
                "analyze": {
                    "provider": "groq",
                    "model": "openai/gpt-oss-20b",
                    "fallback_model": "llama-3.3-70b-versatile",
                    "is_ready": True,
                    "missing_env": [],
                }
            },
            "missing_env": [],
            "audit_secret_configured": True,
            "deprecated_env_present": {
                "OPENAI_API_KEY": False,
                "ANTHROPIC_API_KEY": False,
            },
        }

        response = client.get("/api/intelligence/runtime-profile")

        assert response.status_code == 200
        body = response.json()
        assert body["runtime"]["profile"] == "groq-cloudflare"
        assert body["runtime"]["routes"]["analyze"]["provider"] == "groq"
