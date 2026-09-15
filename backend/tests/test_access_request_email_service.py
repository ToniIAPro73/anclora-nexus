import re
from io import BytesIO
from zipfile import ZipFile

import pytest

from backend.services.access_request_email_service import (
    build_access_request_approved_email,
    build_access_request_rejected_email,
    build_syncxml_pilot_acceptance_email,
)


def record(product: str = "synergi", rejection_reason: str | None = None) -> dict:
    return {
        "id": "request-1",
        "product": product,
        "full_name": "Toni Test",
        "email": "toni@example.com",
        "rejection_reason": rejection_reason,
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
    assert "Synergi" in payload["subject"]
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


@pytest.mark.parametrize(
    ("product", "brand", "wrong_brand"),
    [
        ("data_lab", "Anclora Data Lab", "Anclora GuestHub"),
        ("guesthub", "Anclora GuestHub", "Anclora Synergi"),
        ("synergi", "Anclora Synergi", "Anclora GuestHub"),
    ],
)
def test_approval_email_uses_product_aware_branding(product: str, brand: str, wrong_brand: str) -> None:
    payload = build_access_request_approved_email(record(product))

    assert brand in payload["html"]
    assert wrong_brand not in payload["html"]
    assert "No se ha creado ninguna cuenta externa" not in payload["text"]


def test_guesthub_product_has_guesthub_branding() -> None:
    payload = build_access_request_approved_email(record("guesthub"))

    assert payload["subject"] == "Anclora GuestHub · Solicitud aprobada"
    assert "Anclora GuestHub" in payload["html"]


def test_rejection_email_includes_rejection_reason_when_present() -> None:
    payload = build_access_request_rejected_email(
        record("synergi", rejection_reason="Insufficient service coverage")
    )

    assert "Insufficient service coverage" in payload["text"]
    assert "Insufficient service coverage" in payload["html"]
    assert_non_empty_bodies(payload)


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_rejection_email_handles_missing_or_empty_reason(reason) -> None:
    payload = build_access_request_rejected_email(record("data_lab", rejection_reason=reason))

    assert payload["to"] == "toni@example.com"
    assert "Data Lab" in payload["subject"]
    assert "Toni Test" in payload["text"]
    assert_non_empty_bodies(payload)


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
