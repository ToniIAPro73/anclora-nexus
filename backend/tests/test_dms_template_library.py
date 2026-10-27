"""Integration tests for the template library routes (TestClient, Neon mocked)."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("NEXUS_DOCUMENT_ENCRYPTION_KEY", "00" * 32)
os.environ.setdefault("ADVISOR_AI_BASE_URL", "")

# Stub heavy transitive deps before importing routes
for _mod in [
    "pydantic_settings",
    "neon",
    "sqlalchemy",
    "sqlalchemy.orm",
    "sqlalchemy.ext",
    "sqlalchemy.ext.declarative",
]:
    sys.modules.setdefault(_mod, MagicMock())

_fake_settings = MagicMock()
_fake_settings.NEXUS_DMS_BUCKET = "dms"
_fake_settings.NEXUS_DMS_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_config_mod = MagicMock()
_config_mod.settings = _fake_settings
_orig_config_mod = sys.modules.get("backend.config")
sys.modules["backend.config"] = _config_mod

from backend.api.routes.dms_templates import router as templates_router  # noqa: E402

# Restore the real backend.config for every other test module imported after
# this one — the stub must only be visible while importing the routes above.
if _orig_config_mod is not None:
    sys.modules["backend.config"] = _orig_config_mod
else:
    del sys.modules["backend.config"]

app = FastAPI()
app.include_router(templates_router, prefix="/api/dms/templates")


MOCK_USER_ID = "user-uuid-abc"
MOCK_ORG_ID = "org-uuid-xyz"

SAMPLE_TEMPLATE = {
    "id": "tmpl-1",
    "org_id": MOCK_ORG_ID,
    "name": "Contrato de Arras",
    "template_document_type": "arras_penitenciales",
    "description": "Modelo estándar de arras.",
    "jurisdiction": "España",
    "language": "es",
    "is_global": False,
    "status": "draft",
    "created_at": "2026-06-01T00:00:00Z",
}


def _make_client():
    from backend.api import deps, middleware
    app.dependency_overrides[deps.get_current_user] = lambda: MagicMock(id=MOCK_USER_ID)
    app.dependency_overrides[deps.get_org_id] = lambda: MOCK_ORG_ID
    app.dependency_overrides[middleware.verify_org_membership] = lambda: {"org_id": MOCK_ORG_ID}
    return TestClient(app, raise_server_exceptions=True)


def _mock_neon_table(data: list, insert_data: list | None = None):
    table_mock = MagicMock()
    query_mock = MagicMock()
    query_mock.select.return_value = query_mock
    query_mock.eq.return_value = query_mock
    query_mock.or_.return_value = query_mock
    query_mock.order.return_value = query_mock
    query_mock.limit.return_value = query_mock
    query_mock.execute.return_value = MagicMock(data=data)
    insert_response = MagicMock(data=insert_data or data)
    query_mock.insert.return_value = MagicMock(execute=lambda: insert_response)
    query_mock.update.return_value = query_mock
    table_mock.return_value = query_mock
    return table_mock


@pytest.fixture
def client():
    return _make_client()


# ── List templates ─────────────────────────────────────────────────────────────

def test_list_templates_returns_list(client):
    with patch(
        "backend.api.routes.dms_templates._table",
        side_effect=lambda name: _mock_neon_table([SAMPLE_TEMPLATE])(),
    ):
        response = client.get("/api/dms/templates/")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)


# ── Create template ────────────────────────────────────────────────────────────

def test_create_template_returns_created_object(client):
    with patch(
        "backend.api.routes.dms_templates._table",
        side_effect=lambda name: _mock_neon_table([SAMPLE_TEMPLATE])(),
    ):
        response = client.post(
            "/api/dms/templates/",
            json={
                "name": "Contrato de Arras",
                "template_document_type": "arras_penitenciales",
                "jurisdiction": "España",
                "language": "es",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Contrato de Arras"
    assert body["status"] == "draft"


# ── Get template ───────────────────────────────────────────────────────────────

def test_get_template_by_id(client):
    with patch(
        "backend.api.routes.dms_templates._fetch_template",
        return_value=SAMPLE_TEMPLATE,
    ):
        response = client.get(f"/api/dms/templates/{SAMPLE_TEMPLATE['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "tmpl-1"


def test_get_template_not_found(client):
    with patch(
        "backend.api.routes.dms_templates._fetch_template",
        return_value=None,
    ):
        response = client.get("/api/dms/templates/nonexistent")
    assert response.status_code == 404


# ── Publish template ───────────────────────────────────────────────────────────

def test_publish_template_transitions_status(client):
    published = {**SAMPLE_TEMPLATE, "status": "published", "published_at": "2026-06-13T00:00:00Z"}
    with (
        patch("backend.api.routes.dms_templates._fetch_template", return_value={**SAMPLE_TEMPLATE, "org_id": MOCK_ORG_ID}),
        patch("backend.api.routes.dms_templates._table", side_effect=lambda name: _mock_neon_table([published])()),
    ):
        response = client.patch(f"/api/dms/templates/{SAMPLE_TEMPLATE['id']}/publish")
    assert response.status_code == 200


# ── Deprecate template ─────────────────────────────────────────────────────────

def test_deprecate_template(client):
    deprecated = {**SAMPLE_TEMPLATE, "status": "deprecated"}
    with (
        patch("backend.api.routes.dms_templates._fetch_template", return_value={**SAMPLE_TEMPLATE, "org_id": MOCK_ORG_ID}),
        patch("backend.api.routes.dms_templates._table", side_effect=lambda name: _mock_neon_table([deprecated])()),
    ):
        response = client.patch(f"/api/dms/templates/{SAMPLE_TEMPLATE['id']}/deprecate")
    assert response.status_code == 200


# ── List versions ──────────────────────────────────────────────────────────────

def test_list_template_versions(client):
    version = {"id": "ver-1", "template_id": "tmpl-1", "version_number": 1, "immutable": False}
    with (
        patch("backend.api.routes.dms_templates._fetch_template", return_value=SAMPLE_TEMPLATE),
        patch("backend.api.routes.dms_templates._table", side_effect=lambda name: _mock_neon_table([version])()),
    ):
        response = client.get(f"/api/dms/templates/{SAMPLE_TEMPLATE['id']}/versions")
    assert response.status_code == 200
    assert len(response.json()) == 1
