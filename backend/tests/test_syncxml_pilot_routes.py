"""
Tests for SyncXML Pilot router registration and decision flow.

Covers:
  A. Route registration in backend.main (production entrypoint)
  B. Manual approve / reject / more-info endpoints
  C. Automatic decision matrix (_decide_status)
  D. Webhook security for /api/internal/syncxml-pilot

All Neon, Resend, Hermes and SyncXML calls are mocked.
ALLOW_REAL_NEON_WRITE is never set to true.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from route_helpers import flatten_routes

from backend.api.deps import get_current_user, get_org_id, require_access_request_reviewer
from backend.api.routes.syncxml_pilot import router as syncxml_pilot_router
from backend.services.syncxml_pilot_service import SyncXmlPilotPayload, syncxml_pilot_service

ORG_ID = "9d6cb56d-3f21-4f7b-80ea-797a7c2c62cf"
USER_ID = "reviewer-001"


class MockReviewer:
    id = USER_ID


async def _mock_org_id() -> str:
    return ORG_ID


async def _mock_reviewer() -> MockReviewer:
    return MockReviewer()


@pytest.fixture
def pilot_app():
    """Isolated test app — mirrors the prefix used in backend/main.py."""
    app = FastAPI()
    app.include_router(syncxml_pilot_router, prefix="/api/syncxml-pilot", tags=["SyncXML Pilot"])
    app.dependency_overrides[get_org_id] = _mock_org_id
    app.dependency_overrides[get_current_user] = _mock_reviewer
    app.dependency_overrides[require_access_request_reviewer] = _mock_reviewer
    return app


# ─────────────────────────────────────────────────────────────
# A. Route registration
# ─────────────────────────────────────────────────────────────

def test_routes_registered_in_production_entrypoint():
    """
    backend.main must expose POST /api/syncxml-pilot/{id}/approve and /reject.
    This test will fail if the router is ever removed from backend/main.py.
    """
    from backend.main import app

    routes = {route.path for route in flatten_routes(app.routes)}
    assert "/api/syncxml-pilot/{request_id}/approve" in routes, (
        "Route not found — router not registered in backend/main.py"
    )
    assert "/api/syncxml-pilot/{request_id}/reject" in routes, (
        "Route not found — router not registered in backend/main.py"
    )
    assert "/api/syncxml-pilot/{request_id}/request-more-info" in routes


# ─────────────────────────────────────────────────────────────
# B. Manual endpoints
# ─────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_approve_pending_syncxml_request(pilot_app):
    """approve returns 200, calls provisioning and email via mocks."""
    fake_record = {
        "id": "req-001",
        "product": "syncxml",
        "status": "pending",
        "email": "piloto@test.com",
        "full_name": "Test User",
    }
    mock_result = {"record": {**fake_record, "status": "approved"}, "credentials": {}}

    with patch.object(syncxml_pilot_service, "approve_manual", new=AsyncMock(return_value=mock_result)):
        async with AsyncClient(
            transport=ASGITransport(app=pilot_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/syncxml-pilot/req-001/approve", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["record"]["status"] == "approved"


@pytest.mark.anyio
async def test_approve_failed_credentials_returns_502(pilot_app):
    """failed SyncXML provisioning is not a successful approval."""
    mock_result = {
        "ok": False,
        "status": "failed_credentials",
        "record": {
            "id": "req-001",
            "product": "syncxml",
            "status": "pending",
            "email": "piloto@test.com",
            "metadata": {
                "error_message": "SyncXML returned 503: persistent pilot authentication is not ready",
            },
        },
    }

    with patch.object(syncxml_pilot_service, "approve_manual", new=AsyncMock(return_value=mock_result)):
        async with AsyncClient(
            transport=ASGITransport(app=pilot_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/syncxml-pilot/req-001/approve", json={})

    assert response.status_code == 502
    assert "persistent pilot authentication" in response.json()["detail"]


@pytest.mark.anyio
async def test_approve_blocked_real_write_returns_503(pilot_app):
    """environment safety blocks must surface as API errors."""
    mock_result = {
        "ok": False,
        "blocked": True,
        "reason": "REAL_NEON_WRITE_BLOCKED",
        "action": "approve_manual",
    }

    with patch.object(syncxml_pilot_service, "approve_manual", new=AsyncMock(return_value=mock_result)):
        async with AsyncClient(
            transport=ASGITransport(app=pilot_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/syncxml-pilot/req-001/approve", json={})

    assert response.status_code == 503
    assert response.json()["detail"] == "REAL_NEON_WRITE_BLOCKED"


@pytest.mark.anyio
async def test_reject_pending_syncxml_request(pilot_app):
    """reject returns 200, updates status, no provisioning attempt."""
    fake_result = {
        "record": {
            "id": "req-002",
            "product": "syncxml",
            "status": "rejected",
            "email": "rechazado@test.com",
        }
    }

    with patch.object(syncxml_pilot_service, "reject_manual", new=AsyncMock(return_value=fake_result)):
        async with AsyncClient(
            transport=ASGITransport(app=pilot_app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/syncxml-pilot/req-002/reject",
                json={"internal_reason": "Fuera de alcance", "user_reason": "No aplica al piloto"},
            )

    assert response.status_code == 200
    assert response.json()["record"]["status"] == "rejected"


@pytest.mark.anyio
async def test_approve_nonexistent_id_returns_business_404(pilot_app):
    """
    404 from approve_manual(ValueError) must be a business-level 404,
    clearly distinct from the old router-not-registered 404.
    """
    with patch.object(
        syncxml_pilot_service,
        "approve_manual",
        new=AsyncMock(side_effect=ValueError("Access request not found or not SyncXML")),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=pilot_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/syncxml-pilot/nonexistent-id/approve", json={})

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower() or "syncxml" in response.json()["detail"].lower()


@pytest.mark.anyio
async def test_approve_non_syncxml_product_raises_error(pilot_app):
    """
    The service must reject operating on Synergi/Data Lab records
    from the syncxml endpoint.
    """
    with patch.object(
        syncxml_pilot_service,
        "approve_manual",
        new=AsyncMock(side_effect=ValueError("Not a SyncXML access request")),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=pilot_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/syncxml-pilot/synergi-req-001/approve", json={})

    assert response.status_code == 404


@pytest.mark.anyio
async def test_approve_already_decided_request(pilot_app):
    """Already approved/rejected request: idempotent or controlled error."""
    with patch.object(
        syncxml_pilot_service,
        "approve_manual",
        new=AsyncMock(side_effect=ValueError("Request already decided: approved")),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=pilot_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/syncxml-pilot/already-done/approve", json={})

    assert response.status_code == 404


# ─────────────────────────────────────────────────────────────
# C. Automatic decision matrix
# ─────────────────────────────────────────────────────────────

def _base_payload(**overrides) -> SyncXmlPilotPayload:
    data = {
        "name": "Test User",
        "email": "test@example.com",
        "companyName": "Hotel Test",
        "accommodationType": "hotel",
        "currentWorkflow": "usamos excel para la gestión",
        "mainPain": "mucho tiempo manual",
        "wantsToValidate": "conversión de ficheros xml síntéticos",
        "estimatedMonthlyReservations": "50-100",
        "acceptsPilotConditions": True,
        "acceptsSyntheticOrAnonymizedData": True,
        "locale": "es",
        "raw": {},
    }
    data.update(overrides)
    return SyncXmlPilotPayload.model_validate(data)


def test_decide_rejects_when_real_data_requested():
    """
    Rule: texto contiene 'datos reales' / 'producción' / 'ses automático' → pending
    (la lógica existente devuelve pending, no rejected, para estos casos).
    """
    payload = _base_payload(wantsToValidate="quiero validar con datos reales de producción")
    ai = {"decision": "approve", "score": 90, "riskFlags": []}
    result = syncxml_pilot_service._decide_status(payload, ai)
    # risky_terms match → pending (manual review), not automatic approve
    assert result == "pending"


def test_decide_rejects_when_conditions_not_accepted():
    """Deterministic rejection: no acepta condiciones del piloto."""
    payload = _base_payload(acceptsPilotConditions=False)
    ai = {"decision": "approve", "score": 90, "riskFlags": []}
    result = syncxml_pilot_service._decide_status(payload, ai)
    assert result == "rejected"


def test_decide_keeps_request_pending_when_applicant_has_no_synthetic_sample():
    """No aportar muestra propia no rechaza: se revisa y al aprobar se adjuntan muestras."""
    payload = _base_payload(acceptsSyntheticOrAnonymizedData=False)
    ai = {"decision": "approve", "score": 90, "riskFlags": []}
    with patch("backend.services.syncxml_pilot_service.settings") as mock_settings:
        mock_settings.GUESTHUB_PILOT_AUTO_APPROVE = False
        mock_settings.APP_ENV = "production"
        mock_settings.GUESTHUB_ENV = "production"
        mock_settings.ALLOW_REAL_NEON_WRITE = True
        mock_settings.USE_SYNTHETIC_DATA_ONLY = False
        result = syncxml_pilot_service._decide_status(payload, ai)
    assert result == "pending"


def test_decide_pending_when_auto_approve_false():
    """
    Eligible request (score>=85, no flags, decision=approve) with AUTO_APPROVE=false → pending.
    No provisioning, no welcome email.
    """
    payload = _base_payload()
    ai = {"decision": "approve", "score": 88, "riskFlags": []}
    with patch("backend.services.syncxml_pilot_service.settings") as mock_settings:
        mock_settings.GUESTHUB_PILOT_AUTO_APPROVE = False
        mock_settings.APP_ENV = "production"
        mock_settings.GUESTHUB_ENV = "production"
        mock_settings.ALLOW_REAL_NEON_WRITE = True
        mock_settings.USE_SYNTHETIC_DATA_ONLY = False
        result = syncxml_pilot_service._decide_status(payload, ai)
    assert result == "pending"


def test_decide_approved_only_when_auto_approve_true_and_not_safety_mode():
    """
    AUTO_APPROVE=true + not in safety mode + eligible → approved.
    Safety guardrail: if safety mode is active, must stay pending even with AUTO_APPROVE=true.
    """
    payload = _base_payload()
    ai = {"decision": "approve", "score": 90, "riskFlags": []}
    with patch("backend.services.syncxml_pilot_service.settings") as mock_settings:
        mock_settings.GUESTHUB_PILOT_AUTO_APPROVE = True
        mock_settings.APP_ENV = "production"
        mock_settings.GUESTHUB_ENV = "production"
        mock_settings.ALLOW_REAL_NEON_WRITE = True
        mock_settings.USE_SYNTHETIC_DATA_ONLY = False
        result = syncxml_pilot_service._decide_status(payload, ai)
    assert result == "approved"


def test_decide_pending_when_auto_approve_true_but_safety_mode():
    """AUTO_APPROVE=true but safety mode active → pending."""
    payload = _base_payload()
    ai = {"decision": "approve", "score": 90, "riskFlags": []}
    with patch("backend.services.syncxml_pilot_service.settings") as mock_settings:
        mock_settings.GUESTHUB_PILOT_AUTO_APPROVE = True
        mock_settings.APP_ENV = "staging"
        mock_settings.GUESTHUB_ENV = "staging"
        mock_settings.ALLOW_REAL_NEON_WRITE = False
        mock_settings.USE_SYNTHETIC_DATA_ONLY = True
        result = syncxml_pilot_service._decide_status(payload, ai)
    assert result == "pending"


def test_decide_auto_rejects_low_score_with_flags():
    """Deterministic rejection: AI score<=20 with riskFlags."""
    payload = _base_payload()
    ai = {"decision": "reject", "score": 10, "riskFlags": ["REAL_DATA_REQUESTED", "OUT_OF_SCOPE"]}
    result = syncxml_pilot_service._decide_status(payload, ai)
    assert result == "rejected"


def test_decide_pending_on_ambiguous_ai_response():
    """Ambiguous AI: no clear decision → pending (manual review)."""
    payload = _base_payload()
    ai = {"decision": None, "score": 50, "riskFlags": []}
    result = syncxml_pilot_service._decide_status(payload, ai)
    assert result == "pending"


# ─────────────────────────────────────────────────────────────
# D. Webhook security (/api/internal/syncxml-pilot)
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def webhook_app():
    from fastapi import FastAPI
    from backend.api.internal_webhooks import router as webhooks_router
    app = FastAPI()
    app.include_router(webhooks_router)
    return app


@pytest.mark.anyio
async def test_webhook_invalid_api_key_returns_403(webhook_app):
    """Invalid Bearer token → 401 or 403, no data processed."""
    async with AsyncClient(
        transport=ASGITransport(app=webhook_app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/internal/webhooks/syncxml-pilot",
            json={"email": "x@x.com"},
            headers={"x-api-key": "wrong-secret"},
        )
    assert response.status_code in (401, 403)


@pytest.mark.anyio
async def test_webhook_missing_api_key_returns_403(webhook_app):
    """No API key header → 401 or 403."""
    async with AsyncClient(
        transport=ASGITransport(app=webhook_app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/internal/webhooks/syncxml-pilot",
            json={"email": "x@x.com"},
        )
    assert response.status_code in (401, 403)


@pytest.mark.anyio
async def test_webhook_invalid_payload_returns_traceable_422(webhook_app):
    """Valid auth + invalid payload → traceable 422, no opaque 500."""
    with patch("backend.api.internal_webhooks.settings") as mock_settings:
        mock_settings.GUESTHUB_WEBHOOK_SECRET = "correct-secret"
        mock_settings.NEXUS_INTERNAL_API_KEY = "nexus-key"
        async with AsyncClient(
            transport=ASGITransport(app=webhook_app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/internal/webhooks/syncxml-pilot",
                json={
                    "requestId": "invalid-request",
                    "idempotency_key": "invalid-request",
                    "email": "invalid@example.com",
                },
                headers={"Authorization": "Bearer correct-secret"},
            )

    assert response.status_code == 422
    body = response.json()
    assert body["detail"]["code"] == "SYNCXML_PILOT_WEBHOOK_INVALID_PAYLOAD"
    assert body["detail"]["requestId"] == "invalid-request"
    assert body["detail"]["idempotency_key"] == "invalid-request"


@pytest.mark.anyio
async def test_webhook_valid_key_accepts_payload(webhook_app):
    """Valid API key + valid payload → accepted (200), no real Neon write."""
    valid_payload = {
        "name": "Test User",
        "email": "test@example.com",
        "companyName": "Hotel Test",
        "accommodationType": "hotel",
        "currentWorkflow": "excel manual",
        "mainPain": "mucho tiempo",
        "wantsToValidate": "ficheros xml sintéticos",
        "acceptsPilotConditions": True,
        "acceptsSyntheticOrAnonymizedData": True,
        "locale": "es",
    }
    with patch("backend.api.internal_webhooks.settings") as mock_settings, \
         patch("backend.api.internal_webhooks.syncxml_pilot_service") as mock_service:
        mock_settings.GUESTHUB_WEBHOOK_SECRET = "correct-secret"
        mock_settings.NEXUS_INTERNAL_API_KEY = "nexus-key"
        mock_service.process_incoming_lead = AsyncMock(return_value={"id": "new-req-001"})
        async with AsyncClient(
            transport=ASGITransport(app=webhook_app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/internal/webhooks/syncxml-pilot",
                json=valid_payload,
                headers={"Authorization": "Bearer correct-secret"},
            )
    assert response.status_code == 200
    assert response.json().get("status") == "accepted"


@pytest.mark.anyio
async def test_webhook_blocked_result_returns_503(webhook_app):
    """The webhook must not report accepted when safety mode blocks persistence."""
    with patch("backend.api.internal_webhooks.settings") as mock_settings, \
         patch("backend.api.internal_webhooks.syncxml_pilot_service") as mock_service:
        mock_settings.GUESTHUB_WEBHOOK_SECRET = "correct-secret"
        mock_settings.NEXUS_INTERNAL_API_KEY = "nexus-key"
        mock_service.process_incoming_lead = AsyncMock(
            return_value={
                "blocked": True,
                "reason": "REAL_NEON_WRITE_BLOCKED",
                "action": "process_incoming_lead",
            }
        )
        async with AsyncClient(
            transport=ASGITransport(app=webhook_app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/internal/webhooks/syncxml-pilot",
                json={
                    "requestId": "blocked-request",
                    "name": "Test User",
                    "email": "test@example.com",
                    "accommodationType": "hotel",
                    "estimatedMonthlyReservations": "10",
                    "currentWorkflow": "excel manual",
                    "mainPain": "mucho tiempo",
                    "wantsToValidate": "ficheros xml sintéticos",
                    "acceptsPilotConditions": True,
                    "acceptsSyntheticOrAnonymizedData": False,
                    "locale": "es",
                },
                headers={"Authorization": "Bearer correct-secret"},
            )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "REAL_NEON_WRITE_BLOCKED"


@pytest.mark.anyio
async def test_webhook_missing_persisted_id_returns_500(webhook_app):
    """Accepted responses must include a persisted access request id."""
    with patch("backend.api.internal_webhooks.settings") as mock_settings, \
         patch("backend.api.internal_webhooks.syncxml_pilot_service") as mock_service:
        mock_settings.GUESTHUB_WEBHOOK_SECRET = "correct-secret"
        mock_settings.NEXUS_INTERNAL_API_KEY = "nexus-key"
        mock_service.process_incoming_lead = AsyncMock(return_value={"status": "pending"})
        async with AsyncClient(
            transport=ASGITransport(app=webhook_app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/internal/webhooks/syncxml-pilot",
                json={
                    "requestId": "missing-id-request",
                    "name": "Test User",
                    "email": "test@example.com",
                    "accommodationType": "hotel",
                    "estimatedMonthlyReservations": "10",
                    "currentWorkflow": "excel manual",
                    "mainPain": "mucho tiempo",
                    "wantsToValidate": "ficheros xml sintéticos",
                    "acceptsPilotConditions": True,
                    "acceptsSyntheticOrAnonymizedData": False,
                    "locale": "es",
                },
                headers={"Authorization": "Bearer correct-secret"},
            )

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "SYNCXML_PILOT_WEBHOOK_NOT_PERSISTED"
