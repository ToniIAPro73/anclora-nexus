from __future__ import annotations

import smtplib
import base64
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr
from typing import Any, Dict, List, Optional, TypedDict

from backend.config import settings


class EmailAttachment(TypedDict):
    filename: str
    content: bytes
    content_type: str


def _resend_from() -> Optional[str]:
    return settings.RESEND_FROM or settings.RESEND_FROM_EMAIL


def get_email_transport_summary() -> Dict[str, Any]:
    resend_from = _resend_from()
    resend_enabled = bool((settings.RESEND_API_KEY or "").strip() and (resend_from or "").strip())
    smtp_enabled = bool((settings.SMTP_HOST or "").strip() and (settings.SMTP_FROM_EMAIL or "").strip())
    enabled = resend_enabled or smtp_enabled
    return {
        "native_email_enabled": enabled,
        "provider": "resend" if resend_enabled else "smtp" if smtp_enabled else "mailto",
        "from_email": resend_from or settings.SMTP_FROM_EMAIL,
        "from_name": settings.SMTP_FROM_NAME,
        "reply_to": settings.RESEND_REPLY_TO or settings.SMTP_REPLY_TO,
    }


def _send_with_resend(
    *,
    to_email: str,
    subject: str,
    body: str,
    html: Optional[str] = None,
    attachments: Optional[List[EmailAttachment]] = None,
    from_email: Optional[str] = None,
) -> Dict[str, Any]:
    import resend

    resend.api_key = settings.RESEND_API_KEY
    resend_from = from_email or _resend_from()
    params: resend.Emails.SendParams = {
        "from": str(resend_from),
        "to": [to_email],
        "subject": subject,
        "text": body,
    }
    if html:
        params["html"] = html
    if settings.RESEND_REPLY_TO or settings.SMTP_REPLY_TO:
        params["reply_to"] = settings.RESEND_REPLY_TO or settings.SMTP_REPLY_TO
    if attachments:
        params["attachments"] = [
            {
                "filename": attachment["filename"],
                "content": base64.b64encode(attachment["content"]).decode("ascii"),
            }
            for attachment in attachments
        ]

    result = resend.Emails.send(params)
    message_id = result.get("id") if isinstance(result, dict) else None
    return {
        "provider": "resend",
        "message_id": message_id,
        "from_email": resend_from,
        "reply_to": settings.RESEND_REPLY_TO or settings.SMTP_REPLY_TO,
    }


def send_email_native(
    *,
    to_email: str,
    subject: str,
    body: str,
    html: Optional[str] = None,
    attachments: Optional[List[EmailAttachment]] = None,
    from_email: Optional[str] = None,
) -> Dict[str, Any]:
    transport = get_email_transport_summary()
    if not transport["native_email_enabled"]:
        raise RuntimeError("Native email transport is not configured")

    if transport["provider"] == "resend":
        return _send_with_resend(
            to_email=to_email,
            subject=subject,
            body=body,
            html=html,
            attachments=attachments,
            from_email=from_email,
        )

    message = EmailMessage()
    message["To"] = to_email
    message["From"] = from_email or (
        f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        if settings.SMTP_FROM_NAME
        else str(settings.SMTP_FROM_EMAIL)
    )
    message["Subject"] = subject
    if settings.SMTP_REPLY_TO:
        message["Reply-To"] = settings.SMTP_REPLY_TO
    message["Message-ID"] = make_msgid(domain=(settings.SMTP_FROM_EMAIL or "anclora.local").split("@")[-1])
    message.set_content(body)
    if html:
        message.add_alternative(html, subtype="html")
    for attachment in attachments or []:
        maintype, _, subtype = attachment["content_type"].partition("/")
        message.add_attachment(
            attachment["content"],
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=attachment["filename"],
        )

    if settings.SMTP_USE_SSL:
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD or "")
            smtp.send_message(message)
    else:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
            smtp.ehlo()
            if settings.SMTP_USE_TLS:
                smtp.starttls()
                smtp.ehlo()
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD or "")
            smtp.send_message(message)

    return {
        "provider": "smtp",
        "message_id": message["Message-ID"],
        "from_email": settings.SMTP_FROM_EMAIL,
        "reply_to": settings.SMTP_REPLY_TO,
    }
