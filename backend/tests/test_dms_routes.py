import hashlib
import hmac
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

os.environ.setdefault("DOCUSEAL_WEBHOOK_SECRET", "docuseal-secret")
os.environ.setdefault("NEXUS_DOCUMENT_ENCRYPTION_KEY", "00" * 32)

from backend.api.deps import get_current_user, get_org_id
from backend.api.routes import dms as router_module
from backend.api.routes.dms import require_dms_membership, router


ORG_ID = str(uuid4())
OTHER_ORG_ID = str(uuid4())
USER_ID = str(uuid4())

app = FastAPI()
app.include_router(router, prefix="/api/dms")
app.dependency_overrides[get_org_id] = lambda: ORG_ID
app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=USER_ID)
app.dependency_overrides[require_dms_membership] = lambda: {"id": str(uuid4()), "role": "manager", "status": "active"}
client = TestClient(app)


class QueryBuilder:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []
        self.insert_payload = None
        self.update_payload = None
        self.delete_mode = False

    def select(self, *_args, **_kwargs):
        return self

    def insert(self, payload):
        self.insert_payload = {**payload, "id": payload.get("id") or str(uuid4())}
        return self

    def update(self, payload):
        self.update_payload = payload
        return self

    def delete(self):
        self.delete_mode = True
        return self

    def eq(self, key, value):
        self.filters.append((key, str(value)))
        return self

    def in_(self, key, values):
        self.filters.append((key, {str(value) for value in values}))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        if self.insert_payload is not None:
            self.rows.append(self.insert_payload)
            return SimpleNamespace(data=[self.insert_payload])

        matched = [
            row for row in self.rows
            if all(
                str(row.get(key)) in value if isinstance(value, set) else str(row.get(key)) == value
                for key, value in self.filters
            )
        ]
        if self.delete_mode:
            for row in list(matched):
                self.rows.remove(row)
            return SimpleNamespace(data=matched)
        if self.update_payload is not None:
            for row in matched:
                row.update(self.update_payload)
            return SimpleNamespace(data=matched)
        return SimpleNamespace(data=matched)


class StorageBucketStub:
    def __init__(self, storage):
        self.storage = storage

    def upload(self, path, payload, file_options=None):
        self.storage[path] = {"payload": payload, "options": file_options or {}}
        return SimpleNamespace(path=path)

    def download(self, path):
        return self.storage[path]["payload"]


class StorageStub:
    def __init__(self, storage):
        self.storage = storage

    def from_(self, _bucket):
        return StorageBucketStub(self.storage)


class NeonClientStub:
    def __init__(self):
        self.tables = {
            "real_estate_deal_folders": [],
            "deal_documents": [],
            "document_signature_flows": [],
            "properties": [],
            "leads": [],
            "nexus_sellers": [],
            "companies": [],
            "contacts": [],
            "organizations": [],
            "document_templates": [],
            "document_template_versions": [],
            "document_template_fields": [],
            "deal_folder_parties": [],
            "generated_documents": [],
            "document_versions": [],
            "legal_review_decisions": [],
            "generated_document_signature_flows": [],
            "audit_log": [],
        }
        self.storage_data = {}
        self.storage = StorageStub(self.storage_data)

    def table(self, name):
        return QueryBuilder(self.tables.setdefault(name, []))


@pytest.fixture(autouse=True)
def stub_blob_storage(monkeypatch):
    """Keep DMS route tests isolated from live Vercel Blob credentials."""
    def put(path, payload, **_kwargs):
        client_stub = router_module.neon_service.client
        client_stub.storage_data[path] = {"payload": payload, "options": {}}
        return path

    def get(path, **_kwargs):
        client_stub = router_module.neon_service.client
        return client_stub.storage_data[path]["payload"]

    monkeypatch.setattr(router_module, "put_private_blob", put)
    monkeypatch.setattr(router_module, "get_private_blob", get)


def install_stub(monkeypatch, stub: NeonClientStub) -> NeonClientStub:
    monkeypatch.setattr("backend.api.routes.dms.neon_service.client", stub)
    return stub


def add_folder(stub: NeonClientStub, org_id: str = ORG_ID) -> str:
    folder_id = str(uuid4())
    stub.tables["real_estate_deal_folders"].append({
        "id": folder_id,
        "org_id": org_id,
        "operation_type": "compraventa",
    })
    return folder_id


def add_document(stub: NeonClientStub, folder_id: str, status: str = "pending") -> dict:
    from backend.services.document_encryption_service import DocumentEncryptionService

    content = b"Contrato de compraventa con clausulas de firma."
    payload, iv, tag = DocumentEncryptionService.encrypt_file(content)
    path = f"dms/{ORG_ID}/{folder_id}/doc.enc"
    stub.storage_data[path] = {"payload": payload, "options": {}}
    document = {
        "id": str(uuid4()),
        "folder_id": folder_id,
        "org_id": ORG_ID,
        "title": "Contrato",
        "document_category": "contrato_compraventa",
        "storage_path": path,
        "file_mime_type": "text/plain",
        "file_size_bytes": len(content),
        "sha256_hash": hashlib.sha256(content).hexdigest(),
        "encryption_iv": iv.hex(),
        "encryption_auth_tag": tag.hex(),
        "compliance_status": status,
        "legal_metadata": {"immutable": False},
    }
    stub.tables["deal_documents"].append(document)
    return document


def test_create_folder_returns_uuid(monkeypatch) -> None:
    stub = install_stub(monkeypatch, NeonClientStub())
    lead_id = str(uuid4())
    stub.tables["leads"].append({"id": lead_id, "org_id": ORG_ID, "full_name": "Cliente"})

    response = client.post(
        "/api/dms/folders",
        json={
            "property_id": None,
            "client_lead_id": lead_id,
            "seller_id": None,
            "operation_type": "compraventa",
        },
    )

    assert response.status_code == 200
    assert response.json()["id"]
    assert stub.tables["real_estate_deal_folders"][0]["org_id"] == ORG_ID


def test_create_folder_requires_primary_client(monkeypatch) -> None:
    install_stub(monkeypatch, NeonClientStub())

    response = client.post(
        "/api/dms/folders",
        json={
            "property_id": None,
            "client_lead_id": None,
            "seller_id": None,
            "operation_type": "compraventa",
        },
    )

    assert response.status_code == 422


def test_create_folder_without_permissions_rejected(monkeypatch) -> None:
    install_stub(monkeypatch, NeonClientStub())

    async def forbidden_membership():
        raise HTTPException(status_code=403, detail="forbidden")

    app.dependency_overrides[require_dms_membership] = forbidden_membership
    try:
        response = client.post(
            "/api/dms/folders",
            json={"operation_type": "compraventa"},
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides[require_dms_membership] = lambda: {"id": str(uuid4()), "role": "manager", "status": "active"}


def test_upload_encrypts_document(monkeypatch) -> None:
    stub = install_stub(monkeypatch, NeonClientStub())
    folder_id = add_folder(stub)
    original = b"%PDF-1.4 confidential"

    response = client.post(
        "/api/dms/documents/upload",
        data={"folder_id": folder_id, "title": "Nota simple", "document_category": "nota_simple"},
        files={"file": ("nota.pdf", original, "application/pdf")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sha256_hash"] == hashlib.sha256(original).hexdigest()
    stored = next(iter(stub.storage_data.values()))["payload"]
    assert stored != original


def test_upload_rejects_unsupported_mime(monkeypatch) -> None:
    stub = install_stub(monkeypatch, NeonClientStub())
    folder_id = add_folder(stub)

    response = client.post(
        "/api/dms/documents/upload",
        data={"folder_id": folder_id, "title": "exe", "document_category": "nota_simple"},
        files={"file": ("bad.exe", b"bad", "application/x-msdownload")},
    )

    assert response.status_code == 415


def test_upload_rejects_oversized_file(monkeypatch) -> None:
    stub = install_stub(monkeypatch, NeonClientStub())
    folder_id = add_folder(stub)
    monkeypatch.setenv("NEXUS_DMS_MAX_UPLOAD_BYTES", "4")

    response = client.post(
        "/api/dms/documents/upload",
        data={"folder_id": folder_id, "title": "large", "document_category": "nota_simple"},
        files={"file": ("large.pdf", b"12345", "application/pdf")},
    )

    assert response.status_code == 413
    monkeypatch.delenv("NEXUS_DMS_MAX_UPLOAD_BYTES", raising=False)


def test_upload_rejects_folder_from_other_org(monkeypatch) -> None:
    stub = install_stub(monkeypatch, NeonClientStub())
    folder_id = add_folder(stub, OTHER_ORG_ID)

    response = client.post(
        "/api/dms/documents/upload",
        data={"folder_id": folder_id, "title": "Nota", "document_category": "nota_simple"},
        files={"file": ("nota.pdf", b"%PDF", "application/pdf")},
    )

    assert response.status_code == 404


def test_download_rejects_user_without_permissions(monkeypatch) -> None:
    stub = install_stub(monkeypatch, NeonClientStub())
    folder_id = add_folder(stub)
    document = add_document(stub, folder_id)

    async def forbidden_membership():
        raise HTTPException(status_code=403, detail="forbidden")

    app.dependency_overrides[require_dms_membership] = forbidden_membership
    try:
        response = client.get(f"/api/dms/documents/{document['id']}/download")
        assert response.status_code == 403
    finally:
        app.dependency_overrides[require_dms_membership] = lambda: {"id": str(uuid4()), "role": "manager", "status": "active"}


def test_validate_calls_advisor_ai_mock(monkeypatch) -> None:
    stub = install_stub(monkeypatch, NeonClientStub())
    folder_id = add_folder(stub)
    document = add_document(stub, folder_id)
    calls = []

    async def fake_validate_contract(**kwargs):
        calls.append(kwargs)
        return {
            "status": "ok",
            "block_signing": False,
            "confidence": 0.9,
            "summary": "Sin bloqueos",
            "findings": [],
            "required_actions": [],
            "missing_documents": [],
            "legal_disclaimer": "No sustituye abogado.",
            "sources": [],
            "advisor_available": True,
        }

    monkeypatch.setattr(
        "backend.api.routes.dms.advisor_contract_validator_service.validate_contract",
        fake_validate_contract,
    )

    response = client.post(f"/api/dms/documents/{document['id']}/validate", json={})

    assert response.status_code == 200
    assert calls
    assert response.json()["document"]["compliance_status"] == "approved"


def test_block_signing_updates_compliance_rejected(monkeypatch) -> None:
    stub = install_stub(monkeypatch, NeonClientStub())
    folder_id = add_folder(stub)
    document = add_document(stub, folder_id)

    async def fake_validate_contract(**_kwargs):
        return {
            "status": "review_required",
            "block_signing": True,
            "confidence": 0.8,
            "summary": "Bloqueo",
            "findings": [{"severity": "critical"}],
            "required_actions": ["No firmar"],
            "missing_documents": [],
            "legal_disclaimer": "No sustituye abogado.",
            "sources": [],
            "advisor_available": True,
        }

    monkeypatch.setattr(
        "backend.api.routes.dms.advisor_contract_validator_service.validate_contract",
        fake_validate_contract,
    )

    response = client.post(f"/api/dms/documents/{document['id']}/validate", json={})

    assert response.status_code == 200
    assert response.json()["document"]["compliance_status"] == "rejected"


def test_rejected_document_cannot_be_sent_to_signature(monkeypatch) -> None:
    stub = install_stub(monkeypatch, NeonClientStub())
    folder_id = add_folder(stub)
    document = add_document(stub, folder_id, status="rejected")

    response = client.post(
        f"/api/dms/documents/{document['id']}/signature-flows",
        json={"signer_email": "a@example.com", "signer_name": "A", "signer_role": "buyer"},
    )

    assert response.status_code == 409


def test_docuseal_webhook_invalid_hmac_returns_401() -> None:
    response = client.post(
        "/api/dms/webhooks/docuseal",
        json={
            "event": "submission.completed",
            "submission_id": None,
            "envelope_id": "env_123",
            "status": "completed",
            "document_url": None,
            "signer_email": None,
            "ip_address": None,
            "signing_timestamp": None,
        },
        headers={"x-docuseal-signature": "invalid"},
    )

    assert response.status_code == 401


def test_docuseal_webhook_valid_hmac_updates_signed(monkeypatch) -> None:
    stub = install_stub(monkeypatch, NeonClientStub())
    folder_id = add_folder(stub)
    document = add_document(stub, folder_id)
    stub.tables["document_signature_flows"].append({
        "id": str(uuid4()),
        "document_id": document["id"],
        "org_id": ORG_ID,
        "external_envelope_id": "env_123",
        "flow_status": "sent",
    })
    body = (
        b'{"event":"submission.completed","submission_id":null,"envelope_id":"env_123",'
        b'"status":"completed","document_url":"https://docuseal.test/signed.pdf",'
        b'"signer_email":null,"ip_address":"127.0.0.1","signing_timestamp":null}'
    )
    signature = hmac.new(
        os.environ["DOCUSEAL_WEBHOOK_SECRET"].encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    response = client.post(
        "/api/dms/webhooks/docuseal",
        content=body,
        headers={"x-docuseal-signature": signature, "content-type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json().get("ok") is True
    assert response.json().get("flow_status") == "signed"
    assert stub.tables["document_signature_flows"][0]["flow_status"] == "signed"
    assert stub.tables["deal_documents"][0]["legal_metadata"]["immutable"] is True


def test_generate_document_requires_operation_parties(monkeypatch) -> None:
    stub = install_stub(monkeypatch, NeonClientStub())
    folder_id = add_folder(stub)
    stub.tables["real_estate_deal_folders"][0]["client_lead_id"] = str(uuid4())
    template_id = str(uuid4())
    version_id = str(uuid4())
    stub.tables["document_templates"].append({
        "id": template_id,
        "org_id": ORG_ID,
        "name": "Contrato",
        "template_document_type": "contrato_compraventa",
        "status": "published",
    })
    stub.tables["document_template_versions"].append({
        "id": version_id,
        "org_id": ORG_ID,
        "template_id": template_id,
        "version_number": 1,
        "status": "published",
        "canonical_text": "Contrato {{ buyer_name }}",
    })

    response = client.post(
        f"/api/dms/folders/{folder_id}/generate-document",
        json={"template_version_id": version_id, "title": "Contrato", "generation_payload": {}},
    )

    assert response.status_code == 422
    assert "missing_party_roles" in response.json()["detail"]


def test_available_templates_filter_by_operation_and_language(monkeypatch) -> None:
    stub = install_stub(monkeypatch, NeonClientStub())
    folder_id = add_folder(stub)
    allowed_template_id = str(uuid4())
    nda_template_id = str(uuid4())
    english_template_id = str(uuid4())

    stub.tables["document_templates"].extend([
        {
            "id": allowed_template_id,
            "org_id": ORG_ID,
            "name": "Arras ES",
            "template_document_type": "arras_penitenciales",
            "language": "es",
            "jurisdiction": "ES-IB",
            "status": "published",
        },
        {
            "id": nda_template_id,
            "org_id": ORG_ID,
            "name": "Contrato Temporada ES",
            "template_document_type": "contrato_temporada",
            "language": "es",
            "jurisdiction": "ES-IB",
            "status": "published",
        },
        {
            "id": english_template_id,
            "org_id": ORG_ID,
            "name": "Arras EN",
            "template_document_type": "arras_penitenciales",
            "language": "en",
            "jurisdiction": "ES-IB",
            "status": "published",
        },
    ])
    stub.tables["document_template_versions"].extend([
        {
            "id": str(uuid4()),
            "org_id": ORG_ID,
            "template_id": allowed_template_id,
            "version_number": 1,
            "status": "published",
            "language": "es",
            "canonical_text": "Arras {{ buyer.full_name }}",
        },
        {
            "id": str(uuid4()),
            "org_id": ORG_ID,
            "template_id": nda_template_id,
            "version_number": 1,
            "status": "published",
            "language": "es",
            "canonical_text": "Contrato de temporada",
        },
        {
            "id": str(uuid4()),
            "org_id": ORG_ID,
            "template_id": english_template_id,
            "version_number": 1,
            "status": "published",
            "language": "en",
            "canonical_text": "Earnest money",
        },
    ])

    response = client.get(f"/api/dms/folders/{folder_id}/available-templates?language=es")

    assert response.status_code == 200
    rows = response.json()
    assert [row["name"] for row in rows] == ["Arras ES"]
    assert rows[0]["latest_version"]["language"] == "es"


def test_preview_missing_fields_reports_generation_prerequisites(monkeypatch) -> None:
    stub = install_stub(monkeypatch, NeonClientStub())
    folder_id = add_folder(stub)
    stub.tables["real_estate_deal_folders"][0]["client_lead_id"] = str(uuid4())
    template_id = str(uuid4())
    version_id = str(uuid4())
    stub.tables["document_templates"].append({
        "id": template_id,
        "org_id": ORG_ID,
        "name": "Contrato",
        "template_document_type": "contrato_compraventa",
        "status": "published",
    })
    stub.tables["document_template_versions"].append({
        "id": version_id,
        "org_id": ORG_ID,
        "template_id": template_id,
        "version_number": 1,
        "status": "published",
        "canonical_text": "Contrato",
    })

    response = client.post(
        f"/api/dms/folders/{folder_id}/preview-missing-fields",
        json={"template_version_id": version_id, "overrides": {}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["is_complete"] is False
    assert payload["missing_fields"] == []
    assert payload["prerequisite_issues"] == {"missing_party_roles": ["buyer", "seller"]}


def test_generate_document_resolves_party_variables(monkeypatch) -> None:
    stub = install_stub(monkeypatch, NeonClientStub())
    folder_id = add_folder(stub)
    template_id = str(uuid4())
    version_id = str(uuid4())
    stub.tables["deal_folder_parties"].extend([
        {
            "id": str(uuid4()),
            "folder_id": folder_id,
            "org_id": ORG_ID,
            "party_role": "buyer",
            "full_name": "Ana Buyer",
            "email": "ana@example.com",
            "is_primary": True,
            "is_company": False,
            "kyc_verified": False,
            "created_at": "2026-06-13T00:00:00Z",
            "updated_at": "2026-06-13T00:00:00Z",
        },
        {
            "id": str(uuid4()),
            "folder_id": folder_id,
            "org_id": ORG_ID,
            "party_role": "seller",
            "full_name": "Luis Seller",
            "email": "luis@example.com",
            "is_primary": False,
            "is_company": False,
            "kyc_verified": False,
            "created_at": "2026-06-13T00:00:00Z",
            "updated_at": "2026-06-13T00:00:00Z",
        },
    ])
    stub.tables["document_templates"].append({
        "id": template_id,
        "org_id": ORG_ID,
        "name": "Contrato",
        "template_document_type": "contrato_compraventa",
        "status": "published",
    })
    stub.tables["document_template_versions"].append({
        "id": version_id,
        "org_id": ORG_ID,
        "template_id": template_id,
        "version_number": 1,
        "status": "published",
        "canonical_text": "Contrato entre {{ buyer_name }} y {{ seller_name }}",
    })
    stub.tables["document_template_fields"].extend([
        {
            "template_version_id": version_id,
            "field_key": "buyer_name",
            "label": "Comprador",
            "required": True,
            "source_path": "buyer.full_name",
        },
        {
            "template_version_id": version_id,
            "field_key": "seller_name",
            "label": "Vendedor",
            "required": True,
            "source_path": "seller.full_name",
        },
    ])

    response = client.post(
        f"/api/dms/folders/{folder_id}/generate-document",
        json={"template_version_id": version_id, "title": "Contrato", "generation_payload": {}},
    )

    assert response.status_code == 201
    body = response.json()
    assert "Ana Buyer" in body["preview"]
    assert body["document"]["current_version_id"]
    assert stub.tables["document_versions"][0]["validation_status"] == "pending"
