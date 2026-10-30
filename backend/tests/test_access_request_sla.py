import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from backend.models.access_requests import AccessRequestSlaReason, AccessRequestSlaSeverity
from backend.services.access_request_service import AccessRequestService
from backend.tests.test_access_request_review_service import MockNeonClient

ORG_ID = "test-org"


@pytest.fixture
def neon_client():
    # Requests are read through the table facade; audit events through the
    # `nexus_list_access_request_audit_events` RPC (same contract as the service).
    return MockNeonClient([])


@pytest.fixture
def mock_neon_service(neon_client):
    with patch("backend.services.access_request_service.neon_service") as mock:
        mock.client = neon_client
        yield mock


@pytest.fixture
def mock_audit_service():
    with patch("backend.services.access_request_service.access_request_audit_service") as mock:
        mock.log_event = AsyncMock()
        yield mock


def audit_event(request_id: str, action: str, timestamp: str, details: dict | None = None) -> dict:
    return {
        "org_id": ORG_ID,
        "resource_id": request_id,
        "resource_type": "access_request",
        "action": action,
        "timestamp": timestamp,
        "details": details or {},
    }


@pytest.mark.anyio
async def test_run_sla_scan_deduplication(mock_neon_service, mock_audit_service):
    service = AccessRequestService()
    now = datetime.now(timezone.utc)
    mock_neon_service.client.rows.append({
        "id": "req-1",
        "org_id": ORG_ID,
        "status": "pending",
        "created_at": (now - timedelta(hours=25)).isoformat(),
        "email": "test@example.com",
        "full_name": "Test User",
        "product": "synergi",
        "source": "syncxml_landing",
    })

    # 1. No previous SLA audit event: the alert is created.
    result = await service.run_sla_scan(org_id=ORG_ID, reviewer_id="test-reviewer", limit=10)

    assert result.scanned_count == 1
    assert result.alerts_created == 1
    assert result.alerts_suppressed == 0
    assert len(result.items) == 1
    assert result.items[0].reason == AccessRequestSlaReason.PENDING_OLDER_THAN_24H

    # 2. A recent SLA event for the same reason exists: the alert is suppressed.
    mock_neon_service.client.audit_rows.append(audit_event(
        "req-1",
        "access_request.sla_warning",
        now.isoformat(),
        {"reason": AccessRequestSlaReason.PENDING_OLDER_THAN_24H.value, "severity": AccessRequestSlaSeverity.WARNING.value},
    ))

    result = await service.run_sla_scan(org_id=ORG_ID, reviewer_id="test-reviewer", limit=10)

    assert result.alerts_created == 0
    assert result.alerts_suppressed == 1


@pytest.mark.anyio
async def test_run_sla_scan_critical_pending(mock_neon_service, mock_audit_service):
    service = AccessRequestService()
    now = datetime.now(timezone.utc)
    mock_neon_service.client.rows.append({
        "id": "req-critical",
        "org_id": ORG_ID,
        "status": "pending",
        "created_at": (now - timedelta(hours=73)).isoformat(),
        "email": "test@example.com",
        "full_name": "Critical User",
        "product": "synergi",
    })

    result = await service.run_sla_scan(org_id=ORG_ID, reviewer_id="test-reviewer")

    assert result.alerts_created == 1
    assert result.items[0].severity == AccessRequestSlaSeverity.CRITICAL
    assert result.items[0].reason == AccessRequestSlaReason.PENDING_OLDER_THAN_72H


@pytest.mark.anyio
async def test_run_sla_scan_failed_email(mock_neon_service, mock_audit_service):
    service = AccessRequestService()
    now = datetime.now(timezone.utc)
    mock_neon_service.client.rows.append({
        "id": "req-failed-email",
        "org_id": ORG_ID,
        "status": "approved",
        "email": "test@example.com",
        "created_at": now.isoformat(),
    })
    # Lifecycle of this request: the decision email failed and an invite was sent.
    mock_neon_service.client.audit_rows.extend([
        audit_event("req-failed-email", "access_request.email_send_failed", now.isoformat(), {"status": "failed"}),
        audit_event("req-failed-email", "access_request.provisioning_invite_sent", now.isoformat()),
    ])

    result = await service.run_sla_scan(org_id=ORG_ID, reviewer_id="test-reviewer")

    found_reasons = [item.reason for item in result.items]
    assert AccessRequestSlaReason.DECISION_EMAIL_FAILED in found_reasons


@pytest.mark.anyio
async def test_run_sla_scan_provisioning_attention(mock_neon_service, mock_audit_service):
    service = AccessRequestService()
    now = datetime.now(timezone.utc)
    mock_neon_service.client.rows.append({
        "id": "req-no-prov",
        "org_id": ORG_ID,
        "status": "approved",
        "email": "test@example.com",
        "product": "synergi",
        "full_name": "No Prov User",
        "created_at": now.isoformat(),
    })
    # Lifecycle: approved, email sent successfully, but NO provisioning.
    mock_neon_service.client.audit_rows.extend([
        audit_event("req-no-prov", "access_request.approved", now.isoformat()),
        audit_event("req-no-prov", "access_request.email_sent", now.isoformat(), {"status": "sent"}),
    ])

    result = await service.run_sla_scan(org_id=ORG_ID, reviewer_id="test-reviewer")

    found_reasons = [item.reason for item in result.items]
    assert AccessRequestSlaReason.PROVISIONING_ATTENTION in found_reasons
