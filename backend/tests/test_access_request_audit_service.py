import pytest

from backend.services.access_request_audit_service import AccessRequestAuditService


ORG_ID = "9d6cb56d-3f21-4f7b-80ea-797a7c2c62cf"
REQUEST_ID = "request-1"


class MockNeonService:
    def __init__(self):
        self.inserted = []

    async def insert_audit_log(self, payload):
        self.inserted.append(payload)
        return {"id": "audit-1", **payload}


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
    assert mock_neon.inserted[0]["org_id"] == ORG_ID
    assert mock_neon.inserted[0]["resource_id"] == REQUEST_ID
    assert mock_neon.inserted[0]["resource_type"] == "access_request"
    assert mock_neon.inserted[0]["details"] == {"product": "synergi"}


@pytest.mark.anyio
async def test_log_event_rejects_empty_event_type():
    service = AccessRequestAuditService()

    with pytest.raises(ValueError, match="event_type is required"):
        await service.log_event(
            org_id=ORG_ID,
            access_request_id=REQUEST_ID,
            event_type="   ",
        )
