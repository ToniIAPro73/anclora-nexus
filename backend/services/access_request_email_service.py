from __future__ import annotations

import logging
from datetime import datetime
from html import escape
from email.utils import formataddr, parseaddr
from typing import Any, Dict
from zoneinfo import ZoneInfo

from backend.config import settings
from backend.services.email_delivery_service import get_email_transport_summary, send_email_native
from backend.services.syncxml_sample_workbooks import build_syncxml_sample_attachments

logger = logging.getLogger(__name__)


_PRODUCT_PROFILES = {
    "data_lab": {"label": "Data Lab", "brand": "Anclora Data Lab"},
    "guesthub": {"label": "GuestHub", "brand": "Anclora GuestHub"},
    "syncxml": {"label": "GuestHub", "brand": "Anclora GuestHub"},
    "synergi": {"label": "Synergi", "brand": "Anclora Synergi"},
}


def _product_profile(record: Dict[str, Any]) -> Dict[str, str]:
    product = str(record.get("product") or "").strip().lower()
    return _PRODUCT_PROFILES.get(product, _PRODUCT_PROFILES["synergi"])


def _product_label(record: Dict[str, Any]) -> str:
    return _product_profile(record)["label"]


def _product_brand(record: Dict[str, Any]) -> str:
    return _product_profile(record)["brand"]


def _nexus_sender() -> str | None:
    """Return the canonical sender for Nexus admission decisions."""
    configured = settings.RESEND_FROM or settings.RESEND_FROM_EMAIL
    if not configured:
        return None
    _, address = parseaddr(str(configured))
    if not address:
        return None
    return formataddr(("Anclora Nexus", address))


def _full_name(record: Dict[str, Any]) -> str:
    return str(record.get("full_name") or "there").strip() or "there"


def _email_to(record: Dict[str, Any]) -> str:
    return str(record.get("email") or "").strip()


def _format_madrid_access_expiry(value: Any) -> str:
    if not value:
        return "según condiciones del piloto"
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError:
            return "según condiciones del piloto"

    madrid = parsed.astimezone(ZoneInfo("Europe/Madrid"))
    weekdays = [
        "lunes",
        "martes",
        "miércoles",
        "jueves",
        "viernes",
        "sábado",
        "domingo",
    ]
    months = [
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ]
    return (
        f"{weekdays[madrid.weekday()]}, {madrid.day} de {months[madrid.month - 1]} "
        f"de {madrid.year}, a las {madrid:%H:%M} h (hora peninsular española)"
    )


BRAND_BG = "#070A12"
BRAND_SURFACE = "#101827"
BRAND_SURFACE_ELEVATED = "#151F32"
BRAND_ACCENT = "#BFA46A"
BRAND_TEXT = "#F8FAFC"
BRAND_MUTED = "#A8B3C7"


def _syncxml_app_url() -> str:
    # Legacy fallback URL kept until the owner decides the new GuestHub domain.
    return (settings.GUESTHUB_APP_URL or "https://anclora-syncxml.vercel.app").rstrip("/")


def _syncxml_logo_url() -> str:
    # The product renamed this asset to anclora-guesthub-email.png. Cutover requires
    # the new asset to be deployed at the app URL, otherwise email logos will break.
    return f"{_syncxml_app_url()}/brand/anclora-guesthub-email.png"


def _html_p(text: str) -> str:
    return f"<p style='margin:0 0 16px;color:{BRAND_MUTED};font-size:15px;line-height:22px;'>{escape(text)}</p>"


def _detail_row(label: str, value: Any) -> str:
    normalized = str(value or "").strip() or "No especificado"
    return (
        "<tr>"
        f"<td style='padding:8px 0;color:{BRAND_MUTED};font-size:13px;line-height:18px;width:190px;'>{escape(label)}</td>"
        f"<td style='padding:8px 0;color:{BRAND_TEXT};font-size:14px;line-height:20px;font-weight:700;'>{escape(normalized)}</td>"
        "</tr>"
    )


def _detail_table(rows: list[tuple[str, Any]]) -> str:
    return (
        f"<table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='margin:18px 0 0;border-collapse:collapse;border-top:1px solid rgba(191,164,106,0.34);'>"
        + "".join(_detail_row(label, value) for label, value in rows)
        + "</table>"
    )


def _pill(label: str) -> str:
    return (
        f"<span style='display:inline-block;margin:0 0 12px;padding:6px 10px;border:1px solid rgba(191,164,106,0.42);"
        f"border-radius:999px;color:{BRAND_ACCENT};font-size:12px;line-height:16px;font-weight:800;'>"
        f"{escape(label)}</span>"
    )


def _button(label: str, href: str) -> str:
    return (
        f"<a href='{escape(href)}' style='display:inline-block;margin:8px 0 18px;padding:12px 18px;"
        f"border-radius:999px;background:{BRAND_ACCENT};color:#111827;text-decoration:none;"
        f"font-size:14px;line-height:18px;font-weight:850;'>{escape(label)}</a>"
    )


def _syncxml_request_needs_sample_attachments(record: Dict[str, Any]) -> bool:
    metadata = record.get("metadata") or {}
    raw = metadata.get("raw") or {}
    value = metadata.get("acceptsSyntheticOrAnonymizedData", record.get("gdpr_consent"))
    return raw.get("needsSyntheticSampleAttachments") is True or value is False


def _html_shell(
    *,
    title: str,
    intro: str,
    body_html: str,
    brand_name: str = "Anclora Nexus",
    eyebrow: str = "Acceso Anclora",
    footer_note: str = "Email transaccional de Anclora Nexus.",
) -> str:
    return f"""
      <!doctype html>
      <html lang="es">
      <body style="margin:0;padding:0;background:{BRAND_BG};font-family:Inter,Segoe UI,Arial,sans-serif;color:{BRAND_TEXT};">
      <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:{BRAND_BG};padding:32px 16px;color:{BRAND_TEXT};border-collapse:collapse;">
        <tr>
          <td align="center">
            <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="max-width:720px;border-collapse:collapse;">
              <tr>
                <td style="padding:0 0 18px;">
                  <table role="presentation" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
                    <tr>
                      <td style="padding-right:12px;">
                        <div style="width:48px;height:48px;border-radius:8px;background:{BRAND_ACCENT};color:#111827;font-size:14px;line-height:48px;font-weight:850;text-align:center;">A</div>
                      </td>
                      <td>
                        <div style="color:{BRAND_TEXT};font-size:18px;line-height:24px;font-weight:850;">{escape(brand_name)}</div>
                        <div style="color:{BRAND_MUTED};font-size:13px;line-height:18px;">Decisiones de admisión</div>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
              <tr>
                <td style="border:1px solid rgba(255,255,255,0.10);border-radius:8px;background:{BRAND_SURFACE};overflow:hidden;">
                  <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="border-collapse:collapse;">
                    <tr>
                      <td style="padding:28px 28px 10px;background:{BRAND_SURFACE_ELEVATED};border-bottom:1px solid rgba(255,255,255,0.08);">
                        {_pill(eyebrow)}
                        <h1 style="margin:0;color:{BRAND_TEXT};font-size:24px;line-height:31px;font-weight:850;letter-spacing:0;">{escape(title)}</h1>
                        <p style="margin:10px 0 0;color:{BRAND_MUTED};font-size:15px;line-height:22px;">{escape(intro)}</p>
                      </td>
                    </tr>
                    <tr>
                      <td style="padding:24px 28px 28px;">
                        {body_html}
                        <p style="margin:20px 0 0;color:{BRAND_ACCENT};font-size:14px;line-height:22px;font-weight:700;">Anclora</p>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
              <tr>
                <td style="padding:16px 4px 0;color:{BRAND_MUTED};font-size:12px;line-height:18px;">
                  {escape(footer_note)}
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
      </body>
      </html>
    """


def build_access_request_approved_email(record: Dict[str, Any]) -> Dict[str, str]:
    product = f"Anclora {_product_label(record)}"
    full_name = _full_name(record)
    subject = f"Anclora Nexus · Solicitud aprobada — {product}"

    provisioning_case = str(record.get("provisioning_case") or "").strip().upper()
    provisioning_status = str(record.get("provisioning_status") or "").strip().lower()
    if provisioning_status == "failed" or provisioning_case in {"FAILED", "ERROR"}:
        paragraphs = [
            "Tu solicitud ha sido aprobada, pero no hemos podido completar automáticamente la preparación del acceso.",
            "Nuestro equipo revisará el proceso y te informará de los siguientes pasos.",
        ]
    elif provisioning_case == "CASO_A" or provisioning_status == "invite_ready" or record.get("identity_invitation_id"):
        paragraphs = [
            "Para completar tu acceso, recibirás un correo independiente de Anclora Identity con un enlace seguro para activar tu cuenta.",
            f"Una vez completada la activación podrás acceder a {product}.",
        ]
    elif provisioning_case == "CASO_B" or provisioning_status == "provisioned" or record.get("membership_id"):
        paragraphs = [
            f"El acceso a {product} se ha añadido a tu identidad Anclora existente.",
            "Ya puedes iniciar sesión utilizando tu cuenta habitual.",
        ]
    else:
        paragraphs = [
            "Tu solicitud ha sido aprobada y estamos preparando tu acceso.",
            "Te avisaremos cuando el proceso esté listo para continuar.",
        ]

    text = (
        f"Hola {full_name},\n\n"
        f"Tu solicitud de acceso a {product} ha sido aprobada.\n\n"
        + "\n\n".join(paragraphs)
        + "\n\nGracias por tu interés.\n\nAnclora Nexus"
    )
    html = _html_shell(
        title="Solicitud aprobada",
        intro=f"Hola {full_name}, tu solicitud de acceso a {product} ha sido aprobada.",
        body_html="".join(_html_p(paragraph) for paragraph in paragraphs),
        brand_name="Anclora Nexus",
        eyebrow="Acceso aprobado",
        footer_note=f"Este es un mensaje transaccional relacionado con tu solicitud de acceso a {product}.",
    )
    return {"to": _email_to(record), "subject": subject, "text": text, "html": html}


def build_syncxml_pilot_acceptance_email(record: Dict[str, Any], credentials: Dict[str, Any]) -> Dict[str, str]:
    full_name = _full_name(record)
    login_url = settings.GUESTHUB_LOGIN_URL or settings.GUESTHUB_APP_URL
    email = str(credentials.get("email") or _email_to(record))
    temporary_password = str(credentials.get("temporaryPassword") or "")
    expires_at = _format_madrid_access_expiry(credentials.get("expiresAt"))
    access_expiry_sentence = f"Tu acceso temporal estará disponible hasta el {expires_at}."
    subject = "Anclora GuestHub · Acceso al piloto controlado"
    needs_samples = _syncxml_request_needs_sample_attachments(record)
    sample_text = (
        "\nComo indicaste que no dispones de una muestra sintética propia, adjuntamos dos Excel: "
        "una muestra correcta y una muestra con un huésped incorrecto pero subsanable desde la app.\n"
        if needs_samples
        else ""
    )
    text = (
        f"Hola {full_name},\n\n"
        "Tu solicitud encaja con el alcance actual del piloto controlado de Anclora GuestHub.\n\n"
        f"Acceso: {login_url}\n"
        f"Email autorizado: {email}\n"
        f"Contraseña temporal: {temporary_password}\n"
        f"{access_expiry_sentence}\n"
        "Al iniciar sesión por primera vez, te pediremos crear una contraseña personal.\n\n"
        f"{sample_text}"
        "Límites del piloto:\n"
        "- Usa solo datos sintéticos o anonimizados.\n"
        "- No subas datos reales de huéspedes.\n"
        "- No hay envío automático a SES.HOSPEDAJES en esta fase.\n"
        "- El piloto no constituye asesoramiento legal ni garantiza cumplimiento normativo definitivo.\n"
        "- El acceso es limitado, revocable y revisable.\n\n"
        "Gracias,\nAnclora"
    )
    body_html = (
        _button("Acceder al piloto", login_url)
        + _detail_table([
            ("URL de acceso", login_url),
            ("Email autorizado", email),
            ("Contraseña temporal", temporary_password),
        ])
        + _html_p(access_expiry_sentence)
        + _html_p("Al iniciar sesión por primera vez, te pediremos crear una contraseña personal.")
        + (
            _html_p("Como indicaste que no dispones de una muestra sintética propia, adjuntamos dos Excel: una muestra correcta y una muestra con un huésped incorrecto pero subsanable desde la app.")
            if needs_samples
            else ""
        )
        + "<div style='margin-top:20px;padding:16px;border:1px solid rgba(255,255,255,0.10);border-radius:8px;background:rgba(255,255,255,0.035);'>"
        + f"<div style='color:{BRAND_ACCENT};font-size:12px;line-height:16px;font-weight:800;text-transform:uppercase;letter-spacing:0.08em;'>Límites del piloto</div>"
        + f"<ul style='margin:10px 0 0;padding-left:18px;color:{BRAND_MUTED};font-size:14px;line-height:22px;'>"
        + "<li>Usa solo datos sintéticos o anonimizados.</li>"
        + "<li>No subas datos reales de huéspedes.</li>"
        + "<li>No hay envío automático a SES.HOSPEDAJES en esta fase.</li>"
        + "<li>No constituye asesoramiento legal ni garantía normativa definitiva.</li>"
        + "<li>El acceso es limitado, revocable y revisable.</li>"
        + "</ul></div>"
    )
    html = _html_shell(
        title="Acceso al piloto controlado de GuestHub",
        intro=f"Hola {full_name}, tu solicitud encaja con el alcance actual del piloto controlado.",
        body_html=body_html,
        brand_name=_product_brand(record),
        eyebrow="GuestHub · Acceso aprobado",
    )
    payload: Dict[str, Any] = {"to": email, "subject": subject, "text": text, "html": html}
    if needs_samples:
        payload["attachments"] = build_syncxml_sample_attachments()
    return payload


def build_access_request_rejected_email(record: Dict[str, Any]) -> Dict[str, str]:
    product = f"Anclora {_product_label(record)}"
    full_name = _full_name(record)
    reason = str(record.get("rejection_reason") or "").strip()
    subject = f"Anclora Nexus · Solicitud no aprobada — {product}"
    paragraphs = [
        f"Gracias por tu interés en {product}.",
        "Después de revisar tu solicitud, en este momento no podemos aprobar el acceso solicitado.",
    ]
    if reason:
        paragraphs.append(f"Motivo: {reason}")
    paragraphs.append(
        "Esta decisión afecta únicamente a esta solicitud. Si cambian tus necesidades o las condiciones de acceso al producto, podrás presentar una nueva solicitud más adelante."
    )
    text = (
        f"Hola {full_name},\n\n"
        + "\n\n".join(paragraphs)
        + "\n\nGracias por tu interés.\n\nAnclora Nexus"
    )
    body_html = "".join(_html_p(paragraph) for paragraph in paragraphs)
    html = _html_shell(
        title="Solicitud no aprobada",
        intro=f"Hola {full_name}, gracias por tu interés en {product}.",
        body_html=body_html,
        brand_name="Anclora Nexus",
        eyebrow="Solicitud revisada",
        footer_note=f"Este es un mensaje transaccional relacionado con tu solicitud de acceso a {product}.",
    )
    return {"to": _email_to(record), "subject": subject, "text": text, "html": html}


def build_syncxml_more_info_email(record: Dict[str, Any], message: str) -> Dict[str, str]:
    product = _product_label(record)
    full_name = _full_name(record)
    subject = f"Anclora {product} · Necesitamos aclarar tu solicitud"
    text = (
        f"Hola {full_name},\n\n"
        f"{message}\n\n"
        "Recuerda que esta fase funciona solo con datos sintéticos o anonimizados y sin envío automático a SES.HOSPEDAJES.\n\n"
        "Gracias,\nAnclora"
    )
    html = _html_shell(
        title="Necesitamos aclarar tu solicitud",
        intro=f"Hola {full_name}, antes de confirmar el acceso necesitamos aclarar algunos detalles.",
        body_html=(
            _html_p(message)
            + _html_p("Recuerda que esta fase funciona solo con datos sintéticos o anonimizados y sin envío automático a SES.HOSPEDAJES.")
        ),
        brand_name=_product_brand(record),
        eyebrow=f"{product} · Información adicional",
    )
    return {"to": _email_to(record), "subject": subject, "text": text, "html": html}


def build_access_request_fallback_admin_email(record: Dict[str, Any]) -> Dict[str, str]:
    product = _product_label(record)
    email = _email_to(record)
    subject = f"ACTION REQUIRED: Validation failed for {product} lead"
    text = (
        f"Hello Admin,\n\n"
        f"The automated AI validation failed for the new {product} lead: {email}.\n"
        "Please review this request manually in the Nexus dashboard.\n\n"
        "Regards,\nAnclora Nexus"
    )
    html = _html_shell(
        title="Validation Fallback Triggered",
        intro=f"Automated validation failed for {email}.",
        body_html=_html_p("Please review this request manually in the Nexus dashboard."),
        brand_name=_product_brand(record),
        eyebrow=f"{product} · Revisión manual",
    )
    admin_email = settings.ADMIN_EMAIL
    return {"to": admin_email, "subject": subject, "text": text, "html": html}


class AccessRequestEmailService:
    def build_decision_email(self, record: Dict[str, Any]) -> Dict[str, str]:
        status = str(record.get("status") or "").strip().lower()
        if status == "approved":
            return build_access_request_approved_email(record)
        if status == "rejected":
            return build_access_request_rejected_email(record)
        raise ValueError(f"Unsupported access request decision status: {status}")

    def build_syncxml_acceptance_email(self, record: Dict[str, Any], credentials: Dict[str, Any]) -> Dict[str, str]:
        return build_syncxml_pilot_acceptance_email(record, credentials)

    def build_syncxml_more_info_email(self, record: Dict[str, Any], message: str) -> Dict[str, str]:
        return build_syncxml_more_info_email(record, message)

    def send_decision_email(self, record: Dict[str, Any]) -> Dict[str, Any]:
        mail = self.build_decision_email(record)
        transport = get_email_transport_summary()
        if not transport["native_email_enabled"]:
            logger.info("Access request decision email skipped: native email is not configured")
            return {
                "status": "skipped",
                "transport": "unavailable",
                "to": mail["to"],
                "subject": mail["subject"],
            }

        delivery = send_email_native(
            to_email=mail["to"],
            subject=mail["subject"],
            body=mail["text"],
            html=mail["html"],
            from_email=_nexus_sender(),
        )
        return {
            "status": "sent",
            "transport": transport["provider"],
            "to": mail["to"],
            "subject": mail["subject"],
            "delivery": delivery,
        }


access_request_email_service = AccessRequestEmailService()
