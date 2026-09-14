import pytest
from unittest.mock import AsyncMock

from backend.models.access_requests import (
    AccessRequestProduct,
    AccessRequestRejectDecision,
    AccessRequestReviewDecision,
    AccessRequestSource,
    AccessRequestStatus,
)
from backend.services.access_request_service import (
    AccessRequestInvalidTransitionError,
    AccessRequestNotFoundError,
    AccessRequestService,
)


ORG_ID = "9d6cb56d-3f21-4f7b-80ea-797a7c2c62cf"
REVIEWER_ID = "admin-user"


def access_request_record(
    request_id: str = "request-1",
    status: str = "pending",
    product: str = "synergi",
) -> dict:
    return {
        "id": request_id,
        "org_id": ORG_ID,
        "product": product,
        "source": "syncxml_landing",
        "status": status,
        "intake_domain": "access_request",
        "full_name": "Test User",
        "email": "test@example.com",
        "privacy_accepted": True,
        "gdpr_consent": True,
        "submission_language": "es",
        "captcha_verified": True,
        "created_at": "2026-05-06T10:00:00+00:00",
        "updated_at": "2026-05-06T10:00:00+00:00",
    }


class MockResult:
    def __init__(self, data):
        self.data = data


class MockAccessRequestQuery:
    def __init__(self, rows, update_payload=None):
        self.rows = rows
        self.update_payload = update_payload
        self.filters = []
        self.ilike_filters = []
        self.gte_filters = []
        self.lte_filters = []
        self.limit_value = None
        self.order_desc = False
        self.order_key = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def ilike(self, key, pattern):
        self.ilike_filters.append((key, pattern.strip("%").lower()))
        return self

    def gte(self, key, value):
        self.gte_filters.append((key, value))
        return self

    def lte(self, key, value):
        self.lte_filters.append((key, value))
        return self

    def order(self, _key, desc=False):
        self.order_key = _key
        self.order_desc = desc
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def update(self, payload):
        return MockAccessRequestQuery(self.rows, update_payload=payload)

    def execute(self):
        matches = [
            row for row in self.rows
            if all(row.get(key) == value for key, value in self.filters)
        ]
        for key, value in self.ilike_filters:
            matches = [row for row in matches if value in str(row.get(key) or "").lower()]
        for key, value in self.gte_filters:
            matches = [row for row in matches if str(row.get(key) or "") >= value]
        for key, value in self.lte_filters:
            matches = [row for row in matches if str(row.get(key) or "") <= value]
        if self.order_desc:
            matches = list(reversed(matches))
        if self.limit_value is not None:
            matches = matches[: self.limit_value]
        if self.update_payload is not None:
            for row in matches:
                row.update(self.update_payload)
        return MockResult(matches)


class MockSupabaseClient:
    def __init__(self, rows, audit_rows=None):
        self.rows = rows
        self.audit_rows = audit_rows or []

    def table(self, name):
        assert name in {"access_requests", "audit_log"}
        if name == "audit_log":
            return MockAccessRequestQuery(self.audit_rows)
        return MockAccessRequestQuery(self.rows)


class MockEmailService:
    def __init__(self, fail=False, result=None):
        self.fail = fail
        self.result = result
        self.sent_records = []

    def send_decision_email(self, record):
        self.sent_records.append(dict(record))
        if self.fail:
            raise RuntimeError("SMTP failed")
        if self.result is not None:
            return self.result
        return {"status": "sent", "transport": "smtp", "to": record["email"]}


class MockAuditService:
    def __init__(self):
        self.events = []

    async def log_event(self, **kwargs):
        self.events.append(kwargs)
        return {"id": f"audit-{len(self.events)}", **kwargs}


@pytest.fixture
def service():
    return AccessRequestService()


@pytest.mark.anyio
async def test_list_requests_filters_by_status_and_product(monkeypatch, service):
    rows = [
        access_request_record("request-1", status="pending", product="synergi"),
        access_request_record("request-2", status="approved", product="synergi"),
        access_request_record("request-3", status="pending", product="data_lab"),
    ]
    monkeypatch.setattr(
        "backend.services.access_request_service.supabase_service.client",
        MockSupabaseClient(rows),
    )

    result = await service.list_requests(
        org_id=ORG_ID,
        status=AccessRequestStatus.PENDING,
        product=AccessRequestProduct.DATA_LAB,
    )

    assert [row["id"] for row in result] == ["request-3"]


@pytest.mark.anyio
async def test_list_requests_applies_operations_filters(monkeypatch, service):
    rows = [
        {
            **access_request_record("request-1", status="pending", product="synergi"),
            "source": "nexus_manual",
            "email": "ana@example.com",
            "created_at": "2026-05-01T10:00:00+00:00",
        },
        {
            **access_request_record("request-2", status="pending", product="synergi"),
            "source": "synergi_app",
            "email": "beta@example.com",
            "created_at": "2026-05-03T10:00:00+00:00",
        },
        {
            **access_request_record("request-3", status="pending", product="synergi"),
            "source": "nexus_manual",
            "email": "ana.later@example.com",
            "created_at": "2026-05-08T10:00:00+00:00",
        },
    ]
    monkeypatch.setattr(
        "backend.services.access_request_service.supabase_service.client",
        MockSupabaseClient(rows),
    )

    result = await service.list_requests(
        org_id=ORG_ID,
        status=AccessRequestStatus.PENDING,
        product=AccessRequestProduct.SYNERGI,
        source=AccessRequestSource.NEXUS_MANUAL,
        email="ana",
        created_from="2026-05-01T00:00:00+00:00",
        created_to="2026-05-04T00:00:00+00:00",
    )

    assert [row["id"] for row in result] == ["request-1"]


@pytest.mark.anyio
async def test_get_request_existing(monkeypatch, service):
    rows = [access_request_record("request-1")]
    monkeypatch.setattr(
        "backend.services.access_request_service.supabase_service.client",
        MockSupabaseClient(rows),
    )

    result = await service.get_request(ORG_ID, "request-1")

    assert result["id"] == "request-1"


@pytest.mark.anyio
async def test_get_request_missing_raises_not_found(monkeypatch, service):
    monkeypatch.setattr(
        "backend.services.access_request_service.supabase_service.client",
        MockSupabaseClient([]),
    )

    with pytest.raises(AccessRequestNotFoundError):
        await service.get_request(ORG_ID, "missing")


@pytest.mark.anyio
async def test_list_audit_events_returns_request_scoped_events(monkeypatch, service):
    rows = [access_request_record("request-1")]
    audit_rows = [
        {
            "id": "audit-1",
            "org_id": ORG_ID,
            "timestamp": "2026-05-06T10:00:00+00:00",
            "actor_type": "user",
            "actor_id": REVIEWER_ID,
            "action": "access_request.approved",
            "resource_type": "access_request",
            "resource_id": "request-1",
            "details": {"admin_notes": "Looks good"},
        },
        {
            "id": "audit-2",
            "org_id": ORG_ID,
            "timestamp": "2026-05-06T11:00:00+00:00",
            "actor_type": "user",
            "actor_id": REVIEWER_ID,
            "action": "access_request.approved",
            "resource_type": "access_request",
            "resource_id": "other-request",
            "details": {},
        },
    ]
    monkeypatch.setattr(
        "backend.services.access_request_service.supabase_service.client",
        MockSupabaseClient(rows, audit_rows=audit_rows),
    )

    result = await service.list_audit_events(ORG_ID, "request-1")

    assert [row["id"] for row in result] == ["audit-1"]
    assert result[0]["details"] == {"admin_notes": "Looks good"}


@pytest.mark.anyio
async def test_approve_pending_sets_review_fields(monkeypatch, service):
    rows = [access_request_record("request-1")]
    monkeypatch.setattr(
        "backend.services.access_request_service.supabase_service.client",
        MockSupabaseClient(rows),
    )

    result = await service.approve_request(
        ORG_ID,
        "request-1",
        AccessRequestReviewDecision(admin_notes="Looks good"),
        reviewer_id=REVIEWER_ID,
    )

    assert result["status"] == "approved"
    assert result["reviewed_by"] == REVIEWER_ID
    assert result["admin_notes"] == "Looks good"
    assert result["reviewed_at"]
    assert result["invite_token"]
    assert result["invite_expires_at"]


@pytest.mark.anyio
async def test_approve_sends_email_after_state_update(monkeypatch, service):
    rows = [access_request_record("request-1")]
    email_service = MockEmailService()
    audit_service = MockAuditService()
    monkeypatch.setattr(
        "backend.services.access_request_service.supabase_service.client",
        MockSupabaseClient(rows),
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.access_request_email_service",
        email_service,
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.access_request_audit_service",
        audit_service,
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

    assert result["status"] == "approved"
    assert email_service.sent_records[0]["status"] == "approved"
    assert result["decision_email"]["status"] == "sent"
    assert [event["event_type"] for event in audit_service.events] == [
        "access_request.approved",
        "access_request.provisioning_intent_prepared",
        "access_request.email_sent",
    ]
    assert audit_service.events[0]["actor_id"] == REVIEWER_ID
    assert audit_service.events[1]["metadata"]["provisioning_status"] == "invite_ready"


@pytest.mark.anyio
async def test_reject_pending_sets_rejection_reason(monkeypatch, service):
    rows = [access_request_record("request-1")]
    monkeypatch.setattr(
        "backend.services.access_request_service.supabase_service.client",
        MockSupabaseClient(rows),
    )

    result = await service.reject_request(
        ORG_ID,
        "request-1",
        AccessRequestRejectDecision(
            admin_notes="Not a fit",
            rejection_reason="Missing eligibility criteria",
        ),
        reviewer_id=REVIEWER_ID,
    )

    assert result["status"] == "rejected"
    assert result["reviewed_by"] == REVIEWER_ID
    assert result["rejection_reason"] == "Missing eligibility criteria"
    assert result["reviewed_at"]


@pytest.mark.anyio
async def test_reject_sends_email_after_state_update(monkeypatch, service):
    rows = [access_request_record("request-1")]
    email_service = MockEmailService()
    audit_service = MockAuditService()
    monkeypatch.setattr(
        "backend.services.access_request_service.supabase_service.client",
        MockSupabaseClient(rows),
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.access_request_email_service",
        email_service,
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.access_request_audit_service",
        audit_service,
    )

    result = await service.reject_request(
        ORG_ID,
        "request-1",
        AccessRequestRejectDecision(
            rejection_reason="Not eligible",
        ),
        reviewer_id=REVIEWER_ID,
    )

    assert result["status"] == "rejected"
    assert email_service.sent_records[0]["status"] == "rejected"
    assert result["decision_email"]["status"] == "sent"
    assert [event["event_type"] for event in audit_service.events] == [
        "access_request.rejected",
        "access_request.email_sent",
    ]
    assert audit_service.events[0]["actor_id"] == REVIEWER_ID


@pytest.mark.anyio
async def test_email_failure_does_not_revert_decision_and_logs_failure(monkeypatch, service):
    rows = [access_request_record("request-1")]
    email_service = MockEmailService(fail=True)
    audit_service = MockAuditService()
    monkeypatch.setattr(
        "backend.services.access_request_service.supabase_service.client",
        MockSupabaseClient(rows),
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.access_request_email_service",
        email_service,
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

    assert rows[0]["status"] == "approved"
    assert result["status"] == "approved"
    assert result["decision_email"]["status"] == "failed"
    assert "SMTP failed" in result["decision_email"]["error"]
    assert [event["event_type"] for event in audit_service.events] == [
        "access_request.approved",
        "access_request.provisioning_intent_prepared",
        "access_request.email_send_failed",
    ]


@pytest.mark.anyio
async def test_audit_failure_does_not_break_approval(monkeypatch, service):
    class FailingAuditService:
        async def log_event(self, **_kwargs):
            raise RuntimeError("audit unavailable")

    rows = [access_request_record("request-1")]
    email_service = MockEmailService()
    monkeypatch.setattr(
        "backend.services.access_request_service.supabase_service.client",
        MockSupabaseClient(rows),
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.access_request_email_service",
        email_service,
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.access_request_audit_service",
        FailingAuditService(),
    )

    result = await service.approve_request(
        ORG_ID,
        "request-1",
        AccessRequestReviewDecision(),
        reviewer_id=REVIEWER_ID,
    )

    assert result["status"] == "approved"
    assert result["decision_email"]["status"] == "sent"


def test_reject_decision_requires_rejection_reason():
    with pytest.raises(ValueError, match="rejection_reason is required"):
        AccessRequestRejectDecision(rejection_reason="   ")


@pytest.mark.anyio
@pytest.mark.parametrize("current_status", ["approved", "rejected", "cancelled"])
async def test_approve_terminal_request_fails(monkeypatch, service, current_status):
    rows = [access_request_record("request-1", status=current_status)]
    monkeypatch.setattr(
        "backend.services.access_request_service.supabase_service.client",
        MockSupabaseClient(rows),
    )

    with pytest.raises(AccessRequestInvalidTransitionError):
        await service.approve_request(
            ORG_ID,
            "request-1",
            AccessRequestReviewDecision(),
            reviewer_id=REVIEWER_ID,
        )


@pytest.mark.anyio
@pytest.mark.parametrize("current_status", ["approved", "rejected", "cancelled"])
async def test_reject_terminal_request_fails(monkeypatch, service, current_status):
    rows = [access_request_record("request-1", status=current_status)]
    monkeypatch.setattr(
        "backend.services.access_request_service.supabase_service.client",
        MockSupabaseClient(rows),
    )

    with pytest.raises(AccessRequestInvalidTransitionError):
        await service.reject_request(
            ORG_ID,
            "request-1",
            AccessRequestRejectDecision(
                rejection_reason="Not eligible",
            ),
            reviewer_id=REVIEWER_ID,
        )
