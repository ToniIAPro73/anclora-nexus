"""Exclusiva Webhook Dispatcher Service.

Sends signed webhook POST to Content Generator AI when a property
reaches the "Exclusiva" status in Nexus. Implements exponential backoff
retry (max 3 retries over 1 hour) on delivery failure and logs failures
in audit_log per constitutional requirements.

Requirements: 15.1, 15.4
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Literal, Optional

import httpx
from pydantic import BaseModel, Field

from backend.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Retry configuration (Requirement 15.4)
# Max 3 retries over 1 hour: delays of 60s, 240s, 960s (exponential × 4)
# ---------------------------------------------------------------------------

_MAX_RETRIES = 3
_INITIAL_BACKOFF_SECONDS = 60.0
_BACKOFF_MULTIPLIER = 4.0  # 60s, 240s, 960s ≈ 1260s total < 3600s (1 hour)
_WEBHOOK_TIMEOUT_SECONDS = 30.0


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class LocationInfo(BaseModel):
    """Geographic location information for a property."""

    address: Optional[str] = None
    municipality: Optional[str] = None
    province: Optional[str] = None
    country: str = "España"
    lat: Optional[float] = None
    lng: Optional[float] = None
    postal_code: Optional[str] = None


class PropertyWebhookPayload(BaseModel):
    """Payload sent to Content Generator AI when a property reaches Exclusiva status.

    The signature field contains the HMAC-SHA256 of the payload body
    (excluding the signature field itself) using the shared webhook secret.
    """

    property_id: str
    description: str
    media_urls: list[str] = Field(default_factory=list)
    location: LocationInfo
    features: dict[str, Any] = Field(default_factory=dict)
    event_type: Literal["exclusiva_created"] = "exclusiva_created"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    signature: str = ""


class WebhookDeliveryResult(BaseModel):
    """Result of a webhook dispatch attempt."""

    property_id: str
    delivered: bool
    status_code: Optional[int] = None
    attempts: int = 0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class WebhookDispatcherService:
    """Dispatches signed webhooks to Content Generator AI on Exclusiva events.

    Uses HMAC-SHA256 signature for payload integrity verification.
    Retries with exponential backoff on delivery failure (max 3 retries over 1h).
    Logs all delivery failures in audit_log.
    """

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        database_client: Any = None,
        audit_secret: Optional[str] = None,
    ) -> None:
        self._webhook_url = webhook_url or getattr(settings, "CONTENT_GENERATOR_WEBHOOK_URL", None)
        self._webhook_secret = webhook_secret or getattr(settings, "WEBHOOK_SHARED_SECRET", None)
        self._client = database_client
        self._audit_secret = (
            audit_secret
            or settings.INTERNAL_AUDIT_SECRET
        )

    @property
    def client(self) -> Any:
        """Lazy-load Neon client from the shared service if not injected."""
        if self._client is None:
            from backend.services.neon_service import neon_service
            self._client = neon_service.client
        return self._client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def dispatch_exclusiva_webhook(
        self,
        *,
        property_id: str,
        description: str,
        media_urls: list[str],
        location: LocationInfo,
        features: dict[str, Any],
        org_id: str,
    ) -> WebhookDeliveryResult:
        """Dispatch webhook when a property status changes to Exclusiva.

        Builds the payload, signs it with HMAC-SHA256, and sends a POST
        to Content Generator AI. Retries with exponential backoff on failure.

        Args:
            property_id: Unique property identifier.
            description: Property description for content generation.
            media_urls: List of media asset URLs.
            location: Property geographic location.
            features: Property features dict.
            org_id: Organization ID for scoping and audit.

        Returns:
            WebhookDeliveryResult with delivery status and attempt count.
        """
        if not self._webhook_url:
            logger.error("CONTENT_GENERATOR_WEBHOOK_URL not configured; cannot dispatch webhook.")
            await self._log_failure(
                property_id=property_id,
                org_id=org_id,
                error="CONTENT_GENERATOR_WEBHOOK_URL not configured",
                attempts=0,
            )
            return WebhookDeliveryResult(
                property_id=property_id,
                delivered=False,
                attempts=0,
                error="Webhook URL not configured",
            )

        if not self._webhook_secret:
            logger.error("WEBHOOK_SHARED_SECRET not configured; cannot sign webhook payload.")
            await self._log_failure(
                property_id=property_id,
                org_id=org_id,
                error="WEBHOOK_SHARED_SECRET not configured",
                attempts=0,
            )
            return WebhookDeliveryResult(
                property_id=property_id,
                delivered=False,
                attempts=0,
                error="Webhook secret not configured",
            )

        # Build payload
        payload = PropertyWebhookPayload(
            property_id=property_id,
            description=description,
            media_urls=media_urls,
            location=location,
            features=features,
        )

        # Sign payload
        payload.signature = self.generate_payload_signature(payload)

        # Attempt delivery with retries
        result = await self._deliver_with_retry(payload=payload, org_id=org_id)
        return result

    # ------------------------------------------------------------------
    # HMAC Signature
    # ------------------------------------------------------------------

    def generate_payload_signature(self, payload: PropertyWebhookPayload) -> str:
        """Generate HMAC-SHA256 signature for the webhook payload.

        Signs all payload fields except the signature field itself.

        Args:
            payload: The webhook payload to sign.

        Returns:
            Hex-encoded HMAC-SHA256 signature string.
        """
        signable_data = payload.model_dump(exclude={"signature"}, mode="json")
        message = json.dumps(signable_data, sort_keys=True, default=str)
        return hmac.new(
            self._webhook_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def verify_payload_signature(self, payload: PropertyWebhookPayload) -> bool:
        """Verify the HMAC-SHA256 signature on a webhook payload.

        Args:
            payload: The payload with a signature field to verify.

        Returns:
            True if the signature is valid, False otherwise.
        """
        if not payload.signature:
            return False
        expected = self.generate_payload_signature(payload)
        return hmac.compare_digest(expected, payload.signature)

    # ------------------------------------------------------------------
    # Retry Logic
    # ------------------------------------------------------------------

    async def _deliver_with_retry(
        self,
        *,
        payload: PropertyWebhookPayload,
        org_id: str,
    ) -> WebhookDeliveryResult:
        """Deliver webhook with exponential backoff retry.

        Retries up to 3 times with delays of 60s, 240s, 960s.
        Logs failures in audit_log after all retries are exhausted.
        """
        last_error: Optional[str] = None
        last_status_code: Optional[int] = None
        backoff = _INITIAL_BACKOFF_SECONDS

        payload_json = payload.model_dump(mode="json")

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                status_code = await self._send_webhook(payload_json=payload_json)
                last_status_code = status_code

                if 200 <= status_code < 300:
                    logger.info(
                        "Webhook delivered successfully: property=%s attempt=%d/%d status=%d",
                        payload.property_id,
                        attempt,
                        _MAX_RETRIES,
                        status_code,
                    )
                    return WebhookDeliveryResult(
                        property_id=payload.property_id,
                        delivered=True,
                        status_code=status_code,
                        attempts=attempt,
                    )

                # Non-2xx response — treat as failure
                last_error = f"HTTP {status_code}"
                logger.warning(
                    "Webhook delivery failed: property=%s attempt=%d/%d status=%d",
                    payload.property_id,
                    attempt,
                    _MAX_RETRIES,
                    status_code,
                )

            except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "Webhook delivery error: property=%s attempt=%d/%d error=%s",
                    payload.property_id,
                    attempt,
                    _MAX_RETRIES,
                    exc,
                )

            # Wait before next retry (unless this was the last attempt)
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(backoff)
                backoff *= _BACKOFF_MULTIPLIER

        # All retries exhausted — log failure in audit_log
        await self._log_failure(
            property_id=payload.property_id,
            org_id=org_id,
            error=last_error or "Unknown error after retries",
            attempts=_MAX_RETRIES,
        )

        return WebhookDeliveryResult(
            property_id=payload.property_id,
            delivered=False,
            status_code=last_status_code,
            attempts=_MAX_RETRIES,
            error=last_error,
        )

    async def _send_webhook(self, *, payload_json: dict[str, Any]) -> int:
        """Send a single webhook POST request.

        Args:
            payload_json: Serialized payload dict.

        Returns:
            HTTP status code from the response.
        """
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": payload_json.get("signature", ""),
            "X-Webhook-Event": "exclusiva_created",
        }

        async with httpx.AsyncClient(timeout=_WEBHOOK_TIMEOUT_SECONDS) as client:
            response = await client.post(
                self._webhook_url,
                json=payload_json,
                headers=headers,
            )

        return response.status_code

    # ------------------------------------------------------------------
    # Audit Logging
    # ------------------------------------------------------------------

    async def _log_failure(
        self,
        *,
        property_id: str,
        org_id: str,
        error: str,
        attempts: int,
    ) -> None:
        """Log webhook delivery failure in audit_log with HMAC-SHA256 signature.

        Per constitutional requirements, all significant system events
        are logged in audit_log with integrity signatures.
        """
        audit_payload: dict[str, Any] = {
            "property_id": property_id,
            "event_type": "exclusiva_webhook_delivery_failed",
            "error": error,
            "attempts": attempts,
            "max_retries": _MAX_RETRIES,
            "webhook_url": self._webhook_url or "not_configured",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        hmac_signature = self._generate_audit_signature(audit_payload)

        audit_entry: dict[str, Any] = {
            "org_id": org_id,
            "actor_type": "system",
            "actor_id": "webhook_dispatcher",
            "action": "exclusiva_webhook_failed",
            "resource_type": "property",
            "resource_id": property_id,
            "details": audit_payload,
            "signature": hmac_signature,
        }

        try:
            self.client.table("audit_log").insert(audit_entry).execute()
            logger.info(
                "Webhook failure logged in audit_log: property=%s attempts=%d",
                property_id,
                attempts,
            )
        except Exception as exc:
            logger.error(
                "Failed to log webhook failure in audit_log: property=%s error=%s",
                property_id,
                exc,
            )

    def _generate_audit_signature(self, payload: dict[str, Any]) -> str:
        """Generate HMAC-SHA256 signature for an audit payload.

        Args:
            payload: The data to sign (JSON-serialized with sorted keys).

        Returns:
            Hex-encoded HMAC-SHA256 signature string.
        """
        message = json.dumps(payload, sort_keys=True, default=str)
        return hmac.new(
            self._audit_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()


# ---------------------------------------------------------------------------
# Module-level singleton instance
# ---------------------------------------------------------------------------

webhook_dispatcher_service = WebhookDispatcherService()
