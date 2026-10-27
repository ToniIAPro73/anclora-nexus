"""Tests for advisor_contract_validator_service retry and Pydantic models.

Covers:
- ContractValidationRequest / ContractValidationResponse Pydantic models
- Exponential backoff retry logic (max 3 attempts)
- Command Center notification on exhausted retries
- Successful validation on first attempt
- Successful validation on second attempt (after one failure)
- project_ref routing header (Requirement 11.4)
"""

import os
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


import httpx
import pytest

from backend.services.advisor_contract_validator_service import (
    AdvisorContractValidatorService,
    ContractValidationRequest,
    ContractValidationResponse,
    ValidationIssue,
    _INITIAL_BACKOFF_SECONDS,
    _MAX_RETRIES,
)


# ---------------------------------------------------------------------------
# Pydantic model tests
# ---------------------------------------------------------------------------


class TestPydanticModels:
    def test_contract_validation_request_creates_valid_instance(self):
        req = ContractValidationRequest(
            document_id="doc-123",
            document_content="Contrato de compraventa...",
            document_type="compraventa",
            org_id="org-456",
        )
        assert req.document_id == "doc-123"
        assert req.document_type == "compraventa"
        assert req.org_id == "org-456"

    def test_contract_validation_response_defaults(self):
        resp = ContractValidationResponse(
            document_id="doc-123",
            block_signing=False,
        )
        assert resp.confidence == 0.0
        assert resp.issues == []

    def test_contract_validation_response_with_issues(self):
        resp = ContractValidationResponse(
            document_id="doc-123",
            block_signing=True,
            issues=[
                ValidationIssue(
                    code="MISSING_CLAUSE",
                    severity="critical",
                    description="Falta cláusula de penalización.",
                    clause_reference="Art. 7.2",
                )
            ],
            confidence=0.85,
        )
        assert resp.block_signing is True
        assert len(resp.issues) == 1
        assert resp.issues[0].code == "MISSING_CLAUSE"
        assert resp.issues[0].clause_reference == "Art. 7.2"

    def test_validation_issue_severity_default(self):
        issue = ValidationIssue(code="INFO_01", description="Minor note")
        assert issue.severity == "warning"
        assert issue.clause_reference is None


# ---------------------------------------------------------------------------
# Retry logic tests
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=MagicMock(),
                response=MagicMock(status_code=self.status_code),
            )

    def json(self):
        return self.payload


class TestValidateDocumentWithRetry:
    def _make_service(self, base_url="https://advisor.test", api_key="test-key", project_ref=None):
        return AdvisorContractValidatorService(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=5.0,
            project_ref=project_ref,
        )

    def _make_request(self):
        return ContractValidationRequest(
            document_id="doc-001",
            document_content="Contrato de arrendamiento completo.",
            document_type="arrendamiento",
            org_id="org-123",
        )

    @pytest.mark.asyncio
    async def test_successful_validation_first_attempt(self):
        service = self._make_service()
        request = self._make_request()

        mock_response = FakeResponse({
            "document_id": "doc-001",
            "block_signing": False,
            "issues": [],
            "confidence": 0.95,
        })

        with patch("backend.services.advisor_contract_validator_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await service.validate_document_with_retry(request)

        assert result.document_id == "doc-001"
        assert result.block_signing is False
        assert result.confidence == 0.95
        assert result.issues == []

    @pytest.mark.asyncio
    async def test_retry_succeeds_on_second_attempt(self):
        service = self._make_service()
        request = self._make_request()

        mock_response = FakeResponse({
            "document_id": "doc-001",
            "block_signing": True,
            "issues": [{"code": "ISSUE_1", "severity": "warning", "description": "Test"}],
            "confidence": 0.7,
        })

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.ConnectError("Connection refused")
            return mock_response

        with patch("backend.services.advisor_contract_validator_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                result = await service.validate_document_with_retry(request)

        assert result.block_signing is True
        assert result.confidence == 0.7
        assert len(result.issues) == 1
        assert call_count == 2
        mock_sleep.assert_called_once_with(_INITIAL_BACKOFF_SECONDS)

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_notifies_command_center(self):
        service = self._make_service()
        request = self._make_request()

        async def mock_post(*args, **kwargs):
            raise httpx.TimeoutException("Timeout")

        with patch("backend.services.advisor_contract_validator_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch.object(service, "_notify_command_center", new_callable=AsyncMock) as mock_notify:
                    result = await service.validate_document_with_retry(request)

        assert result.block_signing is True
        assert result.issues[0].code == "ADVISOR_UNREACHABLE"
        mock_notify.assert_called_once_with(
            org_id="org-123",
            document_id="doc-001",
            error=f"Attempt {_MAX_RETRIES}/{_MAX_RETRIES} failed: Timeout",
        )

    @pytest.mark.asyncio
    async def test_no_base_url_notifies_command_center(self):
        service = self._make_service(base_url="")
        request = self._make_request()

        with patch.object(service, "_notify_command_center", new_callable=AsyncMock) as mock_notify:
            result = await service.validate_document_with_retry(request)

        assert result.block_signing is True
        assert result.issues[0].code == "ADVISOR_UNREACHABLE"
        mock_notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_project_ref_sent_as_header(self):
        service = self._make_service(project_ref="lvpplnqbyvscpuljnzqf")
        request = self._make_request()

        captured_headers = {}

        mock_response = FakeResponse({
            "document_id": "doc-001",
            "block_signing": False,
            "issues": [],
            "confidence": 0.9,
        })

        async def mock_post(url, json, headers):
            captured_headers.update(headers)
            return mock_response

        with patch("backend.services.advisor_contract_validator_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await service.validate_document_with_retry(request)

        assert captured_headers.get("x-advisor-project-ref") == "lvpplnqbyvscpuljnzqf"
        assert captured_headers.get("x-advisor-internal-api-key") == "test-key"

    @pytest.mark.asyncio
    async def test_notify_command_center_inserts_alert(self):
        service = self._make_service()

        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = None
        mock_client = MagicMock()
        mock_client.table.return_value = mock_table

        mock_supa = MagicMock()
        mock_supa.client = mock_client

        with patch(
            "backend.services.neon_service.neon_service",
            mock_supa,
        ):
            await service._notify_command_center(
                org_id="org-123",
                document_id="doc-001",
                error="Connection refused",
            )

        mock_client.table.assert_called_with("automation_alerts")
        inserted_row = mock_table.insert.call_args[0][0]
        assert inserted_row["org_id"] == "org-123"
        assert inserted_row["severity"] == "critical"
        assert inserted_row["alert_type"] == "advisor_ai_unreachable"
        assert "doc-001" in inserted_row["message"]
        assert inserted_row["metadata_json"]["document_id"] == "doc-001"

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self):
        """Verifies backoff increases exponentially between retries."""
        service = self._make_service()
        request = self._make_request()

        async def mock_post(*args, **kwargs):
            raise httpx.ConnectError("refused")

        sleep_calls = []

        async def mock_sleep(seconds):
            sleep_calls.append(seconds)

        with patch("backend.services.advisor_contract_validator_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            with patch("asyncio.sleep", side_effect=mock_sleep):
                with patch.object(service, "_notify_command_center", new_callable=AsyncMock):
                    await service.validate_document_with_retry(request)

        # 3 retries → 2 sleep calls (no sleep after last failure)
        assert len(sleep_calls) == _MAX_RETRIES - 1
        assert sleep_calls[0] == _INITIAL_BACKOFF_SECONDS  # 60s
        assert sleep_calls[1] == _INITIAL_BACKOFF_SECONDS * 4.0  # 240s
