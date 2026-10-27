"""Unit tests for the Exclusiva Webhook Dispatcher Service.

Validates Requirements 15.1 (webhook dispatch on Exclusiva status) and
15.4 (exponential backoff retry with max 3 over 1 hour).
"""

import os
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock


import httpx
import pytest

from backend.services.webhook_dispatcher import (
    WebhookDispatcherService,
    PropertyWebhookPayload,
    LocationInfo,
    WebhookDeliveryResult,
    _MAX_RETRIES,
    _INITIAL_BACKOFF_SECONDS,
    _BACKOFF_MULTIPLIER,
)


# ---------------------------------------------------------------------------
# Fake Neon client for audit_log
# ---------------------------------------------------------------------------


class FakeExecuteResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeAuditQuery:
    def __init__(self, tracker):
        self._tracker = tracker

    def insert(self, data):
        self._tracker.append(data)
        return self

    def execute(self):
        return FakeExecuteResult([{"id": "audit-1"}])


class FakeClient:
    def __init__(self):
        self.inserted_audits = []

    def table(self, name):
        if name == "audit_log":
            return FakeAuditQuery(self.inserted_audits)
        return FakeAuditQuery([])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(
    webhook_url="https://content-gen.example.com/api/webhooks/property",
    webhook_secret="test-webhook-secret-12345",
):
    client = FakeClient()
    service = WebhookDispatcherService(
        webhook_url=webhook_url,
        webhook_secret=webhook_secret,
        database_client=client,
        audit_secret="test-audit-secret-key-12345",
    )
    return service, client


def _make_location():
    return LocationInfo(
        address="Calle Test 1",
        municipality="Palma",
        province="Illes Balears",
        country="España",
        lat=39.5696,
        lng=2.6502,
        postal_code="07001",
    )


# ---------------------------------------------------------------------------
# Tests: HMAC Signature Generation
# ---------------------------------------------------------------------------


def test_payload_signature_is_deterministic():
    service, _ = _make_service()
    payload = PropertyWebhookPayload(
        property_id="prop-1",
        description="Villa de lujo en Palma",
        media_urls=["https://example.com/img1.jpg"],
        location=_make_location(),
        features={"bedrooms": 5, "pool": True},
        timestamp=datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
    )

    sig1 = service.generate_payload_signature(payload)
    sig2 = service.generate_payload_signature(payload)

    assert sig1 == sig2
    assert len(sig1) == 64  # SHA-256 hex


def test_payload_signature_changes_with_different_property():
    service, _ = _make_service()
    payload_a = PropertyWebhookPayload(
        property_id="prop-1",
        description="Test",
        location=_make_location(),
    )
    payload_b = PropertyWebhookPayload(
        property_id="prop-2",
        description="Test",
        location=_make_location(),
        timestamp=payload_a.timestamp,
    )

    sig_a = service.generate_payload_signature(payload_a)
    sig_b = service.generate_payload_signature(payload_b)

    assert sig_a != sig_b


def test_payload_signature_changes_with_different_secret():
    service_a, _ = _make_service(webhook_secret="secret-A")
    service_b, _ = _make_service(webhook_secret="secret-B")

    payload = PropertyWebhookPayload(
        property_id="prop-1",
        description="Test",
        location=_make_location(),
        timestamp=datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
    )

    sig_a = service_a.generate_payload_signature(payload)
    sig_b = service_b.generate_payload_signature(payload)

    assert sig_a != sig_b


def test_verify_payload_signature_valid():
    service, _ = _make_service()
    payload = PropertyWebhookPayload(
        property_id="prop-verify",
        description="Verification test",
        location=_make_location(),
        timestamp=datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
    )
    payload.signature = service.generate_payload_signature(payload)

    assert service.verify_payload_signature(payload) is True


def test_verify_payload_signature_invalid():
    service, _ = _make_service()
    payload = PropertyWebhookPayload(
        property_id="prop-verify",
        description="Verification test",
        location=_make_location(),
        signature="invalid-signature",
    )

    assert service.verify_payload_signature(payload) is False


def test_verify_payload_signature_empty():
    service, _ = _make_service()
    payload = PropertyWebhookPayload(
        property_id="prop-verify",
        description="Test",
        location=_make_location(),
        signature="",
    )

    assert service.verify_payload_signature(payload) is False


# ---------------------------------------------------------------------------
# Tests: Successful Delivery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_successful_delivery():
    service, client = _make_service()

    with patch.object(service, "_send_webhook", new_callable=AsyncMock, return_value=200):
        result = await service.dispatch_exclusiva_webhook(
            property_id="prop-ok",
            description="Beautiful villa",
            media_urls=["https://example.com/img.jpg"],
            location=_make_location(),
            features={"bedrooms": 3},
            org_id="org-1",
        )

    assert result.delivered is True
    assert result.status_code == 200
    assert result.attempts == 1
    assert result.error is None
    # No audit_log entry on success
    assert len(client.inserted_audits) == 0


@pytest.mark.asyncio
async def test_dispatch_successful_on_second_attempt():
    service, client = _make_service()

    call_count = 0

    async def mock_send(*, payload_json):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.ConnectError("Connection refused")
        return 200

    with patch.object(service, "_send_webhook", side_effect=mock_send):
        with patch("backend.services.webhook_dispatcher.asyncio.sleep", new_callable=AsyncMock):
            result = await service.dispatch_exclusiva_webhook(
                property_id="prop-retry-ok",
                description="Villa with retry",
                media_urls=[],
                location=_make_location(),
                features={},
                org_id="org-1",
            )

    assert result.delivered is True
    assert result.attempts == 2
    assert len(client.inserted_audits) == 0


# ---------------------------------------------------------------------------
# Tests: Failed Delivery with Retries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_all_retries_exhausted():
    service, client = _make_service()

    with patch.object(
        service, "_send_webhook", new_callable=AsyncMock, side_effect=httpx.TimeoutException("timeout")
    ):
        with patch("backend.services.webhook_dispatcher.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await service.dispatch_exclusiva_webhook(
                property_id="prop-fail",
                description="Failing villa",
                media_urls=[],
                location=_make_location(),
                features={},
                org_id="org-1",
            )

    assert result.delivered is False
    assert result.attempts == _MAX_RETRIES
    assert "TimeoutException" in result.error

    # Verify exponential backoff sleep calls
    assert mock_sleep.call_count == _MAX_RETRIES - 1
    sleep_args = [call.args[0] for call in mock_sleep.call_args_list]
    assert sleep_args[0] == _INITIAL_BACKOFF_SECONDS  # 60s
    assert sleep_args[1] == _INITIAL_BACKOFF_SECONDS * _BACKOFF_MULTIPLIER  # 240s


@pytest.mark.asyncio
async def test_dispatch_failure_logs_in_audit_log():
    service, client = _make_service()

    with patch.object(
        service, "_send_webhook", new_callable=AsyncMock, return_value=500
    ):
        with patch("backend.services.webhook_dispatcher.asyncio.sleep", new_callable=AsyncMock):
            result = await service.dispatch_exclusiva_webhook(
                property_id="prop-audit",
                description="Audit logging test",
                media_urls=[],
                location=_make_location(),
                features={},
                org_id="org-audit",
            )

    assert result.delivered is False
    assert len(client.inserted_audits) == 1

    audit = client.inserted_audits[0]
    assert audit["org_id"] == "org-audit"
    assert audit["actor_type"] == "system"
    assert audit["actor_id"] == "webhook_dispatcher"
    assert audit["action"] == "exclusiva_webhook_failed"
    assert audit["resource_type"] == "property"
    assert audit["resource_id"] == "prop-audit"
    assert "signature" in audit
    assert len(audit["signature"]) == 64  # HMAC-SHA256 hex

    details = audit["details"]
    assert details["property_id"] == "prop-audit"
    assert details["event_type"] == "exclusiva_webhook_delivery_failed"
    assert details["attempts"] == _MAX_RETRIES
    assert details["max_retries"] == _MAX_RETRIES


@pytest.mark.asyncio
async def test_dispatch_non_2xx_treated_as_failure():
    service, client = _make_service()

    with patch.object(service, "_send_webhook", new_callable=AsyncMock, return_value=403):
        with patch("backend.services.webhook_dispatcher.asyncio.sleep", new_callable=AsyncMock):
            result = await service.dispatch_exclusiva_webhook(
                property_id="prop-403",
                description="Forbidden response",
                media_urls=[],
                location=_make_location(),
                features={},
                org_id="org-1",
            )

    assert result.delivered is False
    assert result.status_code == 403
    assert result.error == "HTTP 403"


# ---------------------------------------------------------------------------
# Tests: Configuration Errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_without_webhook_url():
    service, client = _make_service(webhook_url=None)

    result = await service.dispatch_exclusiva_webhook(
        property_id="prop-nourl",
        description="No URL configured",
        media_urls=[],
        location=_make_location(),
        features={},
        org_id="org-1",
    )

    assert result.delivered is False
    assert result.error == "Webhook URL not configured"
    # Failure is logged in audit
    assert len(client.inserted_audits) == 1


@pytest.mark.asyncio
async def test_dispatch_without_webhook_secret():
    service, client = _make_service(webhook_secret=None)

    result = await service.dispatch_exclusiva_webhook(
        property_id="prop-nosecret",
        description="No secret configured",
        media_urls=[],
        location=_make_location(),
        features={},
        org_id="org-1",
    )

    assert result.delivered is False
    assert result.error == "Webhook secret not configured"
    assert len(client.inserted_audits) == 1


# ---------------------------------------------------------------------------
# Tests: Payload Structure
# ---------------------------------------------------------------------------


def test_payload_event_type_is_exclusiva_created():
    payload = PropertyWebhookPayload(
        property_id="prop-1",
        description="Test",
        location=_make_location(),
    )
    assert payload.event_type == "exclusiva_created"


def test_payload_model_dump_includes_all_fields():
    location = _make_location()
    payload = PropertyWebhookPayload(
        property_id="prop-dump",
        description="Dump test",
        media_urls=["https://example.com/a.jpg", "https://example.com/b.jpg"],
        location=location,
        features={"pool": True, "bedrooms": 4},
        timestamp=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )

    data = payload.model_dump(mode="json")

    assert data["property_id"] == "prop-dump"
    assert data["description"] == "Dump test"
    assert len(data["media_urls"]) == 2
    assert data["location"]["municipality"] == "Palma"
    assert data["features"]["pool"] is True
    assert data["event_type"] == "exclusiva_created"
    assert "timestamp" in data
    assert "signature" in data


# ---------------------------------------------------------------------------
# Tests: Backoff Timing
# ---------------------------------------------------------------------------


def test_backoff_fits_within_one_hour():
    """Verify the total max wait time fits within 1 hour (3600s)."""
    total_wait = 0.0
    backoff = _INITIAL_BACKOFF_SECONDS
    for _ in range(_MAX_RETRIES - 1):
        total_wait += backoff
        backoff *= _BACKOFF_MULTIPLIER

    # 60 + 240 = 300s wait time between retries
    # Plus ~30s timeout per request × 3 = 90s max execution time
    # Total: ~390s well within 3600s
    assert total_wait < 3600, f"Total backoff {total_wait}s exceeds 1 hour"
