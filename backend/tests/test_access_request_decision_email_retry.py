import pytest

from backend.services.access_request_service import (
    AccessRequestInvalidTransitionError,
    AccessRequestService,
)
from backend.tests.test_access_request_review_service import (
    ORG_ID,
    REVIEWER_ID,
    MockAuditService,
    MockEmailService,
    MockNeonClient,
    access_request_record,
)


@pytest.fixture
def service():
    return AccessRequestService()


@pytest.mark.anyio
async def test_retry_decision_email_after_failed_status(monkeypatch, service):
    rows = [
        {
            **access_request_record("request-1", status="approved"),
            "reviewed_by": REVIEWER_ID,
            "reviewed_at": "2026-05-06T10:00:00+00:00",
        }
    ]
    audit_rows = [
        {
            "id": "audit-1",
            "org_id": ORG_ID,
            "timestamp": "2026-05-06T10:01:00+00:00",
            "actor_type": "system",
            "actor_id": "system",
            "action": "access_request.email_send_failed",
            "resource_type": "access_request",
            "resource_id": "request-1",
            "details": {"status": "approved"},
        }
    ]
    email_service = MockEmailService()
    audit_service = MockAuditService()
    monkeypatch.setattr(
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows, audit_rows=audit_rows),
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.access_request_email_service",
        email_service,
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.access_request_audit_service",
        audit_service,
    )

    result = await service.retry_decision_email(
        ORG_ID,
        "request-1",
        reviewer_id=REVIEWER_ID,
    )

    assert result["status"] == "approved"
    assert result["reviewed_by"] == REVIEWER_ID
    assert result["reviewed_at"] == "2026-05-06T10:00:00+00:00"
    assert result["decision_email"]["status"] == "sent"
    assert result["lifecycle"]["email_status"] == "sent"
    assert [event["event_type"] for event in audit_service.events] == [
        "access_request.decision_email_retry_requested",
        "access_request.email_sent",
        "access_request.decision_email_retry_succeeded",
    ]


@pytest.mark.anyio
async def test_retry_decision_email_pending_request_fails(monkeypatch, service):
    rows = [access_request_record("request-1")]
    monkeypatch.setattr(
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows),
    )

    with pytest.raises(AccessRequestInvalidTransitionError):
        await service.retry_decision_email(ORG_ID, "request-1", reviewer_id=REVIEWER_ID)


@pytest.mark.anyio
async def test_retry_decision_email_already_sent_fails(monkeypatch, service):
    rows = [
        {
            **access_request_record("request-1", status="rejected"),
            "reviewed_by": REVIEWER_ID,
            "reviewed_at": "2026-05-06T10:00:00+00:00",
            "rejection_reason": "Not eligible",
        }
    ]
    audit_rows = [
        {
            "id": "audit-1",
            "org_id": ORG_ID,
            "timestamp": "2026-05-06T10:01:00+00:00",
            "actor_type": "system",
            "actor_id": "system",
            "action": "access_request.email_sent",
            "resource_type": "access_request",
            "resource_id": "request-1",
            "details": {"status": "sent"},
        }
    ]
    monkeypatch.setattr(
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows, audit_rows=audit_rows),
    )

    with pytest.raises(AccessRequestInvalidTransitionError):
        await service.retry_decision_email(ORG_ID, "request-1", reviewer_id=REVIEWER_ID)


@pytest.mark.anyio
async def test_retry_failure_sanitizes_provider_error(monkeypatch, service):
    rows = [
        {
            **access_request_record("request-1", status="approved"),
            "reviewed_by": REVIEWER_ID,
            "reviewed_at": "2026-05-06T10:00:00+00:00",
        }
    ]
    audit_rows = [
        {
            "id": "audit-1",
            "org_id": ORG_ID,
            "timestamp": "2026-05-06T10:01:00+00:00",
            "actor_type": "system",
            "actor_id": "system",
            "action": "access_request.email_skipped",
            "resource_type": "access_request",
            "resource_id": "request-1",
            "details": {"status": "skipped"},
        }
    ]
    monkeypatch.setattr(
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows, audit_rows=audit_rows),
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.access_request_email_service",
        MockEmailService(fail=True),
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.access_request_audit_service",
        MockAuditService(),
    )

    result = await service.retry_decision_email(
        ORG_ID,
        "request-1",
        reviewer_id=REVIEWER_ID,
    )

    assert result["decision_email"]["status"] == "failed"
    assert result["decision_email"]["error"] == "decision_email_send_failed"
