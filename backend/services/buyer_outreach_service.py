from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from backend.services.buyer_memory_service import buyer_memory_service
from backend.services.email_delivery_service import get_email_transport_summary, send_email_native
from backend.services.llm_service import llm_service
from backend.services.neon_service import NeonService


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


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


def _extract_email(buyer: Dict[str, Any]) -> Optional[str]:
    return buyer.get("email")


def _extract_whatsapp(buyer: Dict[str, Any]) -> Optional[str]:
    return buyer.get("phone")


def _match_summary(match: Dict[str, Any]) -> str:
    title = match.get("property_title") or match.get("property_id") or "property"
    return f"{title} · {match.get('match_status') or 'candidate'} · score {match.get('match_score') or 0}"


def _is_placeholder_copy(text: str) -> bool:
    candidate = _safe_str(text).lower()
    if not candidate:
        return True
    return candidate.startswith("copy generation unavailable.")


def _property_display_name(row: Dict[str, Any]) -> str:
    title = _safe_str(row.get("title"))
    if title:
        return title

    address = _safe_str(row.get("address"))
    if address:
        return address

    zone = _safe_str(row.get("zone"))
    city = _safe_str(row.get("city"))
    property_type = _safe_str(row.get("property_type")).replace("_", " ")

    location = " · ".join([part for part in (zone, city) if part])
    if location and property_type:
        return f"{property_type.title()} · {location}"
    if location:
        return location
    if property_type:
        return property_type.title()
    return "Sin título"


async def add_interaction(
    *,
    db: NeonService,
    org_id: str,
    buyer_id: str,
    tipo: str,
    contenido: str,
    estado: str = "realizado",
    resultado: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    row = {
        "org_id": str(org_id),
        "buyer_id": str(buyer_id),
        "tipo": tipo,
        "contenido": contenido,
        "estado": estado,
        "resultado": resultado,
        "metadata": metadata or {},
    }
    result = db.client.table("buyer_interactions").insert(row).execute()
    return result.data[0] if result.data else row


async def get_interactions(
    *,
    db: NeonService,
    org_id: str,
    buyer_id: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    result = (
        db.client.table("buyer_interactions")
        .select("*")
        .eq("org_id", str(org_id))
        .eq("buyer_id", str(buyer_id))
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


async def _get_buyer(db: NeonService, org_id: str, buyer_id: str) -> Optional[Dict[str, Any]]:
    result = (
        db.client.table("buyer_profiles")
        .select("*")
        .eq("org_id", str(org_id))
        .eq("id", str(buyer_id))
        .limit(1)
        .execute()
    )
    if isinstance(result.data, list):
        return result.data[0] if result.data else None
    return result.data or None


async def _get_matches(db: NeonService, org_id: str, buyer_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    matches = (
        db.client.table("property_buyer_matches")
        .select("*")
        .eq("org_id", str(org_id))
        .eq("buyer_id", str(buyer_id))
        .order("match_score", desc=True)
        .limit(limit)
        .execute()
    ).data or []
    property_ids = [str(item.get("property_id")) for item in matches if item.get("property_id")]
    property_map: Dict[str, str] = {}
    if property_ids:
        for table in ("properties", "prospected_properties"):
            try:
                rows = (
                    db.client.table(table)
                    .select("*")
                    .eq("org_id", str(org_id))
                    .in_("id", property_ids)
                    .execute()
                ).data or []
                for row in rows:
                    property_map[str(row.get("id"))] = _property_display_name(row)
            except Exception:
                continue
        if len(property_map) < len(property_ids):
            for table in ("properties", "prospected_properties"):
                try:
                    rows = (
                        db.client.table(table)
                        .select("*")
                        .in_("id", property_ids)
                        .execute()
                    ).data or []
                    for row in rows:
                        row_id = str(row.get("id") or "")
                        if row_id and row_id not in property_map:
                            property_map[row_id] = _property_display_name(row)
                except Exception:
                    continue
    for item in matches:
        item["property_title"] = property_map.get(str(item.get("property_id")), item.get("property_title"))
    return matches


async def _get_match_activities(db: NeonService, org_id: str, match_ids: List[str], limit: int = 10) -> List[Dict[str, Any]]:
    if not match_ids:
        return []
    rows = (
        db.client.table("match_activity_log")
        .select("*")
        .eq("org_id", str(org_id))
        .in_("match_id", match_ids)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    ).data or []
    return rows


def _build_buyer_console(
    buyer: Dict[str, Any],
    latest_artifacts: Dict[str, Optional[Dict[str, Any]]],
    interactions: List[Dict[str, Any]],
    matches: List[Dict[str, Any]],
    memory_payload: Dict[str, Any],
) -> Dict[str, Any]:
    intro_status = str(buyer.get("buyer_intro_status") or "new")
    has_brief = latest_artifacts.get("buyer_brief") is not None
    has_email = latest_artifacts.get("email_draft") is not None
    has_whatsapp = latest_artifacts.get("whatsapp_draft") is not None
    email_contact = bool(_extract_email(buyer))
    whatsapp_contact = bool(_extract_whatsapp(buyer))
    memory_matches = memory_payload.get("matches") or []
    readiness = "ready_to_send"
    next_action = "Launch supervised buyer outreach"
    recommended_channel = "email"
    reasons: List[str] = []

    if not has_brief:
        readiness = "needs_brief"
        recommended_channel = "review"
        next_action = "Generate buyer outreach brief and drafts"
        reasons.append("Buyer workbench still lacks context brief and outreach drafts.")
    elif intro_status in {"new", "introduced"}:
        if email_contact and has_email:
            recommended_channel = "email"
            next_action = "Send the first supervised buyer email"
            reasons.append("Buyer is still early-stage and email is the best structured first touch.")
        elif whatsapp_contact and has_whatsapp:
            recommended_channel = "whatsapp"
            next_action = "Open the first WhatsApp touchpoint"
            reasons.append("Buyer has direct phone and WhatsApp draft ready.")
        else:
            readiness = "needs_contact_channel"
            recommended_channel = "review"
            next_action = "Persist buyer contact details before outreach"
            reasons.append("There is no valid outreach channel stored yet.")
    elif intro_status in {"qualified", "viewing"}:
        recommended_channel = "call"
        next_action = "Resume the conversation with the strongest property match"
        reasons.append("Buyer is already in motion, so follow-up should anchor on active matches.")
    elif intro_status == "closed":
        recommended_channel = "review"
        next_action = "Maintain referral relationship"
        reasons.append("Buyer is already closed; use the console for stewardship and referrals.")

    if matches:
        reasons.append(f"Top match: {_match_summary(matches[0])}")
    if memory_matches:
        reasons.append(f"Memory focus: {', '.join((memory_matches[0].get('matched_keywords') or [])[:3]) or 'buyer context'}")

    return {
        "readiness": readiness,
        "recommended_channel": recommended_channel,
        "next_action": next_action,
        "reasons": reasons,
        "last_touch_at": _latest_touch_timestamp(interactions),
        "memory_highlights": [
            {
                "summary": ((match.get("record") or {}).get("summary") or ""),
                "score": match.get("score") or 0,
            }
            for match in memory_matches[:3]
        ],
    }


def _fallback_brief(buyer: Dict[str, Any], matches: List[Dict[str, Any]], memory_payload: Dict[str, Any]) -> str:
    top_match = _match_summary(matches[0]) if matches else "No active match yet"
    zones = ", ".join(buyer.get("preferred_zones") or []) or "zona pendiente"
    memory_hint = ""
    memory_matches = memory_payload.get("matches") or []
    if memory_matches:
        memory_hint = f" Ultimo contexto: {((memory_matches[0].get('record') or {}).get('summary') or '')}."
    return (
        f"Buyer {_safe_str(buyer.get('full_name')) or 'sin nombre'} con foco en {zones}. "
        f"Fuente {_safe_str(buyer.get('source_type')).replace('_', ' ')}. "
        f"Top match actual: {top_match}.{memory_hint}"
    ).strip()


def _fallback_email_subject(buyer: Dict[str, Any], matches: List[Dict[str, Any]]) -> str:
    first_name = (_safe_str(buyer.get("full_name")).split(" ") or ["Buyer"])[0]
    property_hint = _match_summary(matches[0]) if matches else "propiedades en tu zona"
    return f"{first_name}, seleccioné una oportunidad en {property_hint}"


def _fallback_email_body(buyer: Dict[str, Any], matches: List[Dict[str, Any]]) -> str:
    first_name = (_safe_str(buyer.get("full_name")).split(" ") or ["Hola"])[0]
    property_hint = _match_summary(matches[0]) if matches else "varias opciones alineadas con tu búsqueda"
    return (
        f"Hola {first_name},\n\n"
        f"He revisado tu búsqueda y creo que hay una oportunidad especialmente relevante: {property_hint}.\n"
        f"Si te encaja, te propongo revisarla juntos y definir siguiente paso hoy.\n\n"
        "Quedo atento."
    )


def _fallback_whatsapp_body(buyer: Dict[str, Any], matches: List[Dict[str, Any]]) -> str:
    first_name = (_safe_str(buyer.get("full_name")).split(" ") or ["Hola"])[0]
    property_hint = _match_summary(matches[0]) if matches else "una oportunidad alineada con tu búsqueda"
    return f"Hola {first_name}, he revisado tu búsqueda y tengo {property_hint}. Si quieres, te paso contexto y vemos siguiente paso hoy."


async def generate_buyer_outreach(
    *,
    db: NeonService,
    org_id: str,
    buyer_id: str,
) -> Dict[str, Any]:
    buyer = await _get_buyer(db, org_id, buyer_id)
    if not buyer:
        raise ValueError("Buyer not found")
    matches = await _get_matches(db, org_id, buyer_id, limit=5)
    memory = await buyer_memory_service.search(
        db=db,
        org_id=org_id,
        buyer_id=buyer_id,
        query="buyer next step objections visit viewing budget",
        limit=5,
    )
    memory_payload = memory.model_dump()
    brief_context = _fallback_brief(buyer, matches, memory_payload)

    try:
        brief = await llm_service.summarize(
            f"Buyer outreach brief.\nBuyer: {buyer}\nMatches: {matches}\nMemory: {memory_payload}"
        )
    except Exception:
        brief = brief_context

    try:
        email_copy = await llm_service.generate_copy(
            f"Write a concise luxury real estate buyer follow-up email in Spanish.\n"
            f"Buyer profile: {buyer}\nTop matches: {matches[:2]}\nBrief: {brief_context}\n"
            "Return subject in first line as SUBJECT: ... and body after BODY:"
        )
    except Exception:
        email_copy = ""

    subject = _fallback_email_subject(buyer, matches)
    body = _fallback_email_body(buyer, matches)
    if "SUBJECT:" in email_copy and "BODY:" in email_copy:
        raw_subject = email_copy.split("SUBJECT:", 1)[1].split("BODY:", 1)[0].strip()
        raw_body = email_copy.split("BODY:", 1)[1].strip()
        if raw_subject:
            subject = raw_subject
        if raw_body:
            body = raw_body

    whatsapp_body = _fallback_whatsapp_body(buyer, matches)
    try:
        whatsapp_candidate = await llm_service.generate_copy(
            f"Write a short WhatsApp follow-up in Spanish for this buyer.\nBuyer: {buyer}\nBrief: {brief_context}\nMatches: {matches[:1]}"
        )
        if whatsapp_candidate and not _is_placeholder_copy(whatsapp_candidate):
            whatsapp_body = whatsapp_candidate.strip()
    except Exception:
        pass

    created = {
        "buyer_brief": await add_interaction(
            db=db,
            org_id=org_id,
            buyer_id=buyer_id,
            tipo="buyer_brief",
            contenido=brief or brief_context,
            metadata={"artifact": "buyer_brief"},
        ),
        "email_draft": await add_interaction(
            db=db,
            org_id=org_id,
            buyer_id=buyer_id,
            tipo="email_draft",
            contenido=body,
            metadata={"artifact": "email_draft", "subject": subject},
        ),
        "whatsapp_draft": await add_interaction(
            db=db,
            org_id=org_id,
            buyer_id=buyer_id,
            tipo="whatsapp_draft",
            contenido=whatsapp_body,
            metadata={"artifact": "whatsapp_draft"},
        ),
    }
    return {
        "buyer_id": buyer_id,
        "brief": created["buyer_brief"]["contenido"],
        "email_subject": subject,
        "email_body": body,
        "whatsapp_body": whatsapp_body,
    }


async def get_buyer_workbench(
    *,
    db: NeonService,
    org_id: str,
    buyer_id: str,
    interaction_limit: int = 20,
) -> Optional[Dict[str, Any]]:
    buyer = await _get_buyer(db, org_id, buyer_id)
    if not buyer:
        return None
    interactions = await get_interactions(db=db, org_id=org_id, buyer_id=buyer_id, limit=interaction_limit)
    matches = await _get_matches(db, org_id, buyer_id, limit=5)
    activities = await _get_match_activities(db, org_id, [str(item.get("id")) for item in matches if item.get("id")], limit=10)
    latest_artifacts: Dict[str, Optional[Dict[str, Any]]] = {
        "buyer_brief": None,
        "email_draft": None,
        "whatsapp_draft": None,
    }
    for item in interactions:
        tipo = str(item.get("tipo") or "")
        metadata = item.get("metadata") or {}
        artifact = str(metadata.get("artifact") or "")
        if not latest_artifacts["buyer_brief"] and (tipo == "buyer_brief" or artifact == "buyer_brief"):
            latest_artifacts["buyer_brief"] = item
        if not latest_artifacts["email_draft"] and (tipo == "email_draft" or artifact == "email_draft"):
            latest_artifacts["email_draft"] = item
        if not latest_artifacts["whatsapp_draft"] and (tipo == "whatsapp_draft" or artifact == "whatsapp_draft"):
            latest_artifacts["whatsapp_draft"] = item

    memory = await buyer_memory_service.search(
        db=db,
        org_id=org_id,
        buyer_id=buyer_id,
        query="buyer next step objections visit viewing budget",
        limit=5,
    )
    memory_payload = memory.model_dump()
    console = _build_buyer_console(
        buyer=buyer,
        latest_artifacts=latest_artifacts,
        interactions=interactions,
        matches=matches,
        memory_payload=memory_payload,
    )
    email_transport = get_email_transport_summary()
    return {
        "buyer": buyer,
        "matches": matches,
        "activities": activities,
        "interactions": interactions,
        "latest_artifacts": latest_artifacts,
        "memory": memory_payload,
        "console": console,
        "snapshot": {
            "interactions_count": len(interactions),
            "matches_count": len(matches),
            "semantic_memory_count": memory.total_records,
            "semantic_memory_ready": memory.status == "ready",
            "recommended_channel": console["recommended_channel"],
            "readiness": console["readiness"],
            "email_native_available": bool(email_transport["native_email_enabled"]),
            "latest_email_delivery": _latest_supervised_delivery(interactions, "email"),
            "latest_whatsapp_delivery": _latest_supervised_delivery(interactions, "whatsapp"),
        },
    }


async def build_supervised_send_payload(
    *,
    db: NeonService,
    org_id: str,
    buyer_id: str,
    channel: str,
    transport: str = "auto",
) -> Dict[str, Any]:
    if channel not in {"email", "whatsapp"}:
        raise ValueError("channel must be email or whatsapp")
    workbench = await get_buyer_workbench(db=db, org_id=org_id, buyer_id=buyer_id, interaction_limit=20)
    if not workbench:
        raise ValueError("Buyer not found")
    buyer = workbench["buyer"]
    artifacts = workbench["latest_artifacts"]
    email_draft = artifacts.get("email_draft")
    whatsapp_draft = artifacts.get("whatsapp_draft")
    subject = str(((email_draft or {}).get("metadata") or {}).get("subject") or _fallback_email_subject(buyer, workbench["matches"]))
    body = str((email_draft or {}).get("contenido") or _fallback_email_body(buyer, workbench["matches"]))

    resolved_transport = transport
    if channel == "email":
        target = _extract_email(buyer)
        if not target:
            raise ValueError("Buyer email is required for supervised email send")
        email_transport = get_email_transport_summary()
        if transport == "auto":
            resolved_transport = "native_email" if email_transport["native_email_enabled"] else "mailto"
        if resolved_transport == "native_email":
            delivery = send_email_native(to_email=str(target), subject=subject, body=body)
            interaction = await add_interaction(
                db=db,
                org_id=org_id,
                buyer_id=buyer_id,
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
                "channel": channel,
                "buyer_id": buyer_id,
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
    else:
        target = _extract_whatsapp(buyer)
        if not target:
            raise ValueError("Buyer phone is required for supervised WhatsApp send")
        digits = re.sub(r"\D", "", str(target))
        body = str((whatsapp_draft or {}).get("contenido") or _fallback_whatsapp_body(buyer, workbench["matches"]))
        subject = ""
        resolved_transport = "wa_me"
        launch_url = f"https://wa.me/{digits}?text={quote(body)}"

    interaction = await add_interaction(
        db=db,
        org_id=org_id,
        buyer_id=buyer_id,
        tipo=channel,
        contenido=body,
        estado="programado",
        resultado="launch_intent_created",
        metadata={
            "artifact": f"supervised_send_{channel}",
            "target": target,
            "subject": subject,
            "launch_url": launch_url,
            "transport": resolved_transport,
        },
    )
    return {
        "channel": channel,
        "buyer_id": buyer_id,
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
    buyer_id: str,
    interaction_id: str,
) -> Optional[Dict[str, Any]]:
    current = (
        db.client.table("buyer_interactions")
        .select("metadata")
        .eq("org_id", str(org_id))
        .eq("buyer_id", str(buyer_id))
        .eq("id", str(interaction_id))
        .maybe_single()
        .execute()
    )
    current_metadata = (current.data or {}).get("metadata") or {}
    result = (
        db.client.table("buyer_interactions")
        .update({
            "estado": "realizado",
            "resultado": "sent_confirmed_human",
            "metadata": {**current_metadata, "confirmed_at": datetime.now(timezone.utc).isoformat()},
        })
        .eq("org_id", str(org_id))
        .eq("buyer_id", str(buyer_id))
        .eq("id", str(interaction_id))
        .execute()
    )
    return result.data[0] if result.data else None


class BuyerOutreachService:
    add_interaction = staticmethod(add_interaction)
    get_interactions = staticmethod(get_interactions)
    generate_buyer_outreach = staticmethod(generate_buyer_outreach)
    get_buyer_workbench = staticmethod(get_buyer_workbench)
    build_supervised_send_payload = staticmethod(build_supervised_send_payload)
    confirm_supervised_send = staticmethod(confirm_supervised_send)


buyer_outreach_service = BuyerOutreachService()
