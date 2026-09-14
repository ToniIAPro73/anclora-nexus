import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.models.access_requests import (
    AccessRequestProduct,
    AccessRequestProvisioningStatus,
    AccessRequestReviewDecision,
    AccessRequestStatus,
)
from backend.services.access_request_service import AccessRequestService
from backend.services.identity_provisioning_service import (
    IdentityProvisioningService,
)


@pytest.fixture
def mock_supabase():
    with patch("backend.services.access_request_service.supabase_service") as mock:
        yield mock


@pytest.fixture
def provisioning_service():
    return IdentityProvisioningService(
        base_url="http://test-identity:4001",
        service_token="test-service-token",
        enabled=True,
    )


@pytest.mark.anyio
async def test_lookup_identity_found(provisioning_service):
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "exists": True,
            "user": {
                "id": "usr-123",
                "email": "existing@anclora.com",
                "displayName": "Existing User",
                "applicationMemberships": ["data-lab"],
            },
        }
        mock_get.return_value = mock_resp

        user = await provisioning_service.lookup_identity("existing@anclora.com")
        assert user is not None
        assert user["id"] == "usr-123"
        assert user["email"] == "existing@anclora.com"


@pytest.mark.anyio
async def test_lookup_identity_not_found(provisioning_service):
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"exists": False}
        mock_get.return_value = mock_resp

        user = await provisioning_service.lookup_identity("newbie@anclora.com")
        assert user is None


@pytest.mark.anyio
async def test_provision_caso_a_new_identity(provisioning_service):
    """CASO A: Identity does not exist -> create invitation."""
    with patch.object(provisioning_service, "lookup_identity", new_callable=AsyncMock) as mock_lookup, \
         patch.object(provisioning_service, "create_invitation", new_callable=AsyncMock) as mock_invite:
        mock_lookup.return_value = None
        mock_invite.return_value = {
            "invitation": {
                "id": "inv-999",
                "token": "tok-abc",
                "expiresAt": "2026-10-01T00:00:00Z",
            },
            "inviteUrl": "https://identity.anclora.com/invitations/tok-abc",
        }

        request_data = {
            "id": "req-1",
            "email": "newbie@anclora.com",
            "product": "data_lab",
            "submission_language": "es",
        }
        result = await provisioning_service.provision_approved_request(request_data, reviewer_id="rev-1")

        assert result["provisioning_status"] == "invite_ready"
        assert result["provisioning_case"] == "CASO_A"
        assert result["identity_invitation_id"] == "inv-999"
        assert result["invite_token"] == "tok-abc"
        assert result["invite_url"] == "https://identity.anclora.com/invitations/tok-abc"
        mock_invite.assert_called_once_with(
            application_id="data-lab",
            email="newbie@anclora.com",
            reviewer_id="rev-1",
            locale="es",
        )


@pytest.mark.anyio
async def test_provision_caso_b_existing_identity(provisioning_service):
    """CASO B: Identity exists -> grant direct application membership."""
    with patch.object(provisioning_service, "lookup_identity", new_callable=AsyncMock) as mock_lookup, \
         patch.object(provisioning_service, "grant_membership", new_callable=AsyncMock) as mock_grant:
        mock_lookup.return_value = {
            "id": "usr-existing-456",
            "email": "existing@anclora.com",
        }
        mock_grant.return_value = {
            "membership": {
                "id": "mem-789",
                "identityUserId": "usr-existing-456",
                "applicationId": "synergi",
            },
            "granted": True,
        }

        request_data = {
            "id": "req-2",
            "email": "existing@anclora.com",
            "product": "synergi",
            "submission_language": "es",
        }
        result = await provisioning_service.provision_approved_request(request_data, reviewer_id="rev-1")

        assert result["provisioning_status"] == "provisioned"
        assert result["provisioning_case"] == "CASO_B"
        assert result["identity_subject_id"] == "usr-existing-456"
        assert result["membership_id"] == "mem-789"
        mock_grant.assert_called_once_with("synergi", "usr-existing-456")


@pytest.mark.anyio
async def test_approve_request_updates_record_with_caso_a(mock_supabase):
    """AccessRequestService.approve_request correctly stores CASO A invitation details."""
    service = AccessRequestService()

    pending_record = {
        "id": "req-caso-a",
        "org_id": "org-test",
        "status": "pending",
        "product": "data_lab",
        "email": "newbie@anclora.com",
    }

    mock_query = MagicMock()
    mock_supabase.client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.execute.return_value.data = [pending_record]

    updated_record = {
        **pending_record,
        "status": "approved",
        "reviewed_by": "admin-1",
        "identity_invitation_id": "inv-001",
        "invite_token": "token-xyz",
        "invite_expires_at": "2026-10-01T00:00:00Z",
        "provisioning_status": "invite_ready",
    }
    mock_query.update.return_value = mock_query
    # When update().execute() is called, return updated_record
    mock_query.execute.side_effect = [
        MagicMock(data=[pending_record]),  # _ensure_pending
        MagicMock(data=[updated_record]),   # _update_pending_request
    ]

    with patch("backend.services.access_request_service.identity_provisioning_service.provision_approved_request", new_callable=AsyncMock) as mock_prov, \
         patch.object(service, "_send_decision_email", new_callable=AsyncMock) as mock_email:
        mock_prov.return_value = {
            "provisioning_status": "invite_ready",
            "provisioning_case": "CASO_A",
            "identity_invitation_id": "inv-001",
            "invite_token": "token-xyz",
            "invite_expires_at": "2026-10-01T00:00:00Z",
        }
        mock_email.return_value = {"status": "sent"}

        decision = AccessRequestReviewDecision(admin_notes="Approved for pilot")
        result = await service.approve_request(
            org_id="org-test",
            request_id="req-caso-a",
            decision=decision,
            reviewer_id="admin-1",
        )

        assert result["status"] == "approved"
        assert result["provisioning_status"] == "invite_ready"
        assert result["identity_invitation_id"] == "inv-001"
        assert result["invite_token"] == "token-xyz"
        assert result["lifecycle"]["provisioning_status"] == AccessRequestProvisioningStatus.INVITE_READY


@pytest.mark.anyio
async def test_approve_request_updates_record_with_caso_b(mock_supabase):
    """AccessRequestService.approve_request correctly stores CASO B membership details."""
    service = AccessRequestService()

    pending_record = {
        "id": "req-caso-b",
        "org_id": "org-test",
        "status": "pending",
        "product": "synergi",
        "email": "existing@anclora.com",
    }

    mock_query = MagicMock()
    mock_supabase.client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.limit.return_value = mock_query

    updated_record = {
        **pending_record,
        "status": "approved",
        "reviewed_by": "admin-1",
        "identity_subject_id": "usr-456",
        "membership_id": "mem-123",
        "provisioning_status": "provisioned",
    }
    mock_query.update.return_value = mock_query
    mock_query.execute.side_effect = [
        MagicMock(data=[pending_record]),  # _ensure_pending
        MagicMock(data=[updated_record]),   # _update_pending_request
    ]

    with patch("backend.services.access_request_service.identity_provisioning_service.provision_approved_request", new_callable=AsyncMock) as mock_prov, \
         patch.object(service, "_send_decision_email", new_callable=AsyncMock) as mock_email:
        mock_prov.return_value = {
            "provisioning_status": "provisioned",
            "provisioning_case": "CASO_B",
            "identity_subject_id": "usr-456",
            "membership_id": "mem-123",
        }
        mock_email.return_value = {"status": "sent"}

        decision = AccessRequestReviewDecision(admin_notes="Approved membership")
        result = await service.approve_request(
            org_id="org-test",
            request_id="req-caso-b",
            decision=decision,
            reviewer_id="admin-1",
        )

        assert result["status"] == "approved"
        assert result["provisioning_status"] == "provisioned"
        assert result["identity_subject_id"] == "usr-456"
        assert result["membership_id"] == "mem-123"
        assert result["lifecycle"]["provisioning_status"] == AccessRequestProvisioningStatus.PROVISIONED


@pytest.mark.anyio
async def test_provision_fail_closed_disabled():
    """Fail-closed: when Identity is disabled, return pending status and never simulate success."""
    service = IdentityProvisioningService(base_url="http://test:4001", service_token="tok", enabled=False)
    req = {"id": "req-fc-1", "email": "fc@example.com", "product": "data_lab"}
    res = await service.provision_approved_request(req, reviewer_id="rev-1")
    assert res["provisioning_status"] == "pending"
    assert res["provisioning_case"] == "NOT_CONFIGURED"
    assert res["identity_subject_id"] is None
    assert res["identity_invitation_id"] is None
    assert res["membership_id"] is None


@pytest.mark.anyio
async def test_provision_fail_closed_network_error(provisioning_service):
    """Fail-closed: when Identity call fails with network/500 error, return failed without simulated credentials."""
    with patch.object(provisioning_service, "lookup_identity", side_effect=Exception("Network connection refused")):
        req = {"id": "req-fc-2", "email": "err@example.com", "product": "synergi"}
        res = await provisioning_service.provision_approved_request(req, reviewer_id="rev-1")
        assert res["provisioning_status"] == "failed"
        assert "Network connection refused" in res["provisioning_error"]
        assert res["identity_subject_id"] is None
        assert res["identity_invitation_id"] is None
        assert res["membership_id"] is None


@pytest.mark.anyio
async def test_approve_request_updates_record_fail_closed(mock_supabase):
    """When Identity provisioning fails, admission is still human-approved but provisioning_status is 'failed'."""
    service = AccessRequestService()

    pending_record = {
        "id": "req-fc-3",
        "org_id": "org-test",
        "status": "pending",
        "product": "data_lab",
        "email": "fc@example.com",
    }

    mock_query = MagicMock()
    mock_supabase.client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.limit.return_value = mock_query

    updated_record = {
        **pending_record,
        "status": "approved",
        "reviewed_by": "admin-1",
        "provisioning_status": "failed",
        "provisioning_error": "Service unavailable",
    }
    mock_query.update.return_value = mock_query
    mock_query.execute.side_effect = [
        MagicMock(data=[pending_record]),
        MagicMock(data=[updated_record]),
    ]

    with patch("backend.services.access_request_service.identity_provisioning_service.provision_approved_request", new_callable=AsyncMock) as mock_prov, \
         patch.object(service, "_send_decision_email", new_callable=AsyncMock) as mock_email:
        mock_prov.return_value = {
            "provisioning_status": "failed",
            "provisioning_error": "Service unavailable",
            "identity_subject_id": None,
            "identity_invitation_id": None,
            "membership_id": None,
        }
        mock_email.return_value = {"status": "skipped"}

        decision = AccessRequestReviewDecision(admin_notes="Approved with downstream error")
        result = await service.approve_request(
            org_id="org-test",
            request_id="req-fc-3",
            decision=decision,
            reviewer_id="admin-1",
        )

        assert result["status"] == "approved"
        assert result["provisioning_status"] == "failed"
        assert result.get("identity_invitation_id") is None
        assert result.get("membership_id") is None
        assert result["lifecycle"]["provisioning_status"] == AccessRequestProvisioningStatus.FAILED
