"""
Property-based test: Signature Block/Unblock Round-Trip with Audit (Property 10)

**Validates: Requirements 12.3, 12.4**

Property statement: For any document, blocking (setting block_signing=true) and
then unblocking (setting block_signing=false) shall restore the document to
'ready_for_signature' status. Every block and unblock event shall produce an
audit_log entry with a valid HMAC-SHA256 signature over the event payload.

This test validates the pure logic of:
1. Status transitions via sequences of block/unblock events
2. Final status correctness based on the last event in the sequence
3. HMAC-SHA256 audit_log entries produced for every event
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac as hmac_module
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Ensure env vars are set before importing backend modules

from backend.services.dms_signature_service import (
    DmsSignatureService,
    SignatureBlockEvent,
    SignatureBlockResult,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HMAC_SHA256_HEX_LENGTH = 64  # 256 bits = 32 bytes = 64 hex chars
HMAC_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")


# ---------------------------------------------------------------------------
# Fake Neon client that tracks mutations
# ---------------------------------------------------------------------------

class FakeExecuteResult:
    def __init__(self, data=None):
        self.data = data or []


class TrackedNeonClient:
    """Tracks all document updates and audit_log inserts."""

    def __init__(self, initial_status: str = "ready_for_signature"):
        self.current_status = initial_status
        self.audit_entries: list[dict[str, Any]] = []
        self.status_updates: list[dict[str, Any]] = []

    def table(self, name: str):
        if name == "generated_documents":
            return _DocumentTableProxy(self)
        if name == "audit_log":
            return _AuditTableProxy(self)
        raise ValueError(f"Unexpected table: {name}")


class _DocumentTableProxy:
    def __init__(self, client: TrackedNeonClient):
        self._client = client

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def update(self, data: dict):
        self._client.status_updates.append(data)
        self._client.current_status = data.get(
            "signature_status", self._client.current_status
        )
        return self

    def execute(self):
        return FakeExecuteResult(
            [{"signature_status": self._client.current_status}]
        )


class _AuditTableProxy:
    def __init__(self, client: TrackedNeonClient):
        self._client = client

    def insert(self, data: dict):
        self._client.audit_entries.append(data)
        return self

    def execute(self):
        return FakeExecuteResult([{"id": "audit-entry"}])


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Generate non-empty block_signing booleans for event sequences
block_signing_values = st.booleans()

# Generate sequences of block/unblock events (1 to 20 events)
event_sequences = st.lists(
    block_signing_values,
    min_size=1,
    max_size=20,
)

# Reasonable document IDs
document_ids = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("L", "Nd", "Pc", "Pd")),
)

# Audit secrets (non-empty strings)
audit_secrets = st.text(min_size=8, max_size=64, alphabet=st.characters(
    whitelist_categories=("L", "Nd"),
))

# Reasons for blocking/unblocking
reasons = st.text(min_size=1, max_size=100, alphabet=st.characters(
    whitelist_categories=("L", "Nd", "Zs", "Pc"),
))

# Org IDs
org_ids = st.uuids().map(str)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestSignatureBlockUnblockRoundTrip:
    """
    Property 10: Signature Block/Unblock Round-Trip with Audit.

    **Validates: Requirements 12.3, 12.4**
    """

    @given(
        document_id=document_ids,
        secret=audit_secrets,
        reasons_list=st.lists(reasons, min_size=2, max_size=2),
        org_id=org_ids,
    )
    @settings(max_examples=200)
    def test_block_then_unblock_restores_ready_for_signature(
        self,
        document_id: str,
        secret: str,
        reasons_list: list[str],
        org_id: str,
    ):
        """
        For any document, blocking then unblocking shall restore status to
        'ready_for_signature'.

        **Validates: Requirements 12.3**
        """
        client = TrackedNeonClient(initial_status="ready_for_signature")
        service = DmsSignatureService(database_client=client, audit_secret=secret)

        # Block event
        block_event = SignatureBlockEvent(
            document_id=document_id,
            block_signing=True,
            reason=reasons_list[0],
        )
        result_block = asyncio.run(
            service.process_block_event(block_event, org_id=org_id)
        )
        assert result_block.new_status == "signature_blocked"

        # Unblock event
        unblock_event = SignatureBlockEvent(
            document_id=document_id,
            block_signing=False,
            reason=reasons_list[1],
        )
        result_unblock = asyncio.run(
            service.process_block_event(unblock_event, org_id=org_id)
        )

        # After unblock, status must be 'ready_for_signature'
        assert result_unblock.new_status == "ready_for_signature"
        assert client.current_status == "ready_for_signature"

    @given(
        document_id=document_ids,
        secret=audit_secrets,
        sequence=event_sequences,
        org_id=org_ids,
    )
    @settings(max_examples=200)
    def test_final_status_determined_by_last_event(
        self,
        document_id: str,
        secret: str,
        sequence: list[bool],
        org_id: str,
    ):
        """
        For any sequence of block/unblock events, the final document status
        is determined solely by the last event: block_signing=True → 'signature_blocked',
        block_signing=False → 'ready_for_signature'.

        **Validates: Requirements 12.3**
        """
        client = TrackedNeonClient(initial_status="ready_for_signature")
        service = DmsSignatureService(database_client=client, audit_secret=secret)

        for block_signing in sequence:
            event = SignatureBlockEvent(
                document_id=document_id,
                block_signing=block_signing,
                reason="auto-generated-reason",
            )
            asyncio.run(service.process_block_event(event, org_id=org_id))

        # Final status depends only on last event
        last_block_signing = sequence[-1]
        expected_status = (
            "signature_blocked" if last_block_signing else "ready_for_signature"
        )
        assert client.current_status == expected_status

    @given(
        document_id=document_ids,
        secret=audit_secrets,
        sequence=event_sequences,
        org_id=org_ids,
    )
    @settings(max_examples=200)
    def test_every_event_produces_audit_log_entry(
        self,
        document_id: str,
        secret: str,
        sequence: list[bool],
        org_id: str,
    ):
        """
        Every block and unblock event shall produce an audit_log entry.
        The number of audit entries must equal the number of events processed.

        **Validates: Requirements 12.4**
        """
        client = TrackedNeonClient(initial_status="ready_for_signature")
        service = DmsSignatureService(database_client=client, audit_secret=secret)

        for block_signing in sequence:
            event = SignatureBlockEvent(
                document_id=document_id,
                block_signing=block_signing,
                reason="test-reason",
            )
            asyncio.run(service.process_block_event(event, org_id=org_id))

        # One audit entry per event
        assert len(client.audit_entries) == len(sequence)

    @given(
        document_id=document_ids,
        secret=audit_secrets,
        sequence=event_sequences,
        org_id=org_ids,
    )
    @settings(max_examples=200)
    def test_every_audit_entry_has_valid_hmac_sha256_signature(
        self,
        document_id: str,
        secret: str,
        sequence: list[bool],
        org_id: str,
    ):
        """
        Every audit_log entry produced by block/unblock events shall contain
        a valid HMAC-SHA256 signature (64-character hex string).

        **Validates: Requirements 12.4**
        """
        client = TrackedNeonClient(initial_status="ready_for_signature")
        service = DmsSignatureService(database_client=client, audit_secret=secret)

        for block_signing in sequence:
            event = SignatureBlockEvent(
                document_id=document_id,
                block_signing=block_signing,
                reason="test-reason",
            )
            asyncio.run(service.process_block_event(event, org_id=org_id))

        # Verify every audit entry has a valid HMAC-SHA256 signature
        for entry in client.audit_entries:
            signature = entry.get("signature", "")
            assert len(signature) == HMAC_SHA256_HEX_LENGTH, (
                f"Expected {HMAC_SHA256_HEX_LENGTH}-char hex signature, "
                f"got {len(signature)} chars: {signature!r}"
            )
            assert HMAC_HEX_PATTERN.match(signature), (
                f"Signature is not valid hex: {signature!r}"
            )

    @given(
        document_id=document_ids,
        secret=audit_secrets,
        block_signing=block_signing_values,
        reason=reasons,
        org_id=org_ids,
    )
    @settings(max_examples=200)
    def test_audit_signature_is_verifiable_hmac(
        self,
        document_id: str,
        secret: str,
        block_signing: bool,
        reason: str,
        org_id: str,
    ):
        """
        The HMAC-SHA256 signature in each audit entry shall be verifiable
        by recomputing HMAC over the audit payload with the same secret.

        **Validates: Requirements 12.4**
        """
        client = TrackedNeonClient(initial_status="ready_for_signature")
        service = DmsSignatureService(database_client=client, audit_secret=secret)

        event = SignatureBlockEvent(
            document_id=document_id,
            block_signing=block_signing,
            reason=reason,
        )
        asyncio.run(service.process_block_event(event, org_id=org_id))

        assert len(client.audit_entries) == 1
        entry = client.audit_entries[0]

        # Recompute HMAC over the payload stored in details
        payload = entry["details"]
        expected_sig = service.generate_hmac_signature(payload)

        assert entry["signature"] == expected_sig, (
            f"Audit signature mismatch: stored={entry['signature']!r}, "
            f"expected={expected_sig!r}"
        )
