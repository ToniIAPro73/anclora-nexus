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


class MockNeonClient:
    def __init__(self, rows, audit_rows=None):
        self.rows = rows
        self.audit_rows = audit_rows or []
        self.rpc_calls = []

    def table(self, name):
        assert name in {"access_requests", "audit_log"}
        if name == "audit_log":
            return MockAccessRequestQuery(self.audit_rows)
        return MockAccessRequestQuery(self.rows)

    def rpc(self, function_name, params=None):
        return MockAccessRequestRpcQuery(self, function_name, params or {})


class MockAccessRequestRpcQuery:
    def __init__(self, client, function_name, params):
        self.client = client
        self.function_name = function_name
        self.params = params

    def execute(self):
        self.client.rpc_calls.append((self.function_name, self.params))
        params = self.params
        if self.function_name == "nexus_review_access_request":
            row = next((row for row in self.client.rows if row["id"] == params["p_request_id"] and row["org_id"] == params["p_org_id"] and row["status"] == "pending"), None)
            if row is None:
                return MockResult([])
            row.update({
                "status": params["p_decision_status"],
                "reviewed_at": params["p_reviewed_at"],
                "reviewed_by": params["p_reviewer_id"],
                "admin_notes": params["p_admin_notes"],
                "rejection_reason": params["p_rejection_reason"],
                "provisioning_status": "pending" if params["p_decision_status"] == "approved" else "not_applicable",
                "updated_at": params["p_reviewed_at"],
            })
            self.client.audit_rows.append(params["p_audit_event"])
            return MockResult([row])
        if self.function_name == "nexus_finalize_access_request_provisioning":
            row = next((row for row in self.client.rows if row["id"] == params["p_request_id"] and row["org_id"] == params["p_org_id"] and row["status"] == "approved" and row.get("provisioning_status") == "pending"), None)
            if row is None:
                return MockResult([])
            row.update({
                "provisioning_status": params["p_provisioning_status"],
                "provisioning_error": params["p_provisioning_error"],
                "identity_subject_id": params["p_identity_subject_id"],
                "identity_invitation_id": params["p_identity_invitation_id"],
                "membership_id": params["p_membership_id"],
                "invite_token": params["p_invite_token"],
                "invite_expires_at": params["p_invite_expires_at"],
                "updated_at": params["p_updated_at"],
            })
            self.client.audit_rows.append(params["p_audit_event"])
            return MockResult([row])
        if self.function_name == "nexus_begin_access_request_provisioning_retry":
            row = next((row for row in self.client.rows if row["id"] == params["p_request_id"] and row["org_id"] == params["p_org_id"] and row["status"] == "approved" and row.get("provisioning_status") in {"failed", "pending"} and not any(row.get(field) for field in ("identity_subject_id", "identity_invitation_id", "membership_id"))), None)
            if row is None:
                return MockResult([])
            row.update({"provisioning_status": "pending", "updated_at": params["p_started_at"]})
            self.client.audit_rows.append(params["p_audit_event"])
            return MockResult([row])
        if self.function_name == "nexus_log_access_request_audit_event":
            self.client.audit_rows.append(params["p_audit_event"])
            return MockResult([params["p_audit_event"]])
        if self.function_name == "nexus_list_access_request_audit_events":
            result = [event for event in self.client.audit_rows if event.get("org_id") == params["p_org_id"] and (params.get("p_request_id") is None or event.get("resource_id") == params["p_request_id"])]
            if params.get("p_actions"):
                result = [event for event in result if event.get("action") in params["p_actions"]]
            if params.get("p_since"):
                result = [event for event in result if str(event.get("timestamp") or "") >= params["p_since"]]
            return MockResult(result[:params.get("p_limit", len(result))])
        raise AssertionError(f"Unexpected RPC: {self.function_name}")


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

    def prepare_event(self, **kwargs):
        self.events.append(kwargs)
        return {
            "org_id": kwargs["org_id"],
            "actor_type": kwargs["actor_type"],
            "actor_id": kwargs["actor_id"] or "system",
            "action": kwargs["event_type"],
            "resource_type": "access_request",
            "resource_id": kwargs["access_request_id"],
            "details": kwargs["metadata"] or {},
            "signature": "test-signature",
            "timestamp": "2026-10-29T00:00:00+00:00",
        }

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
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows),
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
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows),
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
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows),
    )

    result = await service.get_request(ORG_ID, "request-1")

    assert result["id"] == "request-1"


@pytest.mark.anyio
async def test_get_request_missing_raises_not_found(monkeypatch, service):
    monkeypatch.setattr(
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient([]),
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
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows, audit_rows=audit_rows),
    )

    result = await service.list_audit_events(ORG_ID, "request-1")

    assert [row["id"] for row in result] == ["audit-1"]
    assert result[0]["details"] == {"admin_notes": "Looks good"}


@pytest.mark.anyio
async def test_approve_pending_sets_review_fields(monkeypatch, service):
    rows = [access_request_record("request-1")]
    monkeypatch.setattr(
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows),
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
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows),
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
async def test_approval_is_persisted_and_audited_before_identity_provisioning(monkeypatch, service):
    rows = [access_request_record("request-1")]
    client = MockNeonClient(rows)
    audit_service = MockAuditService()
    provision = AsyncMock(return_value={
        "provisioning_status": "provisioned",
        "provisioning_case": "CASO_B",
        "membership_id": "membership-1",
    })
    monkeypatch.setattr("backend.services.access_request_service.neon_service.client", client)
    monkeypatch.setattr("backend.services.access_request_service.access_request_audit_service", audit_service)

    async def assert_durable_decision(*, request, reviewer_id):
        assert rows[0]["status"] == "approved"
        assert rows[0]["provisioning_status"] == "pending"
        assert client.audit_rows[0]["action"] == "access_request.approved"
        assert client.audit_rows[0]["actor_id"] == reviewer_id
        return await provision(request=request, reviewer_id=reviewer_id)

    monkeypatch.setattr(
        "backend.services.access_request_service.identity_provisioning_service.provision_approved_request",
        assert_durable_decision,
    )

    result = await service.approve_request(
        ORG_ID,
        "request-1",
        AccessRequestReviewDecision(),
        reviewer_id=REVIEWER_ID,
    )

    assert result["membership_id"] == "membership-1"
    assert [name for name, _ in client.rpc_calls] == [
        "nexus_review_access_request",
        "nexus_finalize_access_request_provisioning",
    ]
    provision.assert_awaited_once()


@pytest.mark.anyio
async def test_failed_decision_persistence_never_provisions_identity(monkeypatch, service):
    class FailedDecisionClient(MockNeonClient):
        def rpc(self, function_name, params=None):
            if function_name == "nexus_review_access_request":
                return type("FailedQuery", (), {"execute": lambda _self: MockResult([])})()
            return super().rpc(function_name, params)

    rows = [access_request_record("request-1")]
    provision = AsyncMock()
    monkeypatch.setattr(
        "backend.services.access_request_service.neon_service.client",
        FailedDecisionClient(rows),
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.identity_provisioning_service.provision_approved_request",
        provision,
    )

    with pytest.raises(AccessRequestInvalidTransitionError):
        await service.approve_request(
            ORG_ID,
            "request-1",
            AccessRequestReviewDecision(),
            reviewer_id=REVIEWER_ID,
        )

    provision.assert_not_awaited()
    assert rows[0]["status"] == "pending"


@pytest.mark.anyio
async def test_approve_failed_provisioning_does_not_create_local_token(monkeypatch, service):
    rows = [access_request_record("request-1")]
    monkeypatch.setattr(
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows),
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.identity_provisioning_service.provision_approved_request",
        AsyncMock(
            return_value={
                "provisioning_status": "failed",
                "provisioning_case": "IDENTITY_LOOKUP_FAILED",
                "provisioning_error": "Identity lookup failed HTTP 502",
            }
        ),
    )

    result = await service.approve_request(
        ORG_ID,
        "request-1",
        AccessRequestReviewDecision(),
        reviewer_id=REVIEWER_ID,
    )

    assert result["provisioning_status"] == "failed"
    assert result["invite_token"] is None
    assert result["invite_expires_at"] is None
    assert rows[0]["invite_token"] is None
    assert rows[0]["invite_expires_at"] is None


@pytest.mark.anyio
async def test_retry_failed_provisioning_reuses_approved_request(monkeypatch, service):
    rows = [
        {
            **access_request_record("request-1", status="approved", product="data_lab"),
            "reviewed_by": REVIEWER_ID,
            "reviewed_at": "2026-09-15T05:04:43+00:00",
            "provisioning_status": "failed",
            "provisioning_error": "Identity lookup failed HTTP 502",
            "invite_token": "stale-local-fallback",
            "invite_expires_at": "2026-09-29T05:04:43+00:00",
        }
    ]
    audit_service = MockAuditService()
    monkeypatch.setattr(
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows),
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.access_request_audit_service",
        audit_service,
    )
    provision = AsyncMock(
        return_value={
            "provisioning_status": "invite_ready",
            "provisioning_case": "CASO_A",
            "identity_invitation_id": "inv-real",
            "invite_token": "must-not-be-persisted",
            "invite_expires_at": "2026-09-29T05:04:43+00:00",
        }
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.identity_provisioning_service.provision_approved_request",
        provision,
    )

    result = await service.retry_provisioning(ORG_ID, "request-1", REVIEWER_ID)

    provision.assert_awaited_once()
    assert result["status"] == "approved"
    assert result["provisioning_status"] == "invite_ready"
    assert result["identity_invitation_id"] == "inv-real"
    assert result["invite_token"] is None
    assert result["invite_expires_at"] is None
    assert audit_service.events[-1]["event_type"] == "access_request.provisioning_retry"


@pytest.mark.anyio
async def test_retry_provisioning_rejects_existing_identity(monkeypatch, service):
    rows = [
        {
            **access_request_record("request-1", status="approved", product="data_lab"),
            "provisioning_status": "provisioned",
            "identity_subject_id": "identity-1",
        }
    ]
    monkeypatch.setattr(
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows),
    )

    with pytest.raises(AccessRequestInvalidTransitionError):
        await service.retry_provisioning(ORG_ID, "request-1", REVIEWER_ID)


@pytest.mark.anyio
async def test_retry_provisioning_resends_existing_pending_identity_invitation(monkeypatch, service):
    row = {
        **access_request_record("request-qa", status="approved", product="data_lab"),
        "provisioning_status": "invite_ready",
        "identity_invitation_id": "identity-invitation-1",
    }
    audit_service = MockAuditService()
    monkeypatch.setattr(
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient([row]),
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.access_request_audit_service",
        audit_service,
    )
    resend = AsyncMock(return_value={"outcome": "RESENT", "invitationId": "identity-invitation-1"})
    monkeypatch.setattr(
        "backend.services.access_request_service.identity_provisioning_service.resend_invitation",
        resend,
    )

    result = await service.retry_provisioning(ORG_ID, "request-qa", REVIEWER_ID)

    resend.assert_awaited_once_with(
        application_id="data-lab",
        invitation_id="identity-invitation-1",
        locale="es",
    )
    assert result["identity_invitation_id"] == "identity-invitation-1"
    assert result["provisioning_status"] == "invite_ready"
    assert audit_service.events[-1]["event_type"] == "access_request.invitation_email_retry_succeeded"


@pytest.mark.anyio
async def test_reject_pending_sets_rejection_reason(monkeypatch, service):
    rows = [access_request_record("request-1")]
    monkeypatch.setattr(
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows),
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
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows),
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
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows),
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
async def test_audit_event_preparation_failure_prevents_approval(monkeypatch, service):
    class FailingAuditService:
        def prepare_event(self, **_kwargs):
            raise RuntimeError("audit unavailable")

    rows = [access_request_record("request-1")]
    email_service = MockEmailService()
    monkeypatch.setattr(
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows),
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.access_request_email_service",
        email_service,
    )
    monkeypatch.setattr(
        "backend.services.access_request_service.access_request_audit_service",
        FailingAuditService(),
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        await service.approve_request(
            ORG_ID,
            "request-1",
            AccessRequestReviewDecision(),
            reviewer_id=REVIEWER_ID,
        )

    assert rows[0]["status"] == "pending"
    assert email_service.sent_records == []


def test_reject_decision_requires_rejection_reason():
    with pytest.raises(ValueError, match="rejection_reason is required"):
        AccessRequestRejectDecision(rejection_reason="   ")


@pytest.mark.anyio
@pytest.mark.parametrize("current_status", ["approved", "rejected", "cancelled"])
async def test_approve_terminal_request_fails(monkeypatch, service, current_status):
    rows = [access_request_record("request-1", status=current_status)]
    monkeypatch.setattr(
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows),
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
        "backend.services.access_request_service.neon_service.client",
        MockNeonClient(rows),
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
