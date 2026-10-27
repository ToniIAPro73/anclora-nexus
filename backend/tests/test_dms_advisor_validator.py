import os
import asyncio
from types import SimpleNamespace


from backend.services.advisor_contract_validator_service import AdvisorContractValidatorService


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
    calls = []
    response = FakeResponse({})

    def __init__(self, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url, json, headers):
        self.calls.append(SimpleNamespace(url=url, json=json, headers=headers, timeout=self.timeout))
        return self.response


def test_advisor_validator_posts_expected_payload(monkeypatch):
    FakeAsyncClient.calls = []
    FakeAsyncClient.response = FakeResponse({
        "status": "ok",
        "block_signing": False,
        "confidence": 0.91,
        "summary": "OK",
        "findings": [],
        "required_actions": [],
        "missing_documents": [],
        "legal_disclaimer": "No sustituye abogado.",
        "sources": [],
    })
    monkeypatch.setattr("backend.services.advisor_contract_validator_service.httpx.AsyncClient", FakeAsyncClient)
    service = AdvisorContractValidatorService(
        base_url="https://advisor.test",
        api_key="internal-test-key",
        timeout_seconds=3,
    )

    result = asyncio.run(service.validate_contract(
        contract_text="Contrato de compraventa completo.",
        contract_type="contrato_compraventa",
        operation_type="compraventa",
        jurisdiction="ES-IB",
        language="es",
        metadata={"document_id": "doc-1"},
    ))

    assert result["status"] == "ok"
    assert result["advisor_available"] is True
    assert FakeAsyncClient.calls[0].url == "https://advisor.test/api/validate-contract"
    assert FakeAsyncClient.calls[0].json["contractText"].startswith("Contrato")
    assert FakeAsyncClient.calls[0].headers["X-Anclora-Internal-Key"] == "internal-test-key"


def test_advisor_validator_degrades_when_not_configured():
    service = AdvisorContractValidatorService(base_url="", api_key=None)

    result = asyncio.run(service.validate_contract(
        contract_text="Contrato",
        contract_type=None,
        operation_type="compraventa",
        jurisdiction="ES",
        language="es",
        metadata={},
    ))

    assert result["status"] == "review_required"
    assert result["advisor_available"] is False
    assert result["block_signing"] is True
