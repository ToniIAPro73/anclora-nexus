import os
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("NEXUS_DOCUMENT_ENCRYPTION_KEY", "00" * 32)

from backend.api.deps import get_current_user, get_org_id
from backend.api.routes.dms import require_dms_membership, router
from backend.tests.test_dms_routes import ORG_ID, USER_ID, NeonClientStub, add_document, add_folder, install_stub


app = FastAPI()
app.include_router(router, prefix="/api/dms")
app.dependency_overrides[get_org_id] = lambda: ORG_ID
app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=USER_ID)
app.dependency_overrides[require_dms_membership] = lambda: {"id": str(uuid4()), "role": "manager", "status": "active"}
client = TestClient(app)


def test_signed_document_is_immutable_for_validation(monkeypatch):
    stub = install_stub(monkeypatch, NeonClientStub())
    folder_id = add_folder(stub)
    document = add_document(stub, folder_id)
    document["legal_metadata"]["immutable"] = True

    response = client.post(f"/api/dms/documents/{document['id']}/validate", json={})

    assert response.status_code == 409
    assert "immutable" in response.json()["detail"]
