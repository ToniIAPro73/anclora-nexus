"""Tests for CLM features: expanded review decisions, CLM signature flows,
legal review queue, DocuSeal webhook (CLM path), retention sweep."""

import hashlib
import hmac
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("DOCUSEAL_API_KEY", "docuseal-api-key")
os.environ.setdefault("DOCUSEAL_WEBHOOK_SECRET", "webhook-secret")
os.environ.setdefault("NEXUS_DOCUMENT_ENCRYPTION_KEY", "00" * 32)
os.environ.setdefault("NEXUS_INTERNAL_API_KEY", "internal-key-test")

from backend.api.deps import get_current_user, get_org_id
from backend.api.routes.dms import require_dms_membership, router as dms_router
from backend.api.routes.dms_legal_review import router as legal_review_router, require_dms_membership as lr_require
from backend.api.internal_webhooks import router as internal_router

ORG_ID = str(uuid4())
USER_ID = str(uuid4())
DOC_ID = str(uuid4())
VERSION_ID = str(uuid4())
FLOW_ID = str(uuid4())

# ── Shared test app ────────────────────────────────────────────────────────────

app = FastAPI()
app.include_router(dms_router, prefix="/api/dms")
app.include_router(legal_review_router, prefix="/api/dms")
app.include_router(internal_router)

for dep in (require_dms_membership, lr_require):
    app.dependency_overrides[dep] = lambda: {"id": str(uuid4()), "role": "manager", "status": "active"}
app.dependency_overrides[get_org_id] = lambda: ORG_ID
app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=USER_ID)

client = TestClient(app)


# ── Query builder mock ─────────────────────────────────────────────────────────

class QB:
    def __init__(self, rows=None):
        self._rows = list(rows or [])
        self._insert = None
        self._update = None

    def select(self, *_, **__): return self
    def insert(self, p):
        self._insert = {**p, "id": p.get("id") or str(uuid4())}
        return self
    def update(self, p):
        self._update = p
        return self
    def delete(self): return self
    def eq(self, *_): return self
    def neq(self, *_): return self
    def is_(self, *_): return self
    def order(self, *_, **__): return self
    def limit(self, *_): return self
    def execute(self):
        if self._insert:
            return SimpleNamespace(data=[self._insert])
        if self._update:
            return SimpleNamespace(data=self._rows or [{"updated": True}])
        return SimpleNamespace(data=self._rows)


def _doc_row(status="draft", version_id=None):
    return {
        "id": DOC_ID,
        "org_id": ORG_ID,
        "folder_id": str(uuid4()),
        "template_version_id": str(uuid4()),
        "title": "Test document",
        "status": status,
        "current_version_id": version_id or VERSION_ID,
        "generation_payload": {},
    }


def _version_row(validation_status="approved", signature_status=None, immutable=False):
    return {
        "id": VERSION_ID,
        "org_id": ORG_ID,
        "generated_document_id": DOC_ID,
        "version_number": 1,
        "validation_status": validation_status,
        "signature_status": signature_status,
        "is_signed_immutable": immutable,
        "immutable": immutable,
        "content_md5": "abc",
    }


# ── Review decision tests ──────────────────────────────────────────────────────

@pytest.mark.parametrize("decision", [
    "approved",
    "approved_with_conditions",
    "review_required",
    "changes_required",
    "rejected",
])
def test_review_decision_all_valid_values_accepted(decision, monkeypatch):
    """All five CLM decision values should be accepted by the backend."""

    call_log = []

    def mock_table(name):
        if name == "generated_documents":
            return QB([_doc_row()])
        if name == "document_versions":
            return QB([_version_row()])
        qb = QB()
        qb._insert = {"id": str(uuid4()), "status": decision, "decision": decision, "org_id": ORG_ID}
        call_log.append(name)

        class _Capture(QB):
            def insert(self, p):
                qb._insert = {**p, "id": str(uuid4())}
                return self
            def update(self, p):
                return self

        return _Capture([])

    import backend.api.routes.dms as dms_mod
    monkeypatch.setattr(dms_mod, "_table", mock_table)

    resp = client.post(
        f"/api/dms/generated-documents/{DOC_ID}/review-decisions",
        json={"decision": decision, "notes": "test note"},
    )
    assert resp.status_code in (200, 201), f"Unexpected {resp.status_code} for decision={decision}: {resp.text}"


def test_review_decision_invalid_value_rejected(monkeypatch):
    """Unknown decision values must be rejected with 422."""

    def mock_table(name):
        if name == "generated_documents":
            return QB([_doc_row()])
        if name == "document_versions":
            return QB([_version_row()])
        return QB()

    import backend.api.routes.dms as dms_mod
    monkeypatch.setattr(dms_mod, "_table", mock_table)

    resp = client.post(
        f"/api/dms/generated-documents/{DOC_ID}/review-decisions",
        json={"decision": "force_signed"},
    )
    assert resp.status_code == 422


def test_rejected_decision_blocks_signing(monkeypatch):
    """decisions in {rejected, changes_required, review_required} must set block_signing=True."""
    captured = {}

    def mock_table(name):
        class _QB(QB):
            def insert(self, p):
                if name == "legal_review_decisions":
                    captured.update(p)
                return QB([{**p, "id": str(uuid4())}])
            def update(self, _): return QB()

        if name == "generated_documents":
            return QB([_doc_row()])
        if name == "document_versions":
            return QB([_version_row()])
        return _QB()

    import backend.api.routes.dms as dms_mod
    monkeypatch.setattr(dms_mod, "_table", mock_table)

    client.post(
        f"/api/dms/generated-documents/{DOC_ID}/review-decisions",
        json={"decision": "rejected"},
    )
    assert captured.get("block_signing") is True


def test_approved_with_conditions_does_not_block_signing(monkeypatch):
    """approved_with_conditions should NOT block signing."""
    captured = {}

    def mock_table(name):
        class _QB(QB):
            def insert(self, p):
                if name == "legal_review_decisions":
                    captured.update(p)
                return QB([{**p, "id": str(uuid4())}])
            def update(self, _): return QB()

        if name == "generated_documents":
            return QB([_doc_row()])
        if name == "document_versions":
            return QB([_version_row()])
        return _QB()

    import backend.api.routes.dms as dms_mod
    monkeypatch.setattr(dms_mod, "_table", mock_table)

    client.post(
        f"/api/dms/generated-documents/{DOC_ID}/review-decisions",
        json={"decision": "approved_with_conditions"},
    )
    assert captured.get("block_signing") is False


# ── CLM signature flow tests ───────────────────────────────────────────────────

def test_signature_flow_clm_payload_accepted(monkeypatch):
    """CLM payload (signing_level + signers[]) should be accepted."""
    inserted = {}

    def mock_table(name):
        class _QB(QB):
            def insert(self, p):
                if name == "document_signature_flows":
                    inserted.update(p)
                return QB([{**p, "id": str(uuid4())}])
            def update(self, _): return QB()

        if name == "generated_documents":
            return QB([_doc_row(status="approved")])
        if name == "document_versions":
            return QB([_version_row(validation_status="approved")])
        return _QB()

    import backend.api.routes.dms as dms_mod
    monkeypatch.setattr(dms_mod, "_table", mock_table)

    resp = client.post(
        f"/api/dms/generated-documents/{DOC_ID}/signature-flows",
        json={
            "signing_level": "advanced",
            "signers": [
                {"email": "buyer@test.com", "name": "John Buyer", "role": "buyer"},
                {"email": "seller@test.com", "name": "Jane Seller", "role": "seller"},
            ],
        },
    )
    assert resp.status_code == 201
    assert inserted.get("signing_level") == "advanced"
    assert len(inserted.get("signers", [])) == 2


def test_signature_flow_legacy_single_signer_still_accepted(monkeypatch):
    """Legacy single-signer payload remains backwards-compatible."""
    inserted = {}

    def mock_table(name):
        class _QB(QB):
            def insert(self, p):
                if name == "document_signature_flows":
                    inserted.update(p)
                return QB([{**p, "id": str(uuid4())}])
            def update(self, _): return QB()

        if name == "generated_documents":
            return QB([_doc_row(status="approved")])
        if name == "document_versions":
            return QB([_version_row(validation_status="approved")])
        return _QB()

    import backend.api.routes.dms as dms_mod
    monkeypatch.setattr(dms_mod, "_table", mock_table)

    resp = client.post(
        f"/api/dms/generated-documents/{DOC_ID}/signature-flows",
        json={
            "signer_email": "buyer@test.com",
            "signer_name": "John Buyer",
            "signer_role": "buyer",
        },
    )
    assert resp.status_code == 201
    assert inserted.get("signer_email") == "buyer@test.com"


def test_signature_flow_rejected_document_blocked(monkeypatch):
    """Sending a non-approved document to signature must return 409."""

    def mock_table(name):
        if name == "generated_documents":
            return QB([_doc_row(status="review_required")])
        if name == "document_versions":
            return QB([_version_row(validation_status="review_required")])
        return QB()

    import backend.api.routes.dms as dms_mod
    monkeypatch.setattr(dms_mod, "_table", mock_table)

    resp = client.post(
        f"/api/dms/generated-documents/{DOC_ID}/signature-flows",
        json={"signing_level": "simple", "signers": []},
    )
    assert resp.status_code == 409


# ── Legal review queue tests ───────────────────────────────────────────────────

def test_legal_review_queue_returns_list(monkeypatch):
    """GET /api/dms/legal-review/queue returns a list of enriched decisions."""
    rows = [
        {
            "id": str(uuid4()),
            "generated_document_id": DOC_ID,
            "review_type": "manual",
            "status": "pending",
            "risk_level": "high",
            "block_signing": True,
            "reviewer_id": None,
            "notes": None,
            "decided_at": None,
            "created_at": "2025-01-01T00:00:00Z",
            "generated_documents": {"id": DOC_ID, "title": "Arras", "status": "review_required", "folder_id": str(uuid4()), "language": "es"},
        }
    ]

    import backend.api.routes.dms_legal_review as lr_mod
    monkeypatch.setattr(lr_mod, "_table", lambda _: QB(rows))

    resp = client.get("/api/dms/legal-review/queue")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["status"] == "pending"
    assert data[0]["document"]["title"] == "Arras"


def test_legal_review_queue_filtered_by_status(monkeypatch):
    """Status filter parameter should be forwarded to the query."""
    call_args = {}

    class FilterQB(QB):
        def eq(self, key, value):
            call_args[key] = value
            return self

    import backend.api.routes.dms_legal_review as lr_mod
    monkeypatch.setattr(lr_mod, "_table", lambda _: FilterQB([]))

    resp = client.get("/api/dms/legal-review/queue?status=pending")
    assert resp.status_code == 200
    assert call_args.get("status") == "pending"


# ── DocuSeal webhook (CLM path) ────────────────────────────────────────────────

def _make_webhook_sig(body: bytes, secret: str = "webhook-secret") -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_docuseal_webhook_clm_completed_marks_document_signed(monkeypatch):
    """On submission.completed, generated_document status should be updated to 'signed'."""
    updated_tables = {}

    def mock_table(name):
        class _QB(QB):
            def update(self, p):
                updated_tables[name] = p
                return QB([{"updated": True}])

        if name == "document_signature_flows":
            return _QB([{
                "id": FLOW_ID,
                "org_id": ORG_ID,
                "generated_document_id": DOC_ID,
                "document_version_id": VERSION_ID,
                "flow_status": "sent",
                "audit_trail": [],
            }])
        return _QB([])

    import backend.api.routes.dms as dms_mod
    monkeypatch.setattr(dms_mod, "_table", mock_table)

    import json
    payload = {
        "event": "submission.completed",
        "submission_id": "sub-123",
        "envelope_id": "sub-123",
        "status": "completed",
        "document_url": None,
        "signer_email": "buyer@test.com",
        "ip_address": "1.2.3.4",
        "signing_timestamp": None,
    }
    body = json.dumps(payload).encode()
    sig = _make_webhook_sig(body)

    resp = client.post(
        "/api/dms/webhooks/docuseal",
        content=body,
        headers={"content-type": "application/json", "x-docuseal-signature": sig},
    )
    assert resp.status_code == 200
    assert resp.json().get("flow_status") == "signed"
    assert updated_tables.get("generated_documents", {}).get("status") == "signed"


def test_docuseal_webhook_invalid_sig_returns_401():
    """Tampered webhook signature must be rejected."""
    import json
    payload = {"event": "submission.completed", "envelope_id": "x", "status": "completed"}
    body = json.dumps(payload).encode()

    resp = client.post(
        "/api/dms/webhooks/docuseal",
        content=body,
        headers={"content-type": "application/json", "x-docuseal-signature": "bad-sig"},
    )
    assert resp.status_code == 401


# ── Retention sweep tests ──────────────────────────────────────────────────────

def test_retention_sweep_requires_api_key():
    """Endpoint must reject requests without the internal API key."""
    resp = client.post("/api/internal/webhooks/dms-retention-sweep")
    assert resp.status_code == 403


def test_retention_sweep_with_valid_key(monkeypatch):
    """With a valid key, the sweep endpoint calls enforce_retention_for_org per org."""
    calls = []

    async def mock_enforce(org_id):
        calls.append(org_id)
        return {"org_id": org_id, "archived": 0, "flagged": 0, "evaluated": 0}

    import backend.api.internal_webhooks as wh_mod
    monkeypatch.setattr(
        "backend.services.document_retention_service.enforce_retention_for_org",
        mock_enforce,
    )
    # Patch neon query to return two orgs
    monkeypatch.setattr(
        wh_mod.neon_service.client,
        "table",
        lambda _: QB([{"org_id": ORG_ID}, {"org_id": str(uuid4())}]),
    )

    resp = client.post(
        "/api/internal/webhooks/dms-retention-sweep",
        headers={"Authorization": "Bearer internal-key-test"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["orgs_processed"] == 2
    assert data["errors"] == []
