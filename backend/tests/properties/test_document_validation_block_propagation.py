"""
Property-based test: Document Validation Block Propagation (Property 8)

**Validates: Requirements 10.3, 10.4**

For any contract validation response from Advisor AI, the DMS document status
shall be 'signature_blocked' if and only if block_signing === true.
When block_signing === false, the document status shall be 'ready_for_signature'.

This test validates the core logic of `DmsSignatureService.process_block_event`:
- block_signing=True → new_status == "signature_blocked"
- block_signing=False → new_status == "ready_for_signature"

We use hypothesis to generate arbitrary SignatureBlockEvent data and verify the
biconditional property holds across all inputs.
"""

import asyncio
import os
from datetime import datetime, timezone
from typing import Any

from hypothesis import given, settings
from hypothesis.strategies import (
    booleans,
    datetimes,
    text,
    uuids,
)

# Environment variables needed before importing the service

from backend.services.dms_signature_service import (
    DmsSignatureService,
    SignatureBlockEvent,
    SignatureBlockResult,
)


# ---------------------------------------------------------------------------
# Fake Neon client for property tests
# ---------------------------------------------------------------------------

class FakeExecuteResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeDocumentQuery:
    """Chainable mock for the generated_documents table."""

    def __init__(self, current_status: str, tracker: list):
        self._status = current_status
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
    """Chainable mock for the audit_log table."""

    def __init__(self, tracker: list):
        self._tracker = tracker

    def insert(self, data):
        self._tracker.append(data)
        return self

    def execute(self):
        return FakeExecuteResult([{"id": "audit-prop-test"}])


class FakeClient:
    """Minimal Neon client mock for property testing."""

    def __init__(self, document_status: str = "ready_for_signature"):
        self._document_status = document_status
        self.inserted_audits: list[dict[str, Any]] = []
        self.updated_documents: list[dict[str, Any]] = []

    def table(self, name: str):
        if name == "generated_documents":
            return FakeDocumentQuery(self._document_status, self.updated_documents)
        if name == "audit_log":
            return FakeAuditQuery(self.inserted_audits)
        return FakeDocumentQuery(self._document_status, self.updated_documents)


def _make_service(document_status: str = "ready_for_signature") -> DmsSignatureService:
    """Create a DmsSignatureService with an injected fake client."""
    client = FakeClient(document_status)
    return DmsSignatureService(
        database_client=client,
        audit_secret="property-test-secret-key-32bytes!",
    )


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Generate realistic document IDs
document_ids = text(min_size=1, max_size=64, alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_")

# Generate arbitrary reasons
reasons = text(min_size=1, max_size=200)

# Generate timestamps within a practical range
event_timestamps = datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=...,
)

# Generate org IDs
org_ids = text(min_size=1, max_size=36, alphabet="abcdefghijklmnopqrstuvwxyz0123456789-")


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

@given(
    block_signing=booleans(),
    document_id=document_ids,
    reason=reasons,
)
@settings(max_examples=500)
def test_block_signing_true_produces_signature_blocked(
    block_signing: bool,
    document_id: str,
    reason: str,
) -> None:
    """
    Property 8: Document Validation Block Propagation

    For any contract validation response, the DMS document status shall be
    'signature_blocked' iff block_signing is True, and 'ready_for_signature'
    iff block_signing is False.

    **Validates: Requirements 10.3, 10.4**
    """
    service = _make_service()
    event = SignatureBlockEvent(
        document_id=document_id,
        block_signing=block_signing,
        reason=reason,
    )

    result = asyncio.run(
        service.process_block_event(event, org_id="org-property-test")
    )

    # Core biconditional property
    if block_signing:
        assert result.new_status == "signature_blocked", (
            f"block_signing=True but status is '{result.new_status}', "
            f"expected 'signature_blocked' (document_id={document_id})"
        )
    else:
        assert result.new_status == "ready_for_signature", (
            f"block_signing=False but status is '{result.new_status}', "
            f"expected 'ready_for_signature' (document_id={document_id})"
        )


@given(
    block_signing=booleans(),
    document_id=document_ids,
    reason=reasons,
)
@settings(max_examples=500)
def test_status_is_signature_blocked_iff_block_signing_true(
    block_signing: bool,
    document_id: str,
    reason: str,
) -> None:
    """
    Property 8 (biconditional verification): Assert the iff relationship.

    status == 'signature_blocked' ↔ block_signing == True
    status == 'ready_for_signature' ↔ block_signing == False

    **Validates: Requirements 10.3, 10.4**
    """
    service = _make_service()
    event = SignatureBlockEvent(
        document_id=document_id,
        block_signing=block_signing,
        reason=reason,
    )

    result = asyncio.run(
        service.process_block_event(event, org_id="org-biconditional")
    )

    # Forward direction: block_signing=True → signature_blocked
    # Backward direction: signature_blocked → block_signing=True
    is_blocked = result.new_status == "signature_blocked"
    is_ready = result.new_status == "ready_for_signature"

    assert is_blocked == block_signing, (
        f"Biconditional violated: block_signing={block_signing} but "
        f"is_blocked={is_blocked} (status='{result.new_status}')"
    )
    assert is_ready == (not block_signing), (
        f"Biconditional violated: block_signing={block_signing} but "
        f"is_ready={is_ready} (status='{result.new_status}')"
    )

    # The result must be one of the two valid statuses
    assert result.new_status in ("signature_blocked", "ready_for_signature"), (
        f"Unexpected status: '{result.new_status}'"
    )
