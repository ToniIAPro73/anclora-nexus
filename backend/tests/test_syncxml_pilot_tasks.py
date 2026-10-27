from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from backend.services.syncxml_pilot_service import (
    REAL_WRITE_BLOCK_REASON,
    SyncXmlApprovePayload,
    SyncXmlPilotPayload,
    syncxml_pilot_service,
)


class FakeQueryResult:
    def __init__(self, data):
        self.data = data


class FakeAccessRequestsTable:
    def __init__(self):
        self.rows = []
        self.insert_count = 0
        self._filters = []
        self._pending_update = {}

    def select(self, *_args, **_kwargs):
        self._filters = []
        return self

    def eq(self, field, value):
        self._filters.append((field, value))
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def insert(self, record):
        self.insert_count += 1
        stored = {**record, "id": f"ar_{self.insert_count}"}
        self.rows.append(stored)
        return FakeInsertQuery(stored)

    def update(self, data):
        self._pending_update = data
        return self

    def execute(self):
        if self._pending_update:
            target_id = next((value for field, value in self._filters if field == "id"), None)
            for index, row in enumerate(self.rows):
                if row.get("id") == target_id:
                    self.rows[index] = {**row, **self._pending_update}
                    updated = self.rows[index]
                    self._pending_update = {}
                    self._filters = []
                    return FakeQueryResult([updated])
            self._pending_update = {}
            self._filters = []
            return FakeQueryResult([])

        rows = self.rows
        for field, value in self._filters:
            rows = [row for row in rows if row.get(field) == value]
        self._filters = []
        return FakeQueryResult(rows)


class FakeInsertQuery:
    def __init__(self, record):
        self.record = record

    def execute(self):
        return FakeQueryResult([self.record])


def _payload(**overrides):
    base = SyncXmlPilotPayload(
        requestId="req_test",
        name="Ana Test",
        email="ana@example.com",
        accommodationType="Vivienda turística",
        estimatedMonthlyReservations="10-30",
        currentWorkflow="Excel manual",
        mainPain="Necesito revisar XML",
        wantsToValidate="Piloto con datos anonimizados",
        acceptsSyntheticOrAnonymizedData=True,
        acceptsPilotConditions=True,
    )
    data = base.model_dump()
    data.update(overrides)
    return data


def _configure_safe_settings(settings, *, app_env="staging", syncxml_env="staging", allow_real_write=False, synthetic_only=True, auto_approve=False):
    settings.APP_ENV = app_env
    settings.GUESTHUB_ENV = syncxml_env
    settings.ALLOW_REAL_NEON_WRITE = allow_real_write
    settings.USE_SYNTHETIC_DATA_ONLY = synthetic_only
    settings.GUESTHUB_PILOT_AUTO_APPROVE = auto_approve
    settings.PUBLIC_CTA_ORG_ID = "org_1"
    settings.LEGACY_SINGLE_TENANT_ORG_ID = None
    settings.GUESTHUB_INTERNAL_API_SECRET = "secret"
    settings.GUESTHUB_INTERNAL_API_URL = "https://syncxml.test/internal"
    settings.HERMES_WORKER_URL = ""
    settings.HERMES_WORKER_API_KEY = None


def _configure_production_settings(settings, *, auto_approve=False):
    _configure_safe_settings(
        settings,
        app_env="production",
        syncxml_env="production",
        allow_real_write=True,
        synthetic_only=False,
        auto_approve=auto_approve,
    )


@pytest.mark.asyncio
async def test_blocks_real_pilot_request_write_in_staging():
    with patch("backend.services.syncxml_pilot_service.neon_service") as neon, patch(
        "backend.services.syncxml_pilot_service.settings"
    ) as settings:
        _configure_safe_settings(settings)

        result = await syncxml_pilot_service.process_incoming_lead(_payload())

    assert result["blocked"] is True
    assert result["reason"] == REAL_WRITE_BLOCK_REASON
    assert result["action"] == "process_incoming_lead"
    assert result["environment"] == "staging"
    neon.client.table.assert_not_called()


@pytest.mark.asyncio
async def test_blocks_real_write_when_syncxml_environment_is_staging():
    with patch("backend.services.syncxml_pilot_service.neon_service") as neon, patch(
        "backend.services.syncxml_pilot_service.settings"
    ) as settings:
        _configure_safe_settings(settings, app_env="production", syncxml_env="staging", allow_real_write=True, synthetic_only=False)

        result = await syncxml_pilot_service.process_incoming_lead(_payload())

    assert result["blocked"] is True
    assert result["reason"] == REAL_WRITE_BLOCK_REASON
    assert result["syncxmlEnvironment"] == "staging"
    neon.client.table.assert_not_called()


@pytest.mark.asyncio
async def test_blocks_real_write_when_synthetic_only_is_enabled():
    with patch("backend.services.syncxml_pilot_service.neon_service") as neon, patch(
        "backend.services.syncxml_pilot_service.settings"
    ) as settings:
        _configure_safe_settings(settings, app_env="production", syncxml_env="production", allow_real_write=True, synthetic_only=True)

        result = await syncxml_pilot_service.process_incoming_lead(_payload())

    assert result["blocked"] is True
    assert result["useSyntheticDataOnly"] is True
    neon.client.table.assert_not_called()


def test_does_not_autoapprove_when_flag_is_false():
    payload = SyncXmlPilotPayload.model_validate(_payload())

    with patch("backend.services.syncxml_pilot_service.settings") as settings:
        _configure_safe_settings(settings, app_env="production", syncxml_env="production", allow_real_write=True, synthetic_only=False, auto_approve=False)
        decision = syncxml_pilot_service._decide_status(payload, {"decision": "approve", "score": 88, "riskFlags": []})

    assert decision == "pending"


@pytest.mark.asyncio
async def test_allows_production_flow_with_explicit_real_write_and_mocks():
    record = {"id": "ar_1", "org_id": "org_1", "email": "ana@example.com", "metadata": {}, "full_name": "Ana Test"}
    credentials = {
        "ok": True,
        "email": "ana@example.com",
        "temporaryPassword": "Tmp-123456",
        "credentialStatus": "created",
        "pilotUserId": "pilot_1",
        "loginReady": True,
        "status": "active",
    }

    with patch("backend.services.syncxml_pilot_service.neon_service") as neon, patch(
        "backend.services.syncxml_pilot_service.settings"
    ) as settings, patch.object(
        syncxml_pilot_service, "_create_syncxml_user", new=AsyncMock(return_value=credentials)
    ), patch.object(
        syncxml_pilot_service, "_send_safely", return_value=True
    ):
        _configure_safe_settings(settings, app_env="production", syncxml_env="production", allow_real_write=True, synthetic_only=False, auto_approve=True)

        access_table = Mock()
        task_table = Mock()
        neon.client.table.side_effect = lambda name: access_table if name == "access_requests" else task_table
        access_table.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        access_table.insert.return_value.execute.return_value.data = [record]
        access_table.update.return_value.eq.return_value.execute.return_value.data = [{**record, "status": "approved", "metadata": {}}]

        result = await syncxml_pilot_service.process_incoming_lead(_payload())

    assert result["id"] == "ar_1"
    assert result["status"] == "approved"
    neon.client.table.assert_called()
    task_table.insert.assert_not_called()


@pytest.mark.asyncio
async def test_syncxml_same_idempotency_key_does_not_duplicate():
    access_table = FakeAccessRequestsTable()
    task_table = Mock()

    with patch("backend.services.syncxml_pilot_service.neon_service") as neon, patch(
        "backend.services.syncxml_pilot_service.settings"
    ) as settings, patch.object(
        syncxml_pilot_service, "_create_review_task", new=AsyncMock()
    ):
        _configure_production_settings(settings)
        neon.client.table.side_effect = lambda name: access_table if name == "access_requests" else task_table

        first = await syncxml_pilot_service.process_incoming_lead(
            _payload(
                requestId="same-request",
                raw={"idempotency_key": "same-request", "adminEmailSentBySyncxml": True},
            )
        )
        second = await syncxml_pilot_service.process_incoming_lead(
            _payload(
                requestId="same-request",
                raw={"idempotency_key": "same-request", "adminEmailSentBySyncxml": True},
            )
        )

    assert first["id"] == second["id"]
    assert access_table.insert_count == 1


@pytest.mark.asyncio
async def test_syncxml_same_email_different_idempotency_key_creates_two_rows():
    access_table = FakeAccessRequestsTable()
    task_table = Mock()

    with patch("backend.services.syncxml_pilot_service.neon_service") as neon, patch(
        "backend.services.syncxml_pilot_service.settings"
    ) as settings, patch.object(
        syncxml_pilot_service, "_create_review_task", new=AsyncMock()
    ):
        _configure_production_settings(settings)
        neon.client.table.side_effect = lambda name: access_table if name == "access_requests" else task_table

        first = await syncxml_pilot_service.process_incoming_lead(
            _payload(
                requestId="request-one",
                email="same@example.com",
                raw={"idempotency_key": "request-one", "adminEmailSentBySyncxml": True},
            )
        )
        second = await syncxml_pilot_service.process_incoming_lead(
            _payload(
                requestId="request-two",
                email="same@example.com",
                raw={"idempotency_key": "request-two", "adminEmailSentBySyncxml": True},
            )
        )

    assert first["id"] != second["id"]
    assert access_table.insert_count == 2
    assert [row["idempotency_key"] for row in access_table.rows] == ["request-one", "request-two"]


@pytest.mark.asyncio
async def test_syncxml_webhook_persists_explicit_access_request_contract_fields():
    access_table = FakeAccessRequestsTable()
    task_table = Mock()

    with patch("backend.services.syncxml_pilot_service.neon_service") as neon, patch(
        "backend.services.syncxml_pilot_service.settings"
    ) as settings, patch.object(
        syncxml_pilot_service, "_create_review_task", new=AsyncMock()
    ):
        _configure_production_settings(settings)
        neon.client.table.side_effect = lambda name: access_table if name == "access_requests" else task_table

        await syncxml_pilot_service.process_incoming_lead(
            _payload(
                requestId="contract-request",
                raw={"idempotency_key": "contract-request", "adminEmailSentBySyncxml": True},
            )
        )

    record = access_table.rows[0]
    assert record["product"] == "syncxml"
    assert record["source"] == "syncxml_landing"
    assert record["request_type"] == "pilot_request"
    assert record["intake_domain"] == "access_request"
    assert record["routing_target_domain"] == "access_requests"


@pytest.mark.asyncio
async def test_syncxml_webhook_without_own_sample_stays_pending_and_marks_sample_attachments():
    access_table = FakeAccessRequestsTable()
    task_table = Mock()

    with patch("backend.services.syncxml_pilot_service.neon_service") as neon, patch(
        "backend.services.syncxml_pilot_service.settings"
    ) as settings, patch.object(
        syncxml_pilot_service, "_create_review_task", new=AsyncMock()
    ):
        _configure_production_settings(settings)
        neon.client.table.side_effect = lambda name: access_table if name == "access_requests" else task_table

        result = await syncxml_pilot_service.process_incoming_lead(
            _payload(
                requestId="no-own-sample",
                acceptsSyntheticOrAnonymizedData=False,
                raw={"idempotency_key": "no-own-sample", "adminEmailSentBySyncxml": True},
            )
        )

    record = access_table.rows[0]
    assert result["status"] == "pending"
    assert record["gdpr_consent"] is True
    assert record["metadata"]["acceptsSyntheticOrAnonymizedData"] is False
    assert record["metadata"]["needsSyntheticSampleAttachments"] is True
    assert record["metadata"]["has_own_synthetic_or_anonymized_sample"] is False


@pytest.mark.asyncio
async def test_block_reason_is_clear_for_manual_approval():
    with patch("backend.services.syncxml_pilot_service.settings") as settings:
        _configure_safe_settings(settings)
        result = await syncxml_pilot_service.approve_manual("org_1", "req_1", "reviewer_1", SyncXmlApprovePayload())

    assert result == {
        "ok": False,
        "blocked": True,
        "reason": REAL_WRITE_BLOCK_REASON,
        "action": "approve_manual",
        "environment": "staging",
        "syncxmlEnvironment": "staging",
        "allowRealNeonWrite": False,
        "useSyntheticDataOnly": True,
    }


def test_hermes_local_validation_still_works_without_writes():
    payload = SyncXmlPilotPayload.model_validate(_payload())

    result = syncxml_pilot_service._score_locally(payload)

    assert result["decision"] == "approve"
    assert result["recommendedNextAction"] == "approve_pilot"


@pytest.mark.asyncio
async def test_syncxml_user_creation_defaults_temporary_password_to_seven_days():
    record = {
        "id": "ar_1",
        "email": "ana@example.com",
        "full_name": "Ana Test",
    }
    sent = {}

    class FakeResponse:
        is_success = True

        @staticmethod
        def json():
            return {
                "ok": True,
                "email": "ana@example.com",
                "temporaryPassword": "Tmp-123456",
                "loginReady": True,
                "status": "active",
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, json, headers, timeout):
            sent.update({"url": url, "json": json, "headers": headers, "timeout": timeout})
            return FakeResponse()

    with patch("backend.services.syncxml_pilot_service.settings") as settings, patch(
        "backend.services.syncxml_pilot_service.httpx.AsyncClient", return_value=FakeClient()
    ):
        _configure_safe_settings(settings, app_env="production", syncxml_env="production", allow_real_write=True, synthetic_only=False)
        credentials = await syncxml_pilot_service._create_syncxml_user(record, SyncXmlApprovePayload())

    assert credentials["expiresAt"] == sent["json"]["expiresAt"]
    expires_at = datetime.fromisoformat(sent["json"]["expiresAt"].replace("Z", "+00:00"))
    remaining = expires_at - datetime.now(timezone.utc)
    assert 6 <= remaining.days <= 7
    assert sent["json"]["rotatePassword"] is False


@pytest.mark.asyncio
async def test_provisioning_without_login_ready_does_not_send_acceptance_email():
    record = {"id": "ar_1", "org_id": "org_1", "email": "ana@example.com", "metadata": {}, "full_name": "Ana Test"}
    credentials = {
        "ok": True,
        "email": "ana@example.com",
        "temporaryPassword": "Tmp-123456",
        "status": "active",
        "loginReady": False,
        "code": "SYNCXML_PILOT_AUTH_CONFIG_INCOMPLETE",
    }

    with patch("backend.services.syncxml_pilot_service.settings") as settings, patch.object(
        syncxml_pilot_service, "_create_syncxml_user", new=AsyncMock(return_value=credentials)
    ), patch.object(
        syncxml_pilot_service, "_send_safely", return_value=True
    ) as send_safely, patch.object(
        syncxml_pilot_service, "_create_review_task", new=AsyncMock()
    ), patch.object(
        syncxml_pilot_service,
        "_update_request",
        side_effect=lambda _request_id, data: {**record, **data},
    ):
        _configure_production_settings(settings)
        result = await syncxml_pilot_service._approve_with_credentials(
            record,
            SyncXmlApprovePayload(),
            reviewer_id="reviewer_1",
        )

    assert result["ok"] is False
    assert result["status"] == "failed_credentials"
    assert send_safely.call_count == 1
    assert send_safely.call_args.args[2] == "credential_creation_failed"


@pytest.mark.asyncio
async def test_provisioning_same_active_user_retry_without_password_rotates_password_and_approves():
    record = {"id": "ar_1", "org_id": "org_1", "email": "ana@example.com", "metadata": {}, "full_name": "Ana Test"}
    existing_credentials = {
        "ok": True,
        "email": "ana@example.com",
        "temporaryPassword": None,
        "status": "active",
        "loginReady": True,
    }
    rotated_credentials = {
        "ok": True,
        "email": "ana@example.com",
        "temporaryPassword": "Tmp-123456",
        "status": "active",
        "loginReady": True,
        "userId": "pilot_1",
    }
    create_syncxml_user = AsyncMock(side_effect=[existing_credentials, rotated_credentials])

    with patch("backend.services.syncxml_pilot_service.settings") as settings, patch.object(
        syncxml_pilot_service, "_create_syncxml_user", new=create_syncxml_user
    ), patch.object(
        syncxml_pilot_service, "_send_safely", return_value=True
    ) as send_safely, patch.object(
        syncxml_pilot_service, "_create_review_task", new=AsyncMock()
    ), patch.object(
        syncxml_pilot_service,
        "_update_request",
        side_effect=lambda _request_id, data: {**record, **data},
    ):
        _configure_production_settings(settings)
        result = await syncxml_pilot_service._approve_with_credentials(
            record,
            SyncXmlApprovePayload(),
            reviewer_id="reviewer_1",
        )

    assert result["ok"] is True
    assert result["status"] == "approved"
    assert create_syncxml_user.call_count == 2
    assert create_syncxml_user.call_args_list[0].args[1].rotatePassword is False
    assert create_syncxml_user.call_args_list[1].args[1].rotatePassword is True
    assert send_safely.call_count == 1
    assert send_safely.call_args.args[2] == "acceptance_email_failed"
