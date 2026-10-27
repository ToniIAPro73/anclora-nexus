import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from route_helpers import flatten_routes


from backend.api.routes.prospection import router
from backend.api.deps import check_budget_hard_stop, get_org_id, get_current_user


ORG_ID = "org-test-1"


async def mock_check_budget_hard_stop():
    class BudgetStatus:
        status = "ok"
    return BudgetStatus()


async def mock_user():
    class User:
        id = "user-test"
    return User()


app = FastAPI()
app.include_router(router, prefix="/api/prospection")
app.dependency_overrides[check_budget_hard_stop] = mock_check_budget_hard_stop
app.dependency_overrides[get_org_id] = lambda: ORG_ID
app.dependency_overrides[get_current_user] = mock_user
client = TestClient(app)


def test_buyer_workbench_route_exists() -> None:
    matching = [r for r in flatten_routes(app.routes) if r.path == "/api/prospection/buyers/{buyer_id}/workbench"]
    assert matching


@patch("backend.api.routes.prospection.buyer_outreach_service")
def test_buyer_workbench_returns_payload(mock_service: MagicMock) -> None:
    buyer_id = str(uuid4())
    mock_service.get_buyer_workbench = AsyncMock(return_value={
        "buyer": {"id": buyer_id, "full_name": "Hans Mueller", "source_type": "partner_referral", "source_platform": "exp_agent"},
        "matches": [],
        "activities": [],
        "interactions": [],
        "latest_artifacts": {"buyer_brief": None, "email_draft": None, "whatsapp_draft": None},
        "memory": {"status": "ready", "total_records": 2, "matches": [], "query": "buyer", "retrieval_summary": "ok", "version": "ANCLORA-BMCR-001.v1", "buyer_id": buyer_id},
        "console": {"readiness": "needs_brief", "recommended_channel": "review", "next_action": "Generate buyer outreach brief and drafts", "reasons": [], "memory_highlights": []},
        "snapshot": {"interactions_count": 0, "matches_count": 0, "semantic_memory_count": 2, "semantic_memory_ready": True, "recommended_channel": "review", "readiness": "needs_brief", "email_native_available": False},
    })

    response = client.get(f"/api/prospection/buyers/{buyer_id}/workbench")

    assert response.status_code == 200
    assert response.json()["buyer"]["id"] == buyer_id


@patch("backend.api.routes.prospection.buyer_outreach_service")
def test_generate_buyer_outreach_route(mock_service: MagicMock) -> None:
    buyer_id = str(uuid4())
    mock_service.generate_buyer_outreach = AsyncMock(return_value={
        "buyer_id": buyer_id,
        "brief": "Brief",
        "email_subject": "Subject",
        "email_body": "Body",
        "whatsapp_body": "WhatsApp",
    })

    response = client.post(f"/api/prospection/buyers/{buyer_id}/generate-outreach")

    assert response.status_code == 200
    assert response.json()["email_subject"] == "Subject"


@patch("backend.api.routes.prospection.buyer_outreach_service")
def test_send_buyer_supervised_route(mock_service: MagicMock) -> None:
    buyer_id = str(uuid4())
    interaction_id = str(uuid4())
    mock_service.build_supervised_send_payload = AsyncMock(return_value={
        "channel": "email",
        "buyer_id": buyer_id,
        "interaction_id": interaction_id,
        "target": "buyer@example.com",
        "subject": "Subject",
        "body": "Body",
        "launch_url": "mailto:buyer@example.com?subject=Subject",
        "status": "ready_for_human_send",
        "transport": "mailto",
    })

    response = client.post(f"/api/prospection/buyers/{buyer_id}/send-supervised/email")

    assert response.status_code == 200
    assert response.json()["interaction_id"] == interaction_id
