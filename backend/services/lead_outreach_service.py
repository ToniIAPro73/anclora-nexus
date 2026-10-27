from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from backend.services.email_delivery_service import get_email_transport_summary, send_email_native
from backend.services.llm_service import llm_service
from backend.services.neon_service import NeonService


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _extract_email(lead: Dict[str, Any]) -> Optional[str]:
    email = _safe_str(lead.get("email"))
    return email or None


def _latest_touch_timestamp(interactions: List[Dict[str, Any]]) -> Optional[str]:
    for item in interactions:
        created_at = item.get("created_at")
        if created_at:
            return str(created_at)
    return None


def _latest_supervised_delivery(interactions: List[Dict[str, Any]], channel: str) -> Optional[Dict[str, Any]]:
    artifact = f"supervised_send_{channel}"
    for item in interactions:
        metadata = item.get("metadata") or {}
        if str(metadata.get("artifact") or "") == artifact:
            return item
    return None


def _fallback_brief(lead: Dict[str, Any]) -> str:
    return (
        f"HNWI lead {lead.get('name') or 'Unknown'} | "
        f"tier {lead.get('qualification_tier') or 'cold'} | "
        f"score {lead.get('qualification_score') or 0} | "
        f"nationality {lead.get('nationality') or 'unknown'} | "
        f"zone {lead.get('zone_interest') or lead.get('property_interest') or 'Mallorca luxury'}."
    )


def _fallback_email_subject(lead: Dict[str, Any]) -> str:
    zone = _safe_str(lead.get("zone_interest")) or _safe_str(lead.get("property_interest")) or "Mallorca"
    return f"Oportunidades privadas en {zone} para su búsqueda en Mallorca"


def _fallback_email_body(lead: Dict[str, Any]) -> str:
    name = _safe_str(lead.get("name")) or "Hola"
    zone = _safe_str(lead.get("zone_interest")) or "Mallorca"
    nationality = _safe_str(lead.get("nationality"))
    intro = f"Hola {name},"
    context = (
        f"He visto su interés público en oportunidades de alta gama en {zone}."
        if not nationality
        else f"He visto su interés público como comprador {nationality} en oportunidades de alta gama en {zone}."
    )
    return (
        f"{intro}\n\n"
        f"{context} En Anclora Private Estates trabajamos con búsquedas discretas y selección cuidada de propiedades "
        "para compradores que priorizan privacidad, calidad y contexto local.\n\n"
        "Si le encaja, puedo enviarle una selección breve de oportunidades relevantes y un comentario inicial de mercado, "
        "sin compromiso.\n\n"
        "Un saludo,\n"
        "Anclora Private Estates"
    )


async def add_interaction(
    *,
    db: NeonService,
    org_id: str,
    lead_id: str,
    tipo: str,
    contenido: str,
    estado: str = "realizado",
    resultado: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    row = {
        "org_id": str(org_id),
        "lead_id": str(lead_id),
        "tipo": tipo,
        "contenido": contenido,
        "estado": estado,
        "resultado": resultado,
        "metadata": metadata or {},
    }
    result = db.client.table("lead_interactions").insert(row).execute()
    return result.data[0] if result.data else row


async def get_interactions(
    *,
    db: NeonService,
    org_id: str,
    lead_id: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    result = (
        db.client.table("lead_interactions")
        .select("*")
        .eq("org_id", str(org_id))
        .eq("lead_id", str(lead_id))
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


async def _get_lead(db: NeonService, org_id: str, lead_id: str) -> Optional[Dict[str, Any]]:
    result = (
        db.client.table("leads")
        .select("*")
        .eq("org_id", str(org_id))
        .eq("id", str(lead_id))
        .limit(1)
        .execute()
    )
    if isinstance(result.data, list):
        return result.data[0] if result.data else None
    return result.data or None


async def generate_lead_outreach(
    *,
    db: NeonService,
    org_id: str,
    lead_id: str,
) -> Dict[str, Any]:
    lead = await _get_lead(db, org_id, lead_id)
    if not lead:
        raise ValueError("Lead not found")

    brief_context = _fallback_brief(lead)
    try:
        brief = await llm_service.summarize(f"HNWI lead outreach brief.\nLead: {lead}")
    except Exception:
        brief = brief_context

    try:
        email_copy = await llm_service.generate_copy(
            "Write a concise first-contact luxury real estate email in Spanish.\n"
            f"Lead profile: {lead}\n"
            f"Brief: {brief_context}\n"
            "Return subject in first line as SUBJECT: ... and body after BODY:"
        )
    except Exception:
        email_copy = ""

    subject = _fallback_email_subject(lead)
    body = _fallback_email_body(lead)
    if "SUBJECT:" in email_copy and "BODY:" in email_copy:
        raw_subject = email_copy.split("SUBJECT:", 1)[1].split("BODY:", 1)[0].strip()
        raw_body = email_copy.split("BODY:", 1)[1].strip()
        if raw_subject:
            subject = raw_subject
        if raw_body:
            body = raw_body

    created = {
        "lead_brief": await add_interaction(
            db=db,
            org_id=org_id,
            lead_id=lead_id,
            tipo="lead_brief",
            contenido=brief or brief_context,
            metadata={"artifact": "lead_brief"},
        ),
        "email_draft": await add_interaction(
            db=db,
            org_id=org_id,
            lead_id=lead_id,
            tipo="email_draft",
            contenido=body,
            metadata={"artifact": "email_draft", "subject": subject},
        ),
    }
    return {
        "lead_id": lead_id,
        "brief": created["lead_brief"]["contenido"],
        "email_subject": subject,
        "email_body": body,
    }


async def build_supervised_send_payload(
    *,
    db: NeonService,
    org_id: str,
    lead_id: str,
    transport: str = "auto",
) -> Dict[str, Any]:
    lead = await _get_lead(db, org_id, lead_id)
    if not lead:
        raise ValueError("Lead not found")
    target = _extract_email(lead)
    if not target:
        raise ValueError("Lead email is required for supervised email send")

    interactions = await get_interactions(db=db, org_id=org_id, lead_id=lead_id, limit=20)
    draft = next(
        (
            item for item in interactions
            if str(item.get("tipo") or "") == "email_draft"
            or str((item.get("metadata") or {}).get("artifact") or "") == "email_draft"
        ),
        None,
    )
    subject = str(((draft or {}).get("metadata") or {}).get("subject") or _fallback_email_subject(lead))
    body = str((draft or {}).get("contenido") or _fallback_email_body(lead))

    email_transport = get_email_transport_summary()
    resolved_transport = transport
    if transport == "auto":
        resolved_transport = "native_email" if email_transport["native_email_enabled"] else "mailto"

    if resolved_transport == "native_email":
        delivery = send_email_native(to_email=str(target), subject=subject, body=body)
        interaction = await add_interaction(
            db=db,
            org_id=org_id,
            lead_id=lead_id,
            tipo="email",
            contenido=body,
            resultado="sent_native_supervised",
            metadata={
                "artifact": "supervised_send_email",
                "subject": subject,
                "target": target,
                "transport": "native_email",
                "delivery_provider": delivery.get("provider"),
                "provider_message_id": delivery.get("message_id"),
                "sent_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {
            "channel": "email",
            "lead_id": lead_id,
            "interaction_id": interaction.get("id"),
            "target": target,
            "subject": subject,
            "body": body,
            "launch_url": None,
            "status": "sent_natively",
            "transport": "native_email",
            "delivery": delivery,
        }

    launch_url = f"mailto:{quote(str(target))}?subject={quote(subject)}&body={quote(body)}"
    interaction = await add_interaction(
        db=db,
        org_id=org_id,
        lead_id=lead_id,
        tipo="email",
        contenido=body,
        estado="programado",
        resultado="launch_intent_created",
        metadata={
            "artifact": "supervised_send_email",
            "target": target,
            "subject": subject,
            "launch_url": launch_url,
            "transport": resolved_transport,
        },
    )
    return {
        "channel": "email",
        "lead_id": lead_id,
        "interaction_id": interaction.get("id"),
        "target": target,
        "subject": subject,
        "body": body,
        "launch_url": launch_url,
        "status": "ready_for_human_send",
        "transport": resolved_transport,
        "delivery": None,
    }


async def confirm_supervised_send(
    *,
    db: NeonService,
    org_id: str,
    lead_id: str,
    interaction_id: str,
) -> Optional[Dict[str, Any]]:
    current = (
        db.client.table("lead_interactions")
        .select("metadata")
        .eq("org_id", str(org_id))
        .eq("lead_id", str(lead_id))
        .eq("id", str(interaction_id))
        .maybe_single()
        .execute()
    )
    current_metadata = (current.data or {}).get("metadata") or {}
    result = (
        db.client.table("lead_interactions")
        .update(
            {
                "estado": "realizado",
                "resultado": "sent_confirmed_human",
                "metadata": {**current_metadata, "confirmed_at": datetime.now(timezone.utc).isoformat()},
            }
        )
        .eq("org_id", str(org_id))
        .eq("lead_id", str(lead_id))
        .eq("id", str(interaction_id))
        .execute()
    )
    return result.data[0] if result.data else None


async def get_lead_outreach_snapshot(
    *,
    db: NeonService,
    org_id: str,
    lead_id: str,
) -> Optional[Dict[str, Any]]:
    lead = await _get_lead(db, org_id, lead_id)
    if not lead:
        return None
    interactions = await get_interactions(db=db, org_id=org_id, lead_id=lead_id, limit=20)
    latest_artifacts: Dict[str, Optional[Dict[str, Any]]] = {"lead_brief": None, "email_draft": None}
    for item in interactions:
        tipo = str(item.get("tipo") or "")
        artifact = str(((item.get("metadata") or {}).get("artifact")) or "")
        if not latest_artifacts["lead_brief"] and (tipo == "lead_brief" or artifact == "lead_brief"):
            latest_artifacts["lead_brief"] = item
        if not latest_artifacts["email_draft"] and (tipo == "email_draft" or artifact == "email_draft"):
            latest_artifacts["email_draft"] = item
    email_transport = get_email_transport_summary()
    return {
        "lead": lead,
        "interactions": interactions,
        "latest_artifacts": latest_artifacts,
        "snapshot": {
            "interactions_count": len(interactions),
            "email_native_available": bool(email_transport["native_email_enabled"]),
            "latest_email_delivery": _latest_supervised_delivery(interactions, "email"),
            "last_touch_at": _latest_touch_timestamp(interactions),
        },
    }


class LeadOutreachService:
    add_interaction = staticmethod(add_interaction)
    get_interactions = staticmethod(get_interactions)
    generate_lead_outreach = staticmethod(generate_lead_outreach)
    build_supervised_send_payload = staticmethod(build_supervised_send_payload)
    confirm_supervised_send = staticmethod(confirm_supervised_send)
    get_lead_outreach_snapshot = staticmethod(get_lead_outreach_snapshot)


lead_outreach_service = LeadOutreachService()
