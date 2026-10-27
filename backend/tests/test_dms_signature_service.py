"""Unit tests for the DMS Signature Blocking Propagation Service."""

import os
import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


from backend.services.dms_signature_service import (
    DmsSignatureService,
    SignatureBlockEvent,
    SignatureBlockResult,
    PROPAGATION_SLA_SECONDS,
)


class FakeExecuteResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeQuery:
    """Chainable mock for Neon query builder."""

    def __init__(self, data=None):
        self._data = data

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def insert(self, data):
        self._inserted = data
        return self

    def update(self, data):
        self._updated = data
        return self

    def execute(self):
        return FakeExecuteResult(self._data)


class FakeClient:
    """Minimal Neon client mock."""

    def __init__(self, document_status="ready_for_signature"):
        self._document_status = document_status
        self.inserted_audits = []
        self.updated_documents = []

    def table(self, name):
        if name == "generated_documents":
            return FakeDocumentQuery(self._document_status, self.updated_documents)
        if name == "audit_log":
            return FakeAuditQuery(self.inserted_audits)
        return FakeQuery()


class FakeDocumentQuery:
    def __init__(self, status, tracker):
        self._status = status
        self._tracker = tracker

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def update(self, data):
        self._tracker.append(data)
        return self

    def execute(self):
        return FakeExecuteResult([{"signature_status": self._status}])


class FakeAuditQuery:
    def __init__(self, tracker):
        self._tracker = tracker

    def insert(self, data):
        self._tracker.append(data)
        return self

    def execute(self):
        return FakeExecuteResult([{"id": "audit-1"}])


def _make_service(document_status="ready_for_signature"):
    client = FakeClient(document_status)
    service = DmsSignatureService(
        database_client=client,
        audit_secret="test-audit-secret-key-12345",
    )
    return service, client


def test_process_block_event_sets_signature_blocked():
    service, client = _make_service(document_status="ready_for_signature")
    event = SignatureBlockEvent(
        document_id="doc-123",
        block_signing=True,
        reason="Legal irregularity detected in clause 4.2",
    )

    result = asyncio.run(service.process_block_event(event, org_id="org-1"))

    assert isinstance(result, SignatureBlockResult)
    assert result.document_id == "doc-123"
    assert result.new_status == "signature_blocked"
    assert result.previous_status == "ready_for_signature"
    assert result.audit_logged is True
    assert result.propagation_ms >= 0

    # Verify document was updated
    assert len(client.updated_documents) == 1
    update = client.updated_documents[0]
    assert update["signature_status"] == "signature_blocked"
    assert update["block_reason"] == "Legal irregularity detected in clause 4.2"
    assert update["block_source"] == "advisor_ai_validation"


def test_process_unblock_event_restores_ready_for_signature():
    service, client = _make_service(document_status="signature_blocked")
    event = SignatureBlockEvent(
        document_id="doc-456",
        block_signing=False,
        reason="Blocking condition resolved",
    )

    result = asyncio.run(service.process_block_event(event, org_id="org-1"))

    assert result.new_status == "ready_for_signature"
    assert result.previous_status == "signature_blocked"
    assert result.audit_logged is True

    # Verify block_reason and block_source are cleared on unblock
    update = client.updated_documents[0]
    assert update["signature_status"] == "ready_for_signature"
    assert update["block_reason"] is None
    assert update["block_source"] is None


def test_audit_log_entry_has_hmac_signature():
    service, client = _make_service()
    event = SignatureBlockEvent(
        document_id="doc-789",
        block_signing=True,
        reason="Missing mandatory clause",
    )

    asyncio.run(service.process_block_event(event, org_id="org-1", actor_id="agent-1"))

    assert len(client.inserted_audits) == 1
    audit = client.inserted_audits[0]
    assert audit["org_id"] == "org-1"
    assert audit["actor_type"] == "system"
    assert audit["actor_id"] == "agent-1"
    assert audit["action"] == "signature_blocked"
    assert audit["resource_type"] == "generated_document"
    assert audit["resource_id"] == "doc-789"
    assert "signature" in audit
    assert len(audit["signature"]) == 64  # SHA-256 hex


def test_unblock_event_logs_signature_unblocked_action():
    service, client = _make_service(document_status="signature_blocked")
    event = SignatureBlockEvent(
        document_id="doc-101",
        block_signing=False,
        reason="Issue resolved after manual review",
    )

    asyncio.run(service.process_block_event(event, org_id="org-2"))

    audit = client.inserted_audits[0]
    assert audit["action"] == "signature_unblocked"
    assert audit["details"]["block_signing"] is False
    assert audit["details"]["new_status"] == "ready_for_signature"


def test_hmac_signature_generation_is_deterministic():
    service, _ = _make_service()
    payload = {"document_id": "doc-1", "action": "block"}

    sig1 = service.generate_hmac_signature(payload)
    sig2 = service.generate_hmac_signature(payload)

    assert sig1 == sig2
    assert len(sig1) == 64  # SHA-256 hex length


def test_hmac_signature_changes_with_different_payload():
    service, _ = _make_service()
    payload_a = {"document_id": "doc-1", "action": "block"}
    payload_b = {"document_id": "doc-2", "action": "block"}

    sig_a = service.generate_hmac_signature(payload_a)
    sig_b = service.generate_hmac_signature(payload_b)

    assert sig_a != sig_b


def test_verify_event_hmac_valid():
    service, _ = _make_service()
    event = SignatureBlockEvent(
        document_id="doc-hmac",
        block_signing=True,
        reason="Test reason",
        timestamp=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
    )

    # Generate a valid HMAC for this event
    payload = {
        "document_id": event.document_id,
        "block_signing": event.block_signing,
        "reason": event.reason,
        "timestamp": event.timestamp.isoformat(),
    }
    valid_sig = service.generate_hmac_signature(payload)
    event.hmac_signature = valid_sig

    assert service.verify_event_hmac(event) is True


def test_verify_event_hmac_invalid():
    service, _ = _make_service()
    event = SignatureBlockEvent(
        document_id="doc-hmac",
        block_signing=True,
        reason="Test reason",
        timestamp=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        hmac_signature="invalid-signature-value",
    )

    assert service.verify_event_hmac(event) is False


def test_verify_event_hmac_empty_signature():
    service, _ = _make_service()
    event = SignatureBlockEvent(
        document_id="doc-hmac",
        block_signing=True,
        reason="Test",
        hmac_signature="",
    )

    assert service.verify_event_hmac(event) is False


def test_sla_tracking_included_in_result():
    service, _ = _make_service()
    event = SignatureBlockEvent(
        document_id="doc-sla",
        block_signing=True,
        reason="SLA test",
    )

    result = asyncio.run(service.process_block_event(event, org_id="org-1"))

    # The in-memory mock should complete well within 5 seconds
    assert result.sla_met is True
    assert result.propagation_ms < PROPAGATION_SLA_SECONDS * 1000
