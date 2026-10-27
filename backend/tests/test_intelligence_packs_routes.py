import os
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("AI_RUNTIME_PROFILE", "groq-cloudflare")
os.environ.setdefault("GROQ_API_KEY", "groq-test")
os.environ.setdefault("CLOUDFLARE_ACCOUNT_ID", "cf-account-test")
os.environ.setdefault("CLOUDFLARE_API_TOKEN", "cf-token-test")
os.environ.setdefault("INTERNAL_AUDIT_SECRET", "test-secret")

from backend.api.routes.intelligence import router
from backend.api.deps import get_org_id


app = FastAPI()
app.include_router(router, prefix="/api/intelligence")
app.dependency_overrides[get_org_id] = lambda: "org-1"
client = TestClient(app)


@patch("backend.api.routes.intelligence.list_intelligence_packs", new_callable=AsyncMock)
@patch("backend.api.routes.intelligence.get_active_intelligence_pack", new_callable=AsyncMock)
def test_get_intelligence_packs_contract(mock_active, mock_list) -> None:
    mock_list.return_value = [
        {
            "id": "pack-1",
            "pack_label": "Mallorca SW",
            "notebook_id": "nb-1",
            "notebook_name": "SW Notebook",
            "is_default": True,
            "status": "active",
        }
    ]
    mock_active.return_value = mock_list.return_value[0]

    response = client.get("/api/intelligence/packs")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["active_pack"]["id"] == "pack-1"


@patch("backend.api.routes.intelligence.create_intelligence_pack", new_callable=AsyncMock)
def test_create_intelligence_pack_endpoint(mock_create) -> None:
    mock_create.return_value = {
        "id": "pack-2",
        "pack_label": "Tramontana 2026",
        "notebook_id": "nb-2",
        "notebook_name": "Tramontana Notebook",
        "is_default": True,
        "status": "active",
    }

    response = client.post(
        "/api/intelligence/packs",
        json={
            "pack_label": "Tramontana 2026",
            "notebook_id": "nb-2",
            "notebook_name": "Tramontana Notebook",
            "zone_scope": ["soller"],
            "is_default": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["item"]["id"] == "pack-2"
