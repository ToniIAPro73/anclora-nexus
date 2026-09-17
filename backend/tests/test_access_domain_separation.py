"""
Test suite for domain separation between access_request and commercial_lead in Anclora Intake.

Validates:
1. AccessRequestSource enum only contains access-related sources
2. list_requests always filters to access_request domain
3. Commercial endpoint rejects access sources
4. Domain-to-routing consistency
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from backend.models.access_requests import (
    AccessRequestProduct,
    AccessRequestSource,
    PublicAccessRequestCreate,
)
from backend.services.access_request_service import AccessRequestService
from backend.services.captcha_verification_service import CaptchaVerificationError, CaptchaVerificationService
from backend.config import settings
from backend.api.routes.public import router as public_router


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_supabase_service():
    """Mock Supabase service for testing."""
    with patch("backend.services.access_request_service.supabase_service") as mock:
        yield mock


@pytest.fixture
def mock_captcha():
    """Mock Captcha verification service."""
    with patch("backend.services.access_request_service.captcha_verification_service") as mock:
        yield mock


@pytest.fixture
def mock_supabase_public():
    """Mock Supabase service for public API routes (imported locally inside functions)."""
    with patch("backend.services.supabase_service.supabase_service") as mock:
        yield mock


@pytest.fixture
def mock_captcha_public():
    """Mock Turnstile verification for public commercial lead routes."""
    with patch("backend.api.routes.public.captcha_verification_service") as mock:
        mock.verify.return_value = {
            "provider": "turnstile",
            "verified": True,
            "required": True,
            "hostname": "private-estates.test",
        }
        yield mock


@pytest.fixture
def public_app():
    """FastAPI test app — uses the real main app to respect router registration."""
    from backend.api.main import app as main_app
    return main_app


# ============================================================================
# Group A: AccessRequestSource Enum Tests
# ============================================================================

def test_access_source_has_syncxml_landing():
    """Verify SYNCXML_LANDING is in AccessRequestSource enum."""
    assert hasattr(AccessRequestSource, "SYNCXML_LANDING")
    assert AccessRequestSource.SYNCXML_LANDING.value == "syncxml_landing"


def test_access_source_has_synergi_app():
    """Verify SYNERGI_APP is in AccessRequestSource enum."""
    assert hasattr(AccessRequestSource, "SYNERGI_APP")
    assert AccessRequestSource.SYNERGI_APP.value == "synergi_app"


def test_access_source_has_data_lab_app():
    """Verify DATA_LAB_APP is in AccessRequestSource enum."""
    assert hasattr(AccessRequestSource, "DATA_LAB_APP")
    assert AccessRequestSource.DATA_LAB_APP.value == "data_lab_app"


def test_access_source_has_nexus_manual_and_external_api():
    """Verify NEXUS_MANUAL and EXTERNAL_API are in AccessRequestSource enum."""
    assert hasattr(AccessRequestSource, "NEXUS_MANUAL")
    assert AccessRequestSource.NEXUS_MANUAL.value == "nexus_manual"
    assert hasattr(AccessRequestSource, "EXTERNAL_API")
    assert AccessRequestSource.EXTERNAL_API.value == "external_api"


def test_access_source_has_canonical_sources():
    """Verify canonical sources from taxonomy are in AccessRequestSource enum."""
    assert AccessRequestSource.PRIVATE_ESTATES_LANDING.value == "private_estates_landing"
    assert AccessRequestSource.PRIVATE_ESTATES_WEB.value == "private_estates_web"
    assert AccessRequestSource.GUESTHUB_APP.value == "guesthub_app"

def test_access_source_no_uncatalogued_values():
    """Verify uncatalogued/invalid sources are NOT in AccessRequestSource."""
    invalid_sources = ["landing", "invalid_crm", "unknown_source"]

    for invalid_source in invalid_sources:
        with pytest.raises(ValueError):
            # Attempt to create enum from string value should fail
            AccessRequestSource(invalid_source)


# ============================================================================
# Group B: list_requests Domain Filter Tests
# ============================================================================

@pytest.mark.anyio
async def test_list_requests_defaults_to_access_domain(mock_supabase_service):
    """When called without intake_domain, list_requests filters to access_request domain."""
    # Setup
    mock_query = MagicMock()
    mock_supabase_service.client.table.return_value.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.execute.return_value.data = []

    service = AccessRequestService()

    # Execute: call without intake_domain
    await service.list_requests(org_id="test-org")

    # Assert: should apply intake_domain='access_request' filter
    calls = [str(call) for call in mock_query.eq.call_args_list]
    # Find the call with intake_domain filter
    domain_filter_found = any(
        "intake_domain" in str(call) and "access_request" in str(call)
        for call in calls
    )
    assert domain_filter_found, "Expected intake_domain='access_request' filter"


@pytest.mark.anyio
async def test_list_requests_explicit_access_domain(mock_supabase_service):
    """When intake_domain='access_request' is explicit, filter is applied correctly."""
    # Setup
    mock_query = MagicMock()
    mock_supabase_service.client.table.return_value.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.execute.return_value.data = []

    service = AccessRequestService()

    # Execute: call with explicit intake_domain='access_request'
    await service.list_requests(org_id="test-org", intake_domain="access_request")

    # Assert
    calls = [str(call) for call in mock_query.eq.call_args_list]
    domain_filter_found = any(
        "intake_domain" in str(call) and "access_request" in str(call)
        for call in calls
    )
    assert domain_filter_found, "Expected intake_domain='access_request' filter"


@pytest.mark.anyio
async def test_list_requests_respects_intake_domain_parameter(mock_supabase_service):
    """Verify that when intake_domain is provided, it's used in the filter."""
    # Setup
    mock_query = MagicMock()
    mock_supabase_service.client.table.return_value.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.execute.return_value.data = []

    service = AccessRequestService()

    # Execute with different domain (test that parameter is respected)
    await service.list_requests(org_id="test-org", intake_domain="commercial_lead")

    # Assert: commercial_lead filter should be applied
    calls = [str(call) for call in mock_query.eq.call_args_list]
    domain_filter_found = any(
        "intake_domain" in str(call) and "commercial_lead" in str(call)
        for call in calls
    )
    assert domain_filter_found, "Expected intake_domain='commercial_lead' filter when explicitly provided"


# ============================================================================
# Group C: Commercial Endpoint Source Validation Tests
# ============================================================================

@pytest.mark.anyio
async def test_commercial_endpoint_rejects_syncxml_source(public_app, mock_supabase_public):
    """POST /api/public/intake/commercial-leads rejects source='syncxml_landing'."""
    async with AsyncClient(transport=ASGITransport(app=public_app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/public/intake/commercial-leads",
            json={
                "intake_domain": "commercial_lead",
                "source": "syncxml_landing",  # Invalid source for commercial endpoint
                "applicant": {"email": "test@example.com"},
                "request_type": "seller_valuation_request"
            }
        )

    assert response.status_code == 422
    assert "source" in response.text.lower()


@pytest.mark.anyio
async def test_commercial_endpoint_rejects_synergi_source(public_app, mock_supabase_public):
    """POST /api/public/intake/commercial-leads rejects source='synergi_app'."""
    async with AsyncClient(transport=ASGITransport(app=public_app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/public/intake/commercial-leads",
            json={
                "intake_domain": "commercial_lead",
                "source": "synergi_app",  # Invalid source for commercial endpoint
                "applicant": {"email": "test@example.com"},
                "request_type": "seller_valuation_request"
            }
        )

    assert response.status_code == 422
    assert "source" in response.text.lower()


@pytest.mark.anyio
async def test_private_estates_commercial_endpoint_requires_turnstile(public_app, mock_supabase_public):
    """Private Estates leads fail closed when Turnstile metadata is absent."""
    async with AsyncClient(transport=ASGITransport(app=public_app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/public/intake/commercial-leads",
            json={
                "intake_domain": "commercial_lead",
                "source": "private_estates_web",
                "applicant": {"email": "test@example.com"},
            },
        )

    assert response.status_code == 400
    assert "turnstile" in response.text.lower()
    mock_supabase_public.client.table.assert_not_called()


@pytest.mark.anyio
async def test_private_estates_commercial_endpoint_rejects_invalid_turnstile(
    public_app, mock_supabase_public, mock_captcha_public
):
    """A failed Turnstile result prevents commercial lead persistence."""
    mock_captcha_public.verify.return_value = {
        "provider": "turnstile",
        "verified": False,
        "required": True,
    }

    async with AsyncClient(transport=ASGITransport(app=public_app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/public/intake/commercial-leads",
            json={
                "intake_domain": "commercial_lead",
                "source": "private_estates_web",
                "applicant": {"email": "test@example.com"},
                "captcha_provider": "turnstile",
                "captcha_token": "invalid-token",
            },
        )

    assert response.status_code == 400
    mock_supabase_public.client.table.assert_not_called()


@pytest.mark.anyio
async def test_private_estates_commercial_endpoint_rejects_verification_error(
    public_app, mock_supabase_public, mock_captcha_public
):
    mock_captcha_public.verify.side_effect = CaptchaVerificationError("invalid")

    async with AsyncClient(transport=ASGITransport(app=public_app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/public/intake/commercial-leads",
            json={
                "intake_domain": "commercial_lead",
                "source": "private_estates_web",
                "applicant": {"email": "test@example.com"},
                "captcha_provider": "turnstile",
                "captcha_token": "invalid-token",
            },
        )

    assert response.status_code == 400
    mock_supabase_public.client.table.assert_not_called()


@pytest.mark.parametrize("hostname", ["other.anclora.com", None])
def test_turnstile_rejects_hostname_outside_private_estates_allowlist(hostname):
    service = CaptchaVerificationService()
    response = MagicMock()
    response.read.return_value = (
        '{"success": true, "action": "private_estates_contact", '
        + (f'"hostname": "{hostname}"' if hostname else '"hostname": null')
        + "}"
    ).encode()
    response.__enter__.return_value = response

    with patch.object(settings, "TURNSTILE_SECRET_KEY", "configured"):
        with patch("backend.services.captcha_verification_service.urlopen", return_value=response):
            with pytest.raises(CaptchaVerificationError, match="hostname mismatch"):
                service.verify(
                    provider="turnstile",
                    token="runtime-token",
                    expected_action="private_estates_contact",
                    expected_hostnames=["private-estates.anclora.com"],
                )


@pytest.mark.anyio
async def test_private_estates_commercial_endpoint_persists_verified_metadata(
    public_app, mock_supabase_public, mock_captcha_public
):
    """A verified Turnstile result is recorded without persisting the token."""
    mock_query = MagicMock()
    mock_supabase_public.client.table.return_value = mock_query
    mock_query.insert.return_value = mock_query
    mock_query.execute.return_value.data = [{"id": "lead-verified"}]

    async with AsyncClient(transport=ASGITransport(app=public_app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/public/intake/commercial-leads",
            json={
                "intake_domain": "commercial_lead",
                "source": "private_estates_web",
                "applicant": {"email": "test@example.com"},
                "captcha_provider": "turnstile",
                "captcha_token": "verified-token",
            },
        )

    assert response.status_code == 202
    persisted = mock_query.insert.call_args.args[0]
    assert persisted["context"]["captcha_provider"] == "turnstile"
    assert persisted["context"]["captcha_verified"] is True
    assert "verified-token" not in str(persisted)
    mock_captcha_public.verify.assert_called_once_with(
        provider="turnstile",
        token="verified-token",
        remote_ip="127.0.0.1",
        expected_action="private_estates_contact",
        expected_hostnames=["private-estates.anclora.com"],
    )


@pytest.mark.anyio
async def test_commercial_endpoint_accepts_private_estates_landing(public_app, mock_supabase_public, mock_captcha_public):
    """POST /api/public/intake/commercial-leads accepts source='private_estates_landing'."""
    # Setup mock to simulate successful insert
    mock_query = MagicMock()
    mock_supabase_public.client.table.return_value = mock_query
    mock_query.insert.return_value = mock_query
    mock_query.execute.return_value.data = [{"id": "lead-123"}]

    async with AsyncClient(transport=ASGITransport(app=public_app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/public/intake/commercial-leads",
            json={
                "intake_domain": "commercial_lead",
                "source": "private_estates_landing",  # Valid source
                "applicant": {"email": "test@example.com"},
                "request_type": "seller_valuation_request",
                "captcha_provider": "turnstile",
                "captcha_token": "test-token",
            }
        )

    # Should be accepted with 202
    assert response.status_code == 202
    assert response.json().get("status") == "accepted"


# ============================================================================
# Group D: Domain-to-Routing Coherence Tests
# ============================================================================

@pytest.mark.anyio
async def test_commercial_lead_cannot_have_target_product(public_app):
    """If intake_domain='commercial_lead' and target_product is provided, validation fails."""
    async with AsyncClient(transport=ASGITransport(app=public_app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/public/intake/commercial-leads",
            json={
                "intake_domain": "commercial_lead",
                "source": "private_estates_landing",
                "target_product": "syncxml",  # Should not be allowed for commercial
                "applicant": {"email": "test@example.com"},
                "request_type": "seller_valuation_request"
            }
        )

    assert response.status_code == 422
    assert "target_product" in response.text.lower()


@pytest.mark.anyio
async def test_access_request_requires_intake_domain(mock_supabase_service, mock_captcha):
    """Access requests created via service have intake_domain='access_request'."""
    # Setup
    mock_captcha.verify.return_value = {"verified": True, "hostname": "test.com", "required": True}
    mock_supabase_service.client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "request-1", "status": "pending", "product": "synergi", "email": "test@example.com"}
    ]

    service = AccessRequestService()
    data = PublicAccessRequestCreate(
        product=AccessRequestProduct.SYNERGI,
        source=AccessRequestSource.NEXUS_MANUAL,
        full_name="Test User",
        email="test@example.com",
        service_category="agent",
        service_summary="test",
        privacy_accepted=True,
        gdpr_consent=True,
        captcha_token="token"
    )

    # Execute
    await service.create_public_request(data)

    # Assert: domain and routing are set
    args, kwargs = mock_supabase_service.client.table.return_value.insert.call_args
    persistence_data = args[0]
    assert persistence_data.get("intake_domain") == "access_request"
    assert persistence_data.get("routing_target_domain") == "access_requests"


@pytest.mark.anyio
async def test_pe_source_can_create_access_request(mock_supabase_service, mock_captcha):
    """source='private_estates_landing' with intake_domain='access_request' succeeds."""
    mock_captcha.verify.return_value = {"verified": True, "hostname": "test.com", "required": True}
    mock_supabase_service.client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "request-pe-1", "status": "pending", "product": "data_lab", "email": "test@example.com"}
    ]
    service = AccessRequestService()
    data = PublicAccessRequestCreate(
        product=AccessRequestProduct.DATA_LAB,
        source=AccessRequestSource.PRIVATE_ESTATES_LANDING,
        full_name="PE Visitor",
        email="visitor@example.com",
        intended_use="Market analysis",
        privacy_accepted=True,
        gdpr_consent=True,
        captcha_token="token"
    )
    result = await service.create_public_request(data)
    assert result["status"] == "pending"
    assert result["product"] == "data_lab"


# ============================================================================
# Group E: Domain-to-Routing Target Tests
# ============================================================================

@pytest.mark.anyio
async def test_access_domain_routes_to_access_requests_table(mock_supabase_service, mock_captcha):
    """intake_domain='access_request' routes to access_requests table."""
    # Setup
    mock_captcha.verify.return_value = {"verified": True, "hostname": "test.com", "required": True}
    mock_supabase_service.client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "request-1", "status": "pending", "product": "synergi", "email": "test@example.com"}
    ]

    service = AccessRequestService()
    data = PublicAccessRequestCreate(
        product=AccessRequestProduct.SYNERGI,
        source=AccessRequestSource.NEXUS_MANUAL,
        full_name="Test User",
        email="test@example.com",
        service_category="agent",
        service_summary="test",
        privacy_accepted=True,
        gdpr_consent=True,
        captcha_token="token"
    )

    # Execute
    await service.create_public_request(data)

    # Assert: table called should be 'access_requests'
    mock_supabase_service.client.table.assert_called()
    table_call = mock_supabase_service.client.table.call_args[0][0]
    assert table_call == "access_requests"


@pytest.mark.anyio
async def test_commercial_domain_routes_to_leads_or_valuations(public_app, mock_supabase_public, mock_captcha_public):
    """intake_domain='commercial_lead' routes to either valuation_requests or leads_pipeline."""
    # Setup mock
    mock_query = MagicMock()
    mock_supabase_public.client.table.return_value = mock_query
    mock_query.insert.return_value = mock_query
    mock_query.execute.return_value.data = [{"id": "lead-123"}]

    async with AsyncClient(transport=ASGITransport(app=public_app), base_url="http://test") as ac:
        # Test with seller_valuation_request (should route to valuation_requests)
        response = await ac.post(
            "/api/public/intake/commercial-leads",
            json={
                "intake_domain": "commercial_lead",
                "source": "private_estates_landing",
                "applicant": {"email": "test@example.com"},
                "request_type": "seller_valuation_request",
                "captcha_provider": "turnstile",
                "captcha_token": "test-token",
            }
        )

    assert response.status_code == 202
    result = response.json()
    assert result.get("routing") == "valuation_requests", "Valuation requests should route to valuation_requests table"
    # Verify table() was called with valuation_requests
    mock_supabase_public.client.table.assert_called()
    table_calls = [call[0][0] for call in mock_supabase_public.client.table.call_args_list]
    assert "valuation_requests" in table_calls


@pytest.mark.anyio
async def test_commercial_domain_routes_to_leads_pipeline_for_generic_request(public_app, mock_supabase_public, mock_captcha_public):
    """intake_domain='commercial_lead' without seller_valuation_request routes to leads_pipeline."""
    # Setup mock
    mock_query = MagicMock()
    mock_supabase_public.client.table.return_value = mock_query
    mock_query.insert.return_value = mock_query
    mock_query.execute.return_value.data = [{"id": "lead-456"}]

    async with AsyncClient(transport=ASGITransport(app=public_app), base_url="http://test") as ac:
        # Test with generic request type (should route to leads_pipeline)
        response = await ac.post(
            "/api/public/intake/commercial-leads",
            json={
                "intake_domain": "commercial_lead",
                "source": "private_estates_landing",
                "applicant": {"email": "test@example.com"},
                "request_type": "general_inquiry",
                "captcha_provider": "turnstile",
                "captcha_token": "test-token",
            }
        )

    assert response.status_code == 202
    result = response.json()
    assert result.get("routing") == "leads_pipeline", "Generic requests should route to leads_pipeline table"
    # Verify table() was called with leads_pipeline
    mock_supabase_public.client.table.assert_called()
    table_calls = [call[0][0] for call in mock_supabase_public.client.table.call_args_list]
    assert "leads_pipeline" in table_calls
