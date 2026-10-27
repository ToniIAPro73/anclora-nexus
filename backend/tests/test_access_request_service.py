import pytest
from unittest.mock import MagicMock, patch
from backend.models.access_requests import PublicAccessRequestCreate, AccessRequestProduct, AccessRequestSource
from backend.services.access_request_service import AccessRequestService
from backend.services.captcha_verification_service import CaptchaVerificationError

@pytest.fixture
def mock_neon_service():
    with patch("backend.services.access_request_service.neon_service") as mock:
        yield mock

@pytest.fixture
def mock_captcha():
    with patch("backend.services.access_request_service.captcha_verification_service") as mock:
        yield mock

@pytest.mark.anyio
async def test_create_public_request_success(mock_neon_service, mock_captcha):
    # Setup
    mock_captcha.verify.return_value = {"verified": True, "hostname": "test.com", "required": True}
    
    mock_neon_service.client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "test-id", "status": "pending", "product": "synergi", "email": "test@example.com"}
    ]
    
    service = AccessRequestService()
    data = PublicAccessRequestCreate(
        product=AccessRequestProduct.SYNERGI,
        source=AccessRequestSource.NEXUS_MANUAL,
        full_name="Test User",
        email="test@example.com",
        service_category="agent",
        service_summary="test summary",
        privacy_accepted=True,
        gdpr_consent=True,
        captcha_token="valid-token"
    )
    
    # Execute
    result = await service.create_public_request(data)
    
    # Assert
    assert result["id"] == "test-id"
    assert result["status"] == "pending"
    mock_captcha.verify.assert_called_once()
    # Verify org_id was injected
    args, kwargs = mock_neon_service.client.table.return_value.insert.call_args
    assert args[0]["org_id"] == "9d6cb56d-3f21-4f7b-80ea-797a7c2c62cf"

@pytest.mark.anyio
async def test_create_public_request_captcha_fail(mock_captcha):
    # Setup
    mock_captcha.verify.return_value = {"verified": False, "hostname": "test.com", "required": True}
    
    service = AccessRequestService()
    data = PublicAccessRequestCreate(
        product=AccessRequestProduct.SYNERGI,
        source=AccessRequestSource.NEXUS_MANUAL,
        full_name="Test User",
        email="test@example.com",
        service_category="agent",
        service_summary="test summary",
        privacy_accepted=True,
        gdpr_consent=True,
        captcha_token="invalid-token"
    )
    
    # Execute & Assert
    with pytest.raises(CaptchaVerificationError):
        await service.create_public_request(data)

def test_model_validation_product_source_mismatch():
    with pytest.raises(ValueError, match="Synergi app source requires Synergi product"):
        PublicAccessRequestCreate(
            product=AccessRequestProduct.DATA_LAB,
            source=AccessRequestSource.SYNERGI_APP,
            full_name="Test",
            email="test@example.com",
            privacy_accepted=True,
            gdpr_consent=True,
            captcha_token="token"
        )

def test_model_validation_missing_fields_synergi():
    with pytest.raises(ValueError, match="Synergi requests require service_category and service_summary"):
        PublicAccessRequestCreate(
            product=AccessRequestProduct.SYNERGI,
            source=AccessRequestSource.NEXUS_MANUAL,
            full_name="Test",
            email="test@example.com",
            privacy_accepted=True,
            gdpr_consent=True,
            captcha_token="token"
        )

def test_model_validation_missing_fields_datalab():
    with pytest.raises(ValueError, match="Data Lab requests require intended_use or message"):
        PublicAccessRequestCreate(
            product=AccessRequestProduct.DATA_LAB,
            source=AccessRequestSource.NEXUS_MANUAL,
            full_name="Test",
            email="test@example.com",
            privacy_accepted=True,
            gdpr_consent=True,
            captcha_token="token"
        )

def test_model_validation_consents_false():
    with pytest.raises(ValueError, match="Privacy and GDPR consents are required"):
        PublicAccessRequestCreate(
            product=AccessRequestProduct.DATA_LAB,
            source=AccessRequestSource.NEXUS_MANUAL,
            full_name="Test",
            email="test@example.com",
            privacy_accepted=False,
            gdpr_consent=True,
            captcha_token="token"
        )
