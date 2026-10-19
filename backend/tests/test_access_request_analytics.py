from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.api.deps import get_current_user, get_org_id, require_access_request_reviewer
from backend.api.routes.access_requests import router
from backend.services.access_request_service import AccessRequestService
from backend.tests.test_access_request_review_service import (
    ORG_ID,
    REVIEWER_ID,
    MockSupabaseClient,
    access_request_record,
)


class MockUser:
    id = REVIEWER_ID


async def mock_get_org_id() -> str:
    return ORG_ID


async def mock_require_access_request_reviewer() -> MockUser:
    return MockUser()


@pytest.fixture
def app():
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/access-requests")
    test_app.dependency_overrides[get_org_id] = mock_get_org_id
    test_app.dependency_overrides[require_access_request_reviewer] = mock_require_access_request_reviewer
    return test_app


@pytest.fixture
def service():
    return AccessRequestService()


@pytest.mark.anyio
async def test_access_request_analytics_route(app):
    with patch("backend.api.routes.access_requests.access_request_service") as mock_service:
        mock_service.get_analytics_summary = AsyncMock(
            return_value={
                "total_requests": 1,
                "pending_count": 1,
                "approved_count": 0,
                "rejected_count": 0,
                "cancelled_count": 0,
                "requests_by_product": {"synergi": 1, "data_lab": 0},
                "requests_by_source": {"syncxml_landing": 1, "synergi_app": 0, "data_lab_app": 0},
                "pending_older_than_24h": 1,
                "pending_older_than_72h": 0,
                "average_review_time_hours": None,
                "decision_email_failed_count": 0,
                "decision_email_unknown_count": 0,
                "retry_available_count": 0,
                "provisioning_attention_count": 0,
                "generated_at": "2026-05-06T18:00:00+00:00",
                "sample_size": 1,
                "sample_limit": 500,
                "is_sampled": False,
                "attention_items": [
                    {
                        "request_id": "request-1",
                        "reason": "pending_older_than_24h",
                        "severity": "warning",
                        "status": "pending",
                        "product": "synergi",
                        "source": "syncxml_landing",
                        "email": "test@example.com",
                        "created_at": "2026-05-05T10:00:00+00:00",
                        "reviewed_at": None,
                        "age_hours": 32.0,
                    }
                ],
            }
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/access-requests/analytics/summary?limit=500")

    assert response.status_code == 200
    assert response.json()["attention_items"][0]["reason"] == "pending_older_than_24h"
    mock_service.get_analytics_summary.assert_awaited_once_with(org_id=ORG_ID, limit=500)


@pytest.mark.anyio
async def test_access_request_analytics_summary_counts_and_attention(monkeypatch, service):
    rows = [
        {
            **access_request_record("pending-72", status="pending", product="synergi"),
            "email": "pending72@example.com",
            "created_at": "2026-05-03T00:00:00+00:00",
        },
        {
            **access_request_record("approved-failed", status="approved", product="data_lab"),
            "email": "approved@example.com",
            "created_at": "2026-05-05T10:00:00+00:00",
            "reviewed_at": "2026-05-05T16:00:00+00:00",
            "invite_token": "invite-token",
            "invite_expires_at": "2026-05-20T10:00:00+00:00",
        },
        {
            **access_request_record("rejected-unknown", status="rejected", product="synergi"),
            "email": "rejected@example.com",
            "created_at": "2026-05-04T10:00:00+00:00",
            "reviewed_at": "2026-05-05T10:00:00+00:00",
        },
        {
            **access_request_record("approved-provisioning", status="approved", product="synergi"),
            "email": "provisioning@example.com",
            "created_at": "2026-05-05T11:00:00+00:00",
            "reviewed_at": "2026-05-05T13:00:00+00:00",
        },
    ]
    audit_rows = [
        {
            "id": "audit-1",
            "org_id": ORG_ID,
            "timestamp": "2026-05-05T16:01:00+00:00",
            "action": "access_request.email_send_failed",
            "resource_type": "access_request",
            "resource_id": "approved-failed",
            "details": {"status": "approved"},
        }
    ]
    monkeypatch.setattr(
        "backend.services.access_request_service.supabase_service.client",
        MockSupabaseClient(rows, audit_rows=audit_rows),
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.datetime",
        type(
            "FixedDateTime",
            (),
            {
                "now": staticmethod(lambda _tz=None: __import__("datetime").datetime(2026, 5, 6, 12, 0, tzinfo=__import__("datetime").timezone.utc)),
                "fromisoformat": staticmethod(__import__("datetime").datetime.fromisoformat),
            },
        ),
    )

    summary = await service.get_analytics_summary(ORG_ID, limit=500)

    assert summary.total_requests == 4
    assert summary.pending_count == 1
    assert summary.approved_count == 2
    assert summary.rejected_count == 1
    assert summary.requests_by_product == {"synergi": 3, "data_lab": 1, "guesthub": 0, "syncxml": 0}
    assert summary.pending_older_than_24h == 1
    assert summary.pending_older_than_72h == 1
    assert summary.average_review_time_hours == 10.67
    assert summary.decision_email_failed_count == 1
    assert summary.decision_email_unknown_count == 2
    assert summary.retry_available_count == 3
    assert summary.provisioning_attention_count == 1
    reasons = {item.reason for item in summary.attention_items}
    assert {
        "pending_older_than_72h",
        "decision_email_failed",
        "decision_email_unknown",
        "retry_available",
        "provisioning_attention",
    }.issubset(reasons)


@pytest.mark.anyio
async def test_access_request_analytics_uses_bounded_limit(monkeypatch, service):
    rows = [access_request_record("request-1")]
    monkeypatch.setattr(
        "backend.services.access_request_service.supabase_service.client",
        MockSupabaseClient(rows),
    )

    summary = await service.get_analytics_summary(ORG_ID, limit=5000)

    assert summary.sample_limit == 1000
    assert summary.sample_size == 1
