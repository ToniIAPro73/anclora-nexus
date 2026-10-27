import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, AsyncMock
from backend.services.access_request_service import AccessRequestService
from backend.models.access_requests import AccessRequestSlaSeverity, AccessRequestSlaReason

@pytest.fixture
def mock_neon_service():
    with patch("backend.services.access_request_service.neon_service") as mock:
        # Configure table() to return different mocks
        tables = {}
        def get_table(name):
            if name not in tables:
                tables[name] = MagicMock()
            return tables[name]
        
        mock.client.table.side_effect = get_table
        yield mock

@pytest.fixture
def mock_audit_service():
    with patch("backend.services.access_request_service.access_request_audit_service") as mock:
        mock.create_audit_log_entry = AsyncMock()
        yield mock

@pytest.mark.anyio
async def test_run_sla_scan_deduplication(mock_neon_service, mock_audit_service):
    # Setup
    service = AccessRequestService()
    now = datetime.now(timezone.utc)
    
    # Mock pending request older than 24h
    created_at = (now - timedelta(hours=25)).isoformat()
    mock_request = {
        "id": "req-1",
        "status": "pending",
        "created_at": created_at,
        "email": "test@example.com",
        "full_name": "Test User",
        "product": "synergi",
        "source": "syncxml_landing"
    }
    
    # Table "access_requests" fetch
    mock_neon_service.client.table("access_requests").select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [mock_request]
    
    # Table "audit_log" fetch (dedupe)
    mock_neon_service.client.table("audit_log").select.return_value.eq.return_value.eq.return_value.in_.return_value.gte.return_value.execute.return_value.data = []
    
    result = await service.run_sla_scan(org_id="test-org", reviewer_id="test-reviewer", limit=10)
    
    assert result.scanned_count == 1
    assert result.alerts_created == 1
    assert result.alerts_suppressed == 0
    assert len(result.items) == 1
    assert result.items[0].reason == AccessRequestSlaReason.PENDING_OLDER_THAN_24H
    
    # 2. Mock second scan: audit log exists (dedupe)
    mock_audit_service.create_audit_log_entry.reset_mock()
    mock_neon_service.client.table("audit_log").select.return_value.eq.return_value.eq.return_value.in_.return_value.gte.return_value.execute.return_value.data = [
        {
            "timestamp": now.isoformat(),
            "action": "access_request.sla_warning",
            "resource_id": "req-1",
            "details": {"reason": AccessRequestSlaReason.PENDING_OLDER_THAN_24H, "severity": AccessRequestSlaSeverity.WARNING}
        }
    ]
    
    result = await service.run_sla_scan(org_id="test-org", reviewer_id="test-reviewer", limit=10)
    
    assert result.alerts_created == 0
    assert result.alerts_suppressed == 1

@pytest.mark.anyio
async def test_run_sla_scan_critical_pending(mock_neon_service, mock_audit_service):
    # Setup
    service = AccessRequestService()
    now = datetime.now(timezone.utc)
    
    created_at = (now - timedelta(hours=73)).isoformat()
    mock_request = {
        "id": "req-critical",
        "status": "pending",
        "created_at": created_at,
        "email": "test@example.com",
        "full_name": "Critical User",
        "product": "synergi"
    }
    
    mock_neon_service.client.table("access_requests").select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [mock_request]
    mock_neon_service.client.table("audit_log").select.return_value.eq.return_value.eq.return_value.in_.return_value.gte.return_value.execute.return_value.data = []
    
    result = await service.run_sla_scan(org_id="test-org", reviewer_id="test-reviewer")
    
    assert result.alerts_created == 1
    assert result.items[0].severity == AccessRequestSlaSeverity.CRITICAL
    assert result.items[0].reason == AccessRequestSlaReason.PENDING_OLDER_THAN_72H

@pytest.mark.anyio
async def test_run_sla_scan_failed_email(mock_neon_service, mock_audit_service):
    # Setup
    service = AccessRequestService()
    now = datetime.now(timezone.utc)
    
    mock_request = {
        "id": "req-failed-email",
        "status": "approved",
        "email": "test@example.com",
        "created_at": now.isoformat()
    }
    
    mock_neon_service.client.table("access_requests").select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [mock_request]
    mock_neon_service.client.table("audit_log").select.return_value.eq.return_value.eq.return_value.in_.return_value.gte.return_value.execute.return_value.data = []
    
    # Mock individual request audit for lifecycle
    # email_send_failed -> DECISION_EMAIL_FAILED
    # retry_available = True -> RETRY_AVAILABLE alert
    mock_neon_service.client.table("audit_log").select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"action": "access_request.email_send_failed", "details": {"status": "failed"}},
        {"action": "access_request.provisioning_invite_sent", "details": {}}
    ]
    
    result = await service.run_sla_scan(org_id="test-org", reviewer_id="test-reviewer")
    
    found_reasons = [item.reason for item in result.items]
    assert AccessRequestSlaReason.DECISION_EMAIL_FAILED in found_reasons

@pytest.mark.anyio
async def test_run_sla_scan_provisioning_attention(mock_neon_service, mock_audit_service):
    # Setup
    service = AccessRequestService()
    now = datetime.now(timezone.utc)
    
    mock_request = {
        "id": "req-no-prov",
        "status": "approved",
        "email": "test@example.com",
        "product": "synergi",
        "full_name": "No Prov User",
        "created_at": now.isoformat()
    }
    
    mock_neon_service.client.table("access_requests").select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [mock_request]
    mock_neon_service.client.table("audit_log").select.return_value.eq.return_value.eq.return_value.in_.return_value.gte.return_value.execute.return_value.data = []
    
    # Lifecycle: approved, email sent successfully, but NO provisioning
    mock_neon_service.client.table("audit_log").select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"action": "access_request.approved", "details": {}},
        {"action": "access_request.email_sent", "details": {"status": "sent"}}
    ]
    
    result = await service.run_sla_scan(org_id="test-org", reviewer_id="test-reviewer")
    
    found_reasons = [item.reason for item in result.items]
    assert AccessRequestSlaReason.PROVISIONING_ATTENTION in found_reasons
