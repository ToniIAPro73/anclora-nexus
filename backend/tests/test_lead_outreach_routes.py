import os
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from route_helpers import flatten_routes


from backend.api.routes.leads import router
from backend.api.deps import get_org_id


ORG_ID = "org-test-1"

app = FastAPI()
app.include_router(router, prefix="/api")
app.dependency_overrides[get_org_id] = lambda: ORG_ID
client = TestClient(app)


def test_generate_lead_outreach_route_exists() -> None:
    matching = [r for r in flatten_routes(app.routes) if r.path == "/api/leads/{lead_id}/generate-outreach"]
    assert matching


@patch("backend.api.routes.leads.lead_outreach_service")
def test_generate_lead_outreach_route(mock_service: MagicMock) -> None:
    mock_service.generate_lead_outreach = AsyncMock(
        return_value={
            "lead_id": "lead-1",
            "brief": "Brief",
            "email_subject": "Subject",
            "email_body": "Body",
        }
    )

    response = client.post("/api/leads/lead-1/generate-outreach")

    assert response.status_code == 200
    assert response.json()["email_subject"] == "Subject"


@patch("backend.api.routes.leads.lead_outreach_service")
def test_send_lead_supervised_email_route(mock_service: MagicMock) -> None:
    mock_service.build_supervised_send_payload = AsyncMock(
        return_value={
            "channel": "email",
            "lead_id": "lead-1",
            "interaction_id": "int-1",
            "target": "lead@example.com",
            "subject": "Subject",
            "body": "Body",
            "launch_url": "mailto:lead@example.com?subject=Subject",
            "status": "ready_for_human_send",
            "transport": "mailto",
        }
    )

    response = client.post("/api/leads/lead-1/send-supervised/email")

    assert response.status_code == 200
    assert response.json()["interaction_id"] == "int-1"
