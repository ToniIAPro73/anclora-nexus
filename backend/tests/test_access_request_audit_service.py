from types import SimpleNamespace

import pytest

from backend.services.access_request_audit_service import AccessRequestAuditService


ORG_ID = "9d6cb56d-3f21-4f7b-80ea-797a7c2c62cf"
REQUEST_ID = "request-1"


class _RpcCall:
    def __init__(self, owner, name, params):
        self.owner, self.name, self.params = owner, name, params

    def execute(self):
        self.owner.rpc_calls.append((self.name, self.params))
        return SimpleNamespace(data=[self.params["p_audit_event"]])


class _MockClient:
    def __init__(self, owner):
        self.owner = owner

    def rpc(self, name, params):
        return _RpcCall(self.owner, name, params)


class MockNeonService:
    """Mirrors the atomic persistence contract: the service signs the event, the DB function stores it."""

    def __init__(self):
        self.rpc_calls = []
        self.client = _MockClient(self)

    def prepare_access_request_audit_event(self, data):
        return {**data, "signature": "test-signature", "timestamp": "2026-01-01T00:00:00"}


@pytest.mark.anyio
@pytest.mark.parametrize(
    "event_type",
    ["access_request.created", "access_request.approved", "access_request.rejected"],
)
async def test_log_access_request_events(monkeypatch, event_type):
    mock_neon = MockNeonService()
    monkeypatch.setattr(
        "backend.services.access_request_audit_service.neon_service",
        mock_neon,
    )

    service = AccessRequestAuditService()
    result = await service.log_event(
        org_id=ORG_ID,
        access_request_id=REQUEST_ID,
        event_type=event_type,
        actor_id="admin-user",
        actor_type="user",
        metadata={"product": "synergi"},
    )

    assert result["action"] == event_type
    assert result["signature"] == "test-signature"
    name, params = mock_neon.rpc_calls[0]
    assert name == "nexus_log_access_request_audit_event"
    assert params["p_org_id"] == ORG_ID
    assert params["p_request_id"] == REQUEST_ID
    event = params["p_audit_event"]
    assert event["org_id"] == ORG_ID
    assert event["resource_id"] == REQUEST_ID
    assert event["resource_type"] == "access_request"
    assert event["details"] == {"product": "synergi"}


@pytest.mark.anyio
async def test_log_event_rejects_empty_event_type():
    service = AccessRequestAuditService()

    with pytest.raises(ValueError, match="event_type is required"):
        await service.log_event(
            org_id=ORG_ID,
            access_request_id=REQUEST_ID,
            event_type="   ",
        )
