import pytest
from unittest.mock import AsyncMock

from backend.models.access_requests import AccessRequestReviewDecision
from backend.services.access_request_service import AccessRequestService
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
async def test_approve_prepares_invite_lifecycle(monkeypatch, service):
    rows = [access_request_record("request-1")]
    monkeypatch.setattr(
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows),
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.access_request_email_service",
        MockEmailService(),
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.access_request_audit_service",
        MockAuditService(),
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.identity_provisioning_service.provision_approved_request",
        AsyncMock(return_value={"provisioning_status": "invite_ready", "provisioning_case": "CASO_A", "identity_invitation_id": "inv-test"}),
    )

    result = await service.approve_request(
        ORG_ID,
        "request-1",
        AccessRequestReviewDecision(),
        reviewer_id=REVIEWER_ID,
    )

    assert result["invite_token"]
    assert result["invite_expires_at"]
    assert result["lifecycle"]["decision_status"] == "approved"
    assert result["lifecycle"]["provisioning_status"] == "invite_ready"
    assert result["lifecycle"]["email_status"] == "sent"
    assert result["lifecycle"]["retry_available"] is False


@pytest.mark.anyio
async def test_approve_preserves_existing_invite_intent(monkeypatch, service):
    rows = [
        {
            **access_request_record("request-1"),
            "invite_token": "existing-token",
            "invite_expires_at": "2026-05-20T10:00:00+00:00",
        }
    ]
    audit_service = MockAuditService()
    monkeypatch.setattr(
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows),
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.access_request_email_service",
        MockEmailService(),
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.access_request_audit_service",
        audit_service,
    )

    result = await service.approve_request(
        ORG_ID,
        "request-1",
        AccessRequestReviewDecision(),
        reviewer_id=REVIEWER_ID,
    )

    assert result["invite_token"] == "existing-token"
    assert result["invite_expires_at"] == "2026-05-20T10:00:00+00:00"
    provisioning_event = next(
        event
        for event in audit_service.events
        if event["event_type"] == "access_request.provisioning_intent_prepared"
    )
    assert provisioning_event["metadata"]["invite_created"] is False


@pytest.mark.anyio
async def test_get_lifecycle_derives_email_status_from_audit(monkeypatch, service):
    rows = [
        {
            **access_request_record("request-1", status="approved"),
            "reviewed_by": REVIEWER_ID,
            "reviewed_at": "2026-05-06T10:00:00+00:00",
            "invite_token": "invite-token",
            "invite_expires_at": "2026-05-20T10:00:00+00:00",
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
    monkeypatch.setattr(
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows, audit_rows=audit_rows),
    )

    lifecycle = await service.get_lifecycle(ORG_ID, "request-1")

    assert lifecycle.email_status == "failed"
    assert lifecycle.provisioning_status == "invite_ready"
    assert lifecycle.retry_available is True
    assert lifecycle.last_event_at == "2026-05-06T10:01:00+00:00"


@pytest.mark.anyio
async def test_pending_lifecycle_is_not_retryable(monkeypatch, service):
    rows = [access_request_record("request-1")]
    monkeypatch.setattr(
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows),
    )

    lifecycle = await service.get_lifecycle(ORG_ID, "request-1")

    assert lifecycle.decision_status == "pending"
    assert lifecycle.email_status == "not_applicable"
    assert lifecycle.provisioning_status == "not_started"
    assert lifecycle.retry_available is False
    assert lifecycle.provisioning_retry_available is False


@pytest.mark.anyio
async def test_failed_provisioning_can_retry_after_decision_email_was_sent(monkeypatch, service):
    rows = [
        {
            **access_request_record("request-1", status="approved"),
            "reviewed_by": REVIEWER_ID,
            "provisioning_status": "failed",
            "provisioning_error": "Identity provisioning failed (IdentityProvisioningError)",
        }
    ]
    audit_rows = [
        {
            "id": "audit-email-sent",
            "org_id": ORG_ID,
            "timestamp": "2026-05-06T10:01:00+00:00",
            "actor_type": "system",
            "actor_id": "system",
            "action": "access_request.email_sent",
            "resource_type": "access_request",
            "resource_id": "request-1",
            "details": {"status": "approved"},
        }
    ]
    monkeypatch.setattr(
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows, audit_rows=audit_rows),
    )

    lifecycle = await service.get_lifecycle(ORG_ID, "request-1")

    assert lifecycle.email_status == "sent"
    assert lifecycle.retry_available is False
    assert lifecycle.provisioning_status == "failed"
    assert lifecycle.provisioning_retry_available is True
