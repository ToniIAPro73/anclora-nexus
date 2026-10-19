import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock, AsyncMock
from backend.api.main import app

@pytest.fixture
def mock_service():
    with patch("backend.api.routes.public.access_request_service", new_callable=AsyncMock) as mock:
        yield mock

@pytest.mark.anyio
async def test_create_access_request_api(mock_service):
    # Setup
    mock_service.create_public_request.return_value = {
        "id": "test-uuid",
        "status": "pending"
    }
    
    payload = {
        "product": "data_lab",
        "source": "nexus_manual",
        "full_name": "Data Analyst",
        "email": "analyst@example.com",
        "intended_use": "Market research",
        "privacy_accepted": True,
        "gdpr_consent": True,
        "captcha_provider": "turnstile",
        "captcha_token": "valid-token"
    }
    
    # Execute
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/public/access-requests", json=payload)
    
    # Assert
    assert response.status_code == 201, f"Response: {response.text}"
    assert response.json()["request_id"] == "test-uuid"
    assert response.json()["status"] == "submitted"
    mock_service.create_public_request.assert_called_once()
    # Check that org_id was NOT in the payload (service should handle it)
    args, _ = mock_service.create_public_request.call_args
    assert "org_id" not in args[0].model_dump()

@pytest.mark.anyio
async def test_create_access_request_forbidden_org_id(mock_service):
    payload = {
        "org_id": "9d6cb56d-3f21-4f7b-80ea-797a7c2c62cf",
        "product": "data_lab",
        "source": "nexus_manual",
        "full_name": "Attacker",
        "email": "attacker@example.com",
        "intended_use": "Injection",
        "privacy_accepted": True,
        "gdpr_consent": True,
        "captcha_token": "token"
    }
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/public/access-requests", json=payload)
    
    # Assert
    assert response.status_code == 422 # Pydantic extra="forbid" raises validation error

@pytest.mark.anyio
async def test_legacy_data_lab_wrapper(mock_service):
    mock_service.create_public_request.return_value = {"id": "legacy-id", "status": "pending"}
    
    payload = {
        "full_name": "Legacy User",
        "email": "legacy@example.com",
        "intended_use": "Legacy study",
        "privacy_accepted": True,
        "gdpr_consent": True,
        "captcha_token": "token"
    }
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/public/data-lab-access-requests", json=payload)
    
    assert response.status_code == 201
    args, _ = mock_service.create_public_request.call_args
    assert args[0].product == "data_lab"
    assert args[0].source == "data_lab_app"

@pytest.mark.anyio
async def test_legacy_partner_admission_wrapper(mock_service):
    mock_service.create_public_request.return_value = {"id": "legacy-id", "status": "pending"}
    
    payload = {
        "full_name": "Legacy Partner",
        "email": "partner@example.com",
        "service_category": "agent",
        "service_summary": "summary",
        "privacy_accepted": True,
        "gdpr_consent": True,
        "captcha_token": "token"
    }
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/public/partner-admissions", json=payload)
    
    assert response.status_code == 201
    args, _ = mock_service.create_public_request.call_args
    assert args[0].product == "synergi"
    assert args[0].source == "synergi_app"
