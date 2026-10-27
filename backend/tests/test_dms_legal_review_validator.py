"""Tests for validate_legal_document() extension on AdvisorContractValidatorService."""

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock


# Stub pydantic_settings and backend.config before import so no deps needed
_fake_settings = MagicMock()
_fake_settings.ADVISOR_AI_BASE_URL = ""
_fake_settings.ADVISOR_AI_INTERNAL_API_KEY = None
_fake_settings.ADVISOR_AI_TIMEOUT_SECONDS = 30.0
sys.modules.setdefault("pydantic_settings", MagicMock())
_config_mod = MagicMock()
_config_mod.settings = _fake_settings
_orig_config_mod = sys.modules.get("backend.config")
sys.modules["backend.config"] = _config_mod

from backend.services.advisor_contract_validator_service import AdvisorContractValidatorService  # noqa: E402

# Restore the real backend.config for every other test module imported after
# this one — the stub must only be visible while importing the service above.
if _orig_config_mod is not None:
    sys.modules["backend.config"] = _orig_config_mod
else:
    del sys.modules["backend.config"]

VALID_LEGAL_DOCUMENT_RESPONSE = {
    "status": "ok",
    "block_signing": False,
    "risk_level": "low",
    "review_requirement": "none",
    "confidence": 0.9,
    "summary": "Documento conforme.",
    "findings": [],
    "required_actions": [],
    "missing_clauses": [],
    "differences": [],
    "legal_disclaimer": "No sustituye asesor.",
    "sources": [],
    "document_id": "doc-42",
    "validation_timestamp": "2026-06-13T10:00:00Z",
    "rag_sources_used": 3,
}


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class FakeAsyncClient:
    calls: list = []
    response = FakeResponse({})

    def __init__(self, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url, json, headers):
        FakeAsyncClient.calls.append(SimpleNamespace(url=url, json=json, headers=headers))
        return FakeAsyncClient.response


def test_validate_legal_document_happy_path(monkeypatch):
    FakeAsyncClient.calls = []
    FakeAsyncClient.response = FakeResponse(VALID_LEGAL_DOCUMENT_RESPONSE)
    monkeypatch.setattr(
        "backend.services.advisor_contract_validator_service.httpx.AsyncClient",
        FakeAsyncClient,
    )
    service = AdvisorContractValidatorService(
        base_url="https://advisor.test",
        api_key="internal-key",
        timeout_seconds=5,
    )

    result = asyncio.run(service.validate_legal_document(
        document_text="Contrato de compraventa completo con precio, partes, notaría y fecha.",
        document_type="contrato_compraventa",
        jurisdiction="España",
        language="es",
        document_id="doc-42",
        org_id="org-1",
    ))

    assert result["status"] == "ok"
    assert result["advisor_available"] is True
    assert result["risk_level"] == "low"
    assert result["rag_sources_used"] == 3
    assert FakeAsyncClient.calls[0].url == "https://advisor.test/api/legal-documents/validate"
    assert FakeAsyncClient.calls[0].json["currentText"].startswith("Contrato")
    assert "canonicalText" not in FakeAsyncClient.calls[0].json
    assert FakeAsyncClient.calls[0].headers["x-advisor-internal-api-key"] == "internal-key"


def test_validate_legal_document_sends_canonical_template(monkeypatch):
    FakeAsyncClient.calls = []
    FakeAsyncClient.response = FakeResponse(VALID_LEGAL_DOCUMENT_RESPONSE)
    monkeypatch.setattr(
        "backend.services.advisor_contract_validator_service.httpx.AsyncClient",
        FakeAsyncClient,
    )
    service = AdvisorContractValidatorService(
        base_url="https://advisor.test",
        api_key="key",
        timeout_seconds=5,
    )

    asyncio.run(service.validate_legal_document(
        document_text="Contrato con variaciones.",
        document_type="arras",
        canonical_template="Contrato canónico de arras.",
        jurisdiction="España",
        language="es",
    ))

    assert "canonicalText" in FakeAsyncClient.calls[0].json
    assert FakeAsyncClient.calls[0].json["canonicalText"] == "Contrato canónico de arras."


def test_validate_legal_document_safe_failure_no_url():
    service = AdvisorContractValidatorService(base_url="", api_key=None)

    result = asyncio.run(service.validate_legal_document(
        document_text="Cualquier texto.",
        document_type="generico",
    ))

    assert result["status"] == "review_required"
    assert result["advisor_available"] is False
    assert result["block_signing"] is True


def test_validate_legal_document_safe_failure_network_error(monkeypatch):
    class ErrorClient:
        def __init__(self, timeout): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_): return None
        async def post(self, *args, **kwargs):
            raise ConnectionError("Network unreachable")

    monkeypatch.setattr(
        "backend.services.advisor_contract_validator_service.httpx.AsyncClient",
        ErrorClient,
    )
    service = AdvisorContractValidatorService(
        base_url="https://advisor.test",
        api_key="key",
        timeout_seconds=5,
    )

    result = asyncio.run(service.validate_legal_document(
        document_text="Texto de prueba.",
        document_type="generico",
    ))

    assert result["status"] == "review_required"
    assert result["advisor_available"] is False
    assert result["block_signing"] is True
    assert "error" in result


def test_validate_legal_document_normalizes_block_signing(monkeypatch):
    high_risk_response = {
        **VALID_LEGAL_DOCUMENT_RESPONSE,
        "status": "review_required",
        "block_signing": True,
        "risk_level": "critical",
        "review_requirement": "urgent",
    }
    FakeAsyncClient.calls = []
    FakeAsyncClient.response = FakeResponse(high_risk_response)
    monkeypatch.setattr(
        "backend.services.advisor_contract_validator_service.httpx.AsyncClient",
        FakeAsyncClient,
    )
    service = AdvisorContractValidatorService(
        base_url="https://advisor.test",
        api_key="key",
        timeout_seconds=5,
    )

    result = asyncio.run(service.validate_legal_document(
        document_text="Documento con riesgo crítico.",
        document_type="compraventa",
    ))

    assert result["block_signing"] is True
    assert result["risk_level"] == "critical"
    assert result["review_requirement"] == "urgent"
