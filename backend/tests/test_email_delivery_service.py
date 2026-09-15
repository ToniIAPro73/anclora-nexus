import sys
from types import SimpleNamespace

from backend.config import settings
from backend.services.email_delivery_service import get_email_transport_summary, send_email_native


def test_resend_transport_is_preferred_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test")
    monkeypatch.setattr(settings, "RESEND_FROM", "Anclora SyncXML <piloto@anclora.com>")
    monkeypatch.setattr(settings, "RESEND_FROM_EMAIL", None)
    monkeypatch.setattr(settings, "RESEND_REPLY_TO", "antonio@anclora.com")
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "smtp@example.com")

    summary = get_email_transport_summary()

    assert summary["native_email_enabled"] is True
    assert summary["provider"] == "resend"
    assert summary["from_email"] == "Anclora SyncXML <piloto@anclora.com>"
    assert summary["reply_to"] == "antonio@anclora.com"


def test_resend_transport_accepts_render_from_email_alias(monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test")
    monkeypatch.setattr(settings, "RESEND_FROM", None)
    monkeypatch.setattr(settings, "RESEND_FROM_EMAIL", "Anclora SyncXML <piloto@anclora.com>")
    monkeypatch.setattr(settings, "RESEND_REPLY_TO", "antonio@anclora.com")
    monkeypatch.setattr(settings, "SMTP_HOST", None)
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", None)

    summary = get_email_transport_summary()

    assert summary["native_email_enabled"] is True
    assert summary["provider"] == "resend"
    assert summary["from_email"] == "Anclora SyncXML <piloto@anclora.com>"
    assert summary["reply_to"] == "antonio@anclora.com"


def test_send_email_native_uses_resend_sdk(monkeypatch):
    sent = {}

    class FakeEmails:
        @staticmethod
        def send(params):
            sent.update(params)
            return {"id": "email_test_123"}

    fake_resend = SimpleNamespace(api_key=None, Emails=FakeEmails)
    monkeypatch.setitem(sys.modules, "resend", fake_resend)
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test")
    monkeypatch.setattr(settings, "RESEND_FROM", "Anclora SyncXML <piloto@anclora.com>")
    monkeypatch.setattr(settings, "RESEND_FROM_EMAIL", None)
    monkeypatch.setattr(settings, "RESEND_REPLY_TO", "antonio@anclora.com")

    result = send_email_native(
        to_email="toni@example.com",
        subject="Solicitud aprobada",
        body="Texto fallback",
        html="<strong>HTML</strong>",
        from_email="Anclora Data Lab <piloto@anclora.com>",
    )

    assert result["provider"] == "resend"
    assert result["message_id"] == "email_test_123"
    assert sent == {
        "from": "Anclora Data Lab <piloto@anclora.com>",
        "to": ["toni@example.com"],
        "subject": "Solicitud aprobada",
        "text": "Texto fallback",
        "html": "<strong>HTML</strong>",
        "reply_to": "antonio@anclora.com",
    }


def test_send_email_native_passes_attachments_to_resend(monkeypatch):
    sent = {}

    class FakeEmails:
        @staticmethod
        def send(params):
            sent.update(params)
            return {"id": "email_test_attachments"}

    fake_resend = SimpleNamespace(api_key=None, Emails=FakeEmails)
    monkeypatch.setitem(sys.modules, "resend", fake_resend)
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test")
    monkeypatch.setattr(settings, "RESEND_FROM", "Anclora SyncXML <piloto@anclora.com>")
    monkeypatch.setattr(settings, "RESEND_FROM_EMAIL", None)
    monkeypatch.setattr(settings, "RESEND_REPLY_TO", None)

    result = send_email_native(
        to_email="toni@example.com",
        subject="Solicitud aprobada",
        body="Texto fallback",
        attachments=[
            {
                "filename": "muestra.xlsx",
                "content": b"sample-bytes",
                "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
        ],
    )

    assert result["provider"] == "resend"
    assert sent["attachments"] == [{"filename": "muestra.xlsx", "content": "c2FtcGxlLWJ5dGVz"}]
