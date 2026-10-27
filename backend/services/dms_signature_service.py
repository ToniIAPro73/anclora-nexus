"""DMS Signature Blocking Propagation Service.

Processes SignatureBlockEvent from Advisor AI contract validation and
propagates block/unblock status to the DMS within a 5-second SLA.
All events are logged in audit_log with HMAC-SHA256 signatures per
constitutional requirements (Requirement 12).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from backend.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SLA constant
# ---------------------------------------------------------------------------
PROPAGATION_SLA_SECONDS = 5.0


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class SignatureBlockEvent(BaseModel):
    """Event emitted by the contract validator when a block/unblock decision is made."""

    document_id: str
    block_signing: bool
    reason: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    hmac_signature: str = ""  # HMAC-SHA256 of event payload


class SignatureBlockResult(BaseModel):
    """Result of processing a SignatureBlockEvent."""

    document_id: str
    previous_status: Optional[str]
    new_status: str
    propagation_ms: float
    sla_met: bool
    audit_logged: bool


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class DmsSignatureService:
    """Propagates signature blocking decisions to the DMS.

    Designed to be called from the contract validator service after receiving
    a validation response from Advisor AI. Enforces a 5-second SLA for status
    propagation and logs all events in the audit_log with HMAC-SHA256 integrity.
    """

    def __init__(self, database_client: Any = None, audit_secret: Optional[str] = None) -> None:
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

    async def process_block_event(
        self,
        event: SignatureBlockEvent,
        *,
        org_id: str,
        actor_id: Optional[str] = None,
    ) -> SignatureBlockResult:
        """Process a SignatureBlockEvent and propagate status to the DMS.

        Args:
            event: The block/unblock event from Advisor AI validation.
            org_id: Organization ID for scoping and audit.
            actor_id: The actor triggering the event (user, system, or agent).

        Returns:
            SignatureBlockResult with propagation timing and audit status.
        """
        start_time = time.monotonic()

        # Determine target status
        new_status = "signature_blocked" if event.block_signing else "ready_for_signature"
        block_reason = event.reason if event.block_signing else None
        block_source = "advisor_ai_validation" if event.block_signing else None

        # Fetch current document status
        previous_status = await self._get_current_signature_status(
            document_id=event.document_id, org_id=org_id
        )

        # Update document status in DMS
        await self._update_document_signature_status(
            document_id=event.document_id,
            org_id=org_id,
            signature_status=new_status,
            block_reason=block_reason,
            block_source=block_source,
        )

        # Log in audit_log with HMAC-SHA256
        audit_logged = await self._log_audit_event(
            event=event,
            org_id=org_id,
            actor_id=actor_id or "system",
            new_status=new_status,
            previous_status=previous_status,
        )

        elapsed_ms = (time.monotonic() - start_time) * 1000
        sla_met = elapsed_ms <= (PROPAGATION_SLA_SECONDS * 1000)

        if not sla_met:
            logger.warning(
                "Signature block propagation SLA breached: %.1fms > %.0fms | document=%s",
                elapsed_ms,
                PROPAGATION_SLA_SECONDS * 1000,
                event.document_id,
            )

        logger.info(
            "Signature block event processed: document=%s block=%s status=%s elapsed=%.1fms sla=%s",
            event.document_id,
            event.block_signing,
            new_status,
            elapsed_ms,
            "met" if sla_met else "breached",
        )

        return SignatureBlockResult(
            document_id=event.document_id,
            previous_status=previous_status,
            new_status=new_status,
            propagation_ms=round(elapsed_ms, 2),
            sla_met=sla_met,
            audit_logged=audit_logged,
        )

    # ------------------------------------------------------------------
    # HMAC Signature Generation
    # ------------------------------------------------------------------

    def generate_hmac_signature(self, payload: dict[str, Any]) -> str:
        """Generate HMAC-SHA256 signature for an audit payload.

        Args:
            payload: The data to sign (will be JSON-serialized with sorted keys).

        Returns:
            Hex-encoded HMAC-SHA256 signature string.
        """
        message = json.dumps(payload, sort_keys=True, default=str)
        return hmac.new(
            self._audit_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def verify_event_hmac(self, event: SignatureBlockEvent) -> bool:
        """Verify the HMAC signature on an incoming SignatureBlockEvent.

        Args:
            event: The event with an hmac_signature field to verify.

        Returns:
            True if the signature is valid, False otherwise.
        """
        if not event.hmac_signature:
            return False

        payload = {
            "document_id": event.document_id,
            "block_signing": event.block_signing,
            "reason": event.reason,
            "timestamp": event.timestamp.isoformat(),
        }
        expected = self.generate_hmac_signature(payload)
        return hmac.compare_digest(expected, event.hmac_signature)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_current_signature_status(
        self, *, document_id: str, org_id: str
    ) -> Optional[str]:
        """Fetch the current signature_status of a document."""
        try:
            response = (
                self.client.table("generated_documents")
                .select("signature_status")
                .eq("id", document_id)
                .eq("org_id", org_id)
                .limit(1)
                .execute()
            )
            if response.data:
                return response.data[0].get("signature_status")
            return None
        except Exception as exc:
            logger.error(
                "Failed to fetch signature status: document=%s error=%s",
                document_id,
                exc,
            )
            return None

    async def _update_document_signature_status(
        self,
        *,
        document_id: str,
        org_id: str,
        signature_status: str,
        block_reason: Optional[str],
        block_source: Optional[str],
    ) -> None:
        """Update the document's signature blocking columns."""
        update_data: dict[str, Any] = {
            "signature_status": signature_status,
            "block_reason": block_reason,
            "block_source": block_source,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self.client.table("generated_documents").update(update_data).eq(
                "id", document_id
            ).eq("org_id", org_id).execute()
        except Exception as exc:
            logger.error(
                "Failed to update signature status: document=%s status=%s error=%s",
                document_id,
                signature_status,
                exc,
            )
            raise

    async def _log_audit_event(
        self,
        *,
        event: SignatureBlockEvent,
        org_id: str,
        actor_id: str,
        new_status: str,
        previous_status: Optional[str],
    ) -> bool:
        """Log a block/unblock event in audit_log with HMAC-SHA256 signature."""
        action = "signature_blocked" if event.block_signing else "signature_unblocked"

        audit_payload: dict[str, Any] = {
            "document_id": event.document_id,
            "block_signing": event.block_signing,
            "reason": event.reason,
            "previous_status": previous_status,
            "new_status": new_status,
            "event_timestamp": event.timestamp.isoformat(),
            "source": "advisor_ai_validation",
        }

        hmac_signature = self.generate_hmac_signature(audit_payload)

        audit_entry = {
            "org_id": org_id,
            "actor_type": "system",
            "actor_id": actor_id,
            "action": action,
            "resource_type": "generated_document",
            "resource_id": event.document_id,
            "details": audit_payload,
            "signature": hmac_signature,
        }

        try:
            self.client.table("audit_log").insert(audit_entry).execute()
            return True
        except Exception as exc:
            logger.error(
                "Failed to log audit event: document=%s action=%s error=%s",
                event.document_id,
                action,
                exc,
            )
            return False


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
dms_signature_service = DmsSignatureService()
