"""
API route tests — FastAPI TestClient. Feature: ANCLORA-PBM-001
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient

from route_helpers import flatten_routes
from backend.api.routes.prospection import router

app = FastAPI()
app.include_router(router, prefix="/api/prospection")
ORG_ID = str(uuid4())
USER_ID = str(uuid4())

async def mock_get_org_id() -> str:
    return ORG_ID

class MockUser:
    id = USER_ID

async def mock_get_current_user() -> MockUser:
    return MockUser()

async def mock_check_budget_hard_stop():
    class BudgetStatus:
        status = "ok"
    return BudgetStatus()

from backend.api.deps import get_org_id, get_current_user, check_budget_hard_stop
app.dependency_overrides[get_org_id] = mock_get_org_id
app.dependency_overrides[get_current_user] = mock_get_current_user
app.dependency_overrides[check_budget_hard_stop] = mock_check_budget_hard_stop
client = TestClient(app)


class TestRouteRegistration:
    @pytest.mark.parametrize("method,path", [
        ("POST", "/api/prospection/properties"),
        ("GET", "/api/prospection/properties"),
        ("GET", "/api/prospection/workspace"),
        ("POST", "/api/prospection/workspace/actions/followup-task"),
        ("POST", "/api/prospection/workspace/actions/mark-reviewed"),
        ("PATCH", "/api/prospection/properties/{property_id}"),
        ("POST", "/api/prospection/properties/{property_id}/score"),
        ("POST", "/api/prospection/buyers"),
        ("GET", "/api/prospection/buyers"),
        ("PATCH", "/api/prospection/buyers/{buyer_id}"),
        ("GET", "/api/prospection/buyers/{buyer_id}/memory"),
        ("POST", "/api/prospection/buyers/{buyer_id}/memory/rebuild"),
        ("POST", "/api/prospection/matches/recompute"),
        ("GET", "/api/prospection/matches"),
        ("PATCH", "/api/prospection/matches/{match_id}"),
        ("POST", "/api/prospection/matches/{match_id}/activity"),
        ("GET", "/api/prospection/matches/{match_id}/activities"),
    ])
    def test_endpoint_exists(self, method: str, path: str) -> None:
        routes = flatten_routes(app.routes)
        matching = [r for r in routes if hasattr(r, "path") and r.path == path and method in r.methods]
        assert len(matching) == 1, f"{method} {path} not found"


class TestPropertyEndpoints:
    @patch("backend.api.routes.prospection.prospection_service")
    def test_create_property_valid(self, mock_svc: MagicMock) -> None:
        mock_svc.create_property = AsyncMock(return_value={"id": str(uuid4()), "org_id": ORG_ID, "source": "idealista", "status": "new"})
        resp = client.post("/api/prospection/properties", json={"source": "idealista", "title": "Test"})
        assert resp.status_code == 201

    def test_create_property_invalid_source(self) -> None:
        resp = client.post("/api/prospection/properties", json={"source": "scraper"})
        assert resp.status_code == 422

    @patch("backend.api.routes.prospection.prospection_service")
    def test_list_properties(self, mock_svc: MagicMock) -> None:
        mock_svc.list_properties = AsyncMock(return_value={"items": [], "total": 0, "limit": 50, "offset": 0})
        resp = client.get("/api/prospection/properties")
        assert resp.status_code == 200
        assert "items" in resp.json()

    @patch("backend.api.routes.prospection.prospection_service")
    def test_update_property_not_found(self, mock_svc: MagicMock) -> None:
        mock_svc.update_property = AsyncMock(return_value=None)
        resp = client.patch(f"/api/prospection/properties/{uuid4()}", json={"title": "X"})
        assert resp.status_code == 404

    @patch("backend.api.routes.prospection.verify_org_membership", new_callable=AsyncMock)
    @patch("backend.api.routes.prospection.prospection_service")
    def test_workspace_owner_scope(self, mock_svc: MagicMock, mock_verify: MagicMock) -> None:
        mock_verify.return_value = {"role": "owner"}
        mock_svc.get_workspace = AsyncMock(return_value={
            "scope": {"org_id": ORG_ID, "role": "owner", "user_id": None},
            "properties": {"items": [], "total": 0, "limit": 25, "offset": 0},
            "buyers": {"items": [], "total": 0, "limit": 25, "offset": 0},
            "matches": {"items": [], "total": 0, "limit": 25, "offset": 0},
            "totals": {"properties": 0, "buyers": 0, "matches": 0},
        })
        resp = client.get("/api/prospection/workspace")
        assert resp.status_code == 200
        assert resp.json()["scope"]["role"] == "owner"

    @patch("backend.api.routes.prospection.prospection_service")
    def test_workspace_followup_task_action(self, mock_svc: MagicMock) -> None:
        task_id = str(uuid4())
        mock_svc.create_workspace_followup_task = AsyncMock(return_value={"task_id": task_id})
        resp = client.post(
            "/api/prospection/workspace/actions/followup-task",
            json={"entity_type": "property", "entity_id": str(uuid4())},
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "followup_task"
        assert resp.json()["task_id"] == task_id

    @patch("backend.api.routes.prospection.prospection_service")
    def test_workspace_mark_reviewed_action(self, mock_svc: MagicMock) -> None:
        entity_id = str(uuid4())
        mock_svc.mark_workspace_item_reviewed = AsyncMock(
            return_value={"entity_type": "property", "entity_id": entity_id}
        )
        resp = client.post(
            "/api/prospection/workspace/actions/mark-reviewed",
            json={"entity_type": "property", "entity_id": entity_id},
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "mark_reviewed"


class TestBuyerEndpoints:
    @patch("backend.api.routes.prospection.prospection_service")
    def test_create_buyer_valid(self, mock_svc: MagicMock) -> None:
        mock_svc.create_buyer = AsyncMock(return_value={"id": str(uuid4()), "org_id": ORG_ID, "status": "active"})
        resp = client.post("/api/prospection/buyers", json={"full_name": "Buyer", "budget_min": 1000000, "budget_max": 3000000})
        assert resp.status_code == 201

    @patch("backend.api.routes.prospection.prospection_service")
    def test_list_buyers_with_source_filters(self, mock_svc: MagicMock) -> None:
        mock_svc.list_buyers = AsyncMock(return_value={"items": [], "total": 0, "limit": 50, "offset": 0})
        resp = client.get("/api/prospection/buyers?source_type=partner_referral&source_platform=exp_agent")
        assert resp.status_code == 200
        mock_svc.list_buyers.assert_awaited_once()
        _, kwargs = mock_svc.list_buyers.await_args
        assert kwargs["source_type"] == "partner_referral"
        assert kwargs["source_platform"] == "exp_agent"

    def test_create_buyer_invalid_budget(self) -> None:
        resp = client.post("/api/prospection/buyers", json={"budget_min": 5000000, "budget_max": 1000000})
        assert resp.status_code == 422


class TestMatchEndpoints:
    @patch("backend.api.routes.prospection.prospection_service")
    def test_recompute(self, mock_svc: MagicMock) -> None:
        from backend.models.prospection import RecomputeResponse
        mock_svc.recompute_matches = AsyncMock(return_value=RecomputeResponse(matches_created=5, matches_updated=3, total_computed=8))
        resp = client.post("/api/prospection/matches/recompute", json={})
        assert resp.status_code == 200
        assert resp.json()["total_computed"] == 8

    @patch("backend.api.routes.prospection.prospection_service")
    def test_update_match_not_found(self, mock_svc: MagicMock) -> None:
        mock_svc.update_match = AsyncMock(return_value=None)
        resp = client.patch(f"/api/prospection/matches/{uuid4()}", json={"match_status": "contacted"})
        assert resp.status_code == 404


class TestActivityEndpoints:
    @patch("backend.api.routes.prospection.prospection_service")
    def test_log_activity(self, mock_svc: MagicMock) -> None:
        mock_svc.log_activity = AsyncMock(return_value={"id": str(uuid4()), "activity_type": "call"})
        resp = client.post(f"/api/prospection/matches/{uuid4()}/activity", json={"activity_type": "call"})
        assert resp.status_code == 201

    @patch("backend.api.routes.prospection.prospection_service")
    def test_list_activities(self, mock_svc: MagicMock) -> None:
        mock_svc.list_activities = AsyncMock(return_value={"items": [], "total": 0})
        resp = client.get(f"/api/prospection/matches/{uuid4()}/activities")
        assert resp.status_code == 200
