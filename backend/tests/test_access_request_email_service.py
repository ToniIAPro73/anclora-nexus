import re
from io import BytesIO
from zipfile import ZipFile

import pytest

from backend.config import settings
from backend.services import access_request_email_service as email_service_module
from backend.services.access_request_email_service import (
    build_access_request_approved_email,
    build_access_request_rejected_email,
    build_syncxml_pilot_acceptance_email,
)


def record(
    product: str = "synergi",
    rejection_reason: str | None = None,
    **provisioning: object,
) -> dict:
    return {
        "id": "request-1",
        "product": product,
        "full_name": "Toni Test",
        "email": "toni@example.com",
        "rejection_reason": rejection_reason,
        **provisioning,
    }


def assert_non_empty_bodies(payload: dict) -> None:
    assert payload["text"].strip()
    assert payload["html"].strip()
    assert "<table" in payload["html"]


def worksheet_xml(xlsx_content: bytes) -> str:
    with ZipFile(BytesIO(xlsx_content)) as archive:
        return archive.read("xl/worksheets/sheet1.xml").decode("utf-8")


def test_approval_email_for_synergi_includes_product_recipient_subject_and_name() -> None:
    payload = build_access_request_approved_email(record("synergi"))

    assert payload["to"] == "toni@example.com"
    assert payload["subject"] == "Anclora Nexus · Solicitud aprobada — Anclora Synergi"
    assert "Synergi" in payload["text"]
    assert "Toni Test" in payload["text"]
    assert_non_empty_bodies(payload)


def test_approval_email_for_data_lab_includes_product_recipient_subject_and_name() -> None:
    payload = build_access_request_approved_email(record("data_lab"))

    assert payload["to"] == "toni@example.com"
    assert "Data Lab" in payload["subject"]
    assert "Data Lab" in payload["text"]
    assert "Toni Test" in payload["text"]
    assert_non_empty_bodies(payload)


@pytest.mark.parametrize("product", ["data_lab", "guesthub", "synergi"])
def test_decision_email_uses_nexus_branding_and_product_context(product: str) -> None:
    payload = build_access_request_approved_email(record(product, provisioning_case="CASO_A"))

    assert "Anclora Nexus" in payload["subject"]
    assert "Anclora Nexus" in payload["html"]
    assert f"Anclora {('Data Lab' if product == 'data_lab' else 'GuestHub' if product == 'guesthub' else 'Synergi')}" in payload["text"]
    assert "Anclora SyncXML" not in payload["html"]
    assert "Piloto controlado" not in payload["html"]
    assert "No se ha creado ninguna cuenta externa" not in payload["text"]


def test_guesthub_product_keeps_product_context_under_nexus_branding() -> None:
    payload = build_access_request_approved_email(record("guesthub", provisioning_case="CASO_A"))

    assert payload["subject"] == "Anclora Nexus · Solicitud aprobada — Anclora GuestHub"
    assert "Anclora Nexus" in payload["html"]
    assert "Anclora GuestHub" in payload["text"]


def test_approval_case_a_mentions_identity_activation() -> None:
    payload = build_access_request_approved_email(
        record("data_lab", provisioning_case="CASO_A", provisioning_status="invite_ready")
    )

    assert "Anclora Identity" in payload["text"]
    assert "activar tu cuenta" in payload["text"]
    assert "Una vez completada la activación" in payload["text"]
    assert "Anclora Identity" in payload["html"]


def test_approval_case_b_mentions_existing_identity() -> None:
    payload = build_access_request_approved_email(
        record("data_lab", provisioning_case="CASO_B", provisioning_status="provisioned")
    )

    assert "identidad Anclora existente" in payload["text"]
    assert "cuenta habitual" in payload["text"]
    assert "Anclora Identity" not in payload["text"]


def test_approval_pending_does_not_claim_provisioning_completed() -> None:
    payload = build_access_request_approved_email(record("synergi", provisioning_status="pending"))

    assert "estamos preparando tu acceso" in payload["text"]
    assert "Te avisaremos" in payload["text"]
    assert "Anclora Identity" not in payload["text"]


def test_approval_failed_hides_technical_details() -> None:
    payload = build_access_request_approved_email(
        record(
            "guesthub",
            provisioning_case="ERROR",
            provisioning_status="failed",
            provisioning_error="Identity lookup failed with HTTP 502",
            admin_notes="internal reviewer note",
        )
    )

    assert "no hemos podido completar automáticamente" in payload["text"]
    assert "HTTP 502" not in payload["text"]
    assert "internal reviewer note" not in payload["text"]
    assert "Identity lookup failed" not in payload["html"]


def test_rejection_email_includes_rejection_reason_when_present() -> None:
    payload = build_access_request_rejected_email(
        record("synergi", rejection_reason="Insufficient service coverage")
    )

    assert payload["subject"] == "Anclora Nexus · Solicitud no aprobada — Anclora Synergi"
    assert "Insufficient service coverage" in payload["text"]
    assert "Insufficient service coverage" in payload["html"]
    assert "Anclora Nexus" in payload["html"]
    assert_non_empty_bodies(payload)


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_rejection_email_handles_missing_or_empty_reason(reason) -> None:
    payload = build_access_request_rejected_email(record("data_lab", rejection_reason=reason))

    assert payload["to"] == "toni@example.com"
    assert "Data Lab" in payload["subject"]
    assert "Toni Test" in payload["text"]
    assert_non_empty_bodies(payload)


@pytest.mark.parametrize("product", ["data_lab", "guesthub", "synergi"])
def test_rejection_email_is_product_aware_without_changing_nexus_sender(product: str) -> None:
    payload = build_access_request_rejected_email(
        record(product, rejection_reason="Public reason", admin_notes="Do not expose this")
    )

    assert payload["subject"] == f"Anclora Nexus · Solicitud no aprobada — Anclora {('Data Lab' if product == 'data_lab' else 'GuestHub' if product == 'guesthub' else 'Synergi')}"
    assert "Anclora Nexus" in payload["html"]
    assert "Public reason" in payload["text"]
    assert "Do not expose this" not in payload["text"]
    assert "Do not expose this" not in payload["html"]
    assert "Anclora SyncXML" not in payload["html"]


def test_decision_email_uses_nexus_sender_even_when_legacy_display_name_is_configured(monkeypatch) -> None:
    sent = {}
    monkeypatch.setattr(settings, "RESEND_FROM", "Anclora SyncXML <no-reply@anclora.com>")
    monkeypatch.setattr(settings, "RESEND_FROM_EMAIL", None)
    monkeypatch.setattr(
        email_service_module,
        "get_email_transport_summary",
        lambda: {"native_email_enabled": True, "provider": "resend"},
    )

    def fake_send_email_native(**kwargs):
        sent.update(kwargs)
        return {"provider": "resend", "message_id": "msg-1"}

    monkeypatch.setattr(email_service_module, "send_email_native", fake_send_email_native)
    result = email_service_module.access_request_email_service.send_decision_email(
        {**record("data_lab", provisioning_case="CASO_A"), "status": "approved"}
    )

    assert result["status"] == "sent"
    assert sent["from_email"] == "Anclora Nexus <no-reply@anclora.com>"
    assert sent["subject"] == "Anclora Nexus · Solicitud aprobada — Anclora Data Lab"


def test_syncxml_acceptance_email_uses_human_expiry_and_first_login_instruction() -> None:
    payload = build_syncxml_pilot_acceptance_email(
        record("syncxml"),
        {
            "email": "toni@example.com",
            "temporaryPassword": "Tmp-123456",
            "expiresAt": "2026-06-28T01:53:42.673404Z",
            "loginReady": True,
            "status": "active",
        },
    )

    assert "Caducidad/revisión" not in payload["text"]
    assert "Caducidad/revisión" not in payload["html"]
    assert "2026-06-28T01:53:42.673404Z" not in payload["text"]
    assert "2026-06-28T01:53:42.673404Z" not in payload["html"]
    expected_expiry = (
        "Tu acceso temporal estará disponible hasta el domingo, 28 de junio de 2026, "
        "a las 03:53 h (hora peninsular española)."
    )
    assert expected_expiry in payload["text"]
    assert expected_expiry in payload["html"]
    assert "Al iniciar sesión por primera vez" in payload["text"]
    assert "Al iniciar sesión por primera vez" in payload["html"]
    assert "Acceder al piloto" in payload["html"]
    assert_non_empty_bodies(payload)


def test_syncxml_acceptance_email_adds_sample_workbooks_when_applicant_has_no_sample() -> None:
    payload = build_syncxml_pilot_acceptance_email(
        {
            **record("syncxml"),
            "metadata": {
                "acceptsSyntheticOrAnonymizedData": False,
                "raw": {"needsSyntheticSampleAttachments": True},
            },
        },
        {
            "email": "toni@example.com",
            "temporaryPassword": "Tmp-123456",
            "expiresAt": "2026-06-28T01:53:42.673404Z",
            "loginReady": True,
            "status": "active",
        },
    )

    assert "adjuntamos dos Excel" in payload["text"]
    assert "attachments" in payload
    assert [item["filename"] for item in payload["attachments"]] == [
        "anclora-guesthub-muestra-correcta.xlsx",
        "anclora-guesthub-muestra-subsanable.xlsx",
    ]
    assert all(item["content"].startswith(b"PK") for item in payload["attachments"])

    valid_xml = worksheet_xml(payload["attachments"][0]["content"])
    fixable_xml = worksheet_xml(payload["attachments"][1]["content"])

    assert re.search(r"NUMERO DE PERSONAS</t></is></c><c r=\"B13\"[^>]*><is><t>2</t>", valid_xml)
    assert re.search(r"NUMERO DE PERSONAS</t></is></c><c r=\"B13\"[^>]*><is><t>3</t>", fixable_xml)
    assert "ES9121000418450200051332" in valid_xml
    assert "ES9121000418450200051332" in fixable_xml
    assert "Titular" not in valid_xml
    assert "Acompañante" not in valid_xml
    assert "Titular" not in fixable_xml
    assert "Acompañante" not in fixable_xml


def test_syncxml_acceptance_email_omits_sample_workbooks_when_applicant_has_sample() -> None:
    payload = build_syncxml_pilot_acceptance_email(
        {
            **record("syncxml"),
            "metadata": {"acceptsSyntheticOrAnonymizedData": True},
        },
        {
            "email": "toni@example.com",
            "temporaryPassword": "Tmp-123456",
            "expiresAt": "2026-06-28T01:53:42.673404Z",
            "loginReady": True,
            "status": "active",
        },
    )

    assert "attachments" not in payload
