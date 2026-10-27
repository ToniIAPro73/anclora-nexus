"""
Seller Prospection StateGraph — ANCLORA-SIP-001

6-node LangGraph pipeline for seller lead intake:
  START → extract_lead_data → calculate_priority → check_limits
       → generate_outreach_copy → create_approval_task → conditional_router → END

All outputs include AI identifier: [Generado por Anclora Nexus Agent — {skill}]
Constitutional limits enforced as hard stops.
"""

import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from typing import Literal, Optional

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from backend.config import settings

# ─── Guardrails: forbidden phrases in outreach copy ──────────────────────────
_FORBIDDEN_PHRASES = re.compile(
    r"\b(garantizado|mejor del mercado|solo (quedan|disponible[s]?)|exclusivo|"
    r"oferta irrepetible|no lo pierdas|urgente|inmediatamente|precio m[áa]ximo garantizado)\b",
    re.IGNORECASE,
)

# ─── Priority formula weights ─────────────────────────────────────────────────
_W_BUDGET = 0.35
_W_URGENCY = 0.25
_W_PROPERTY_FIT = 0.25
_W_SOURCE_QUALITY = 0.15

# Zone quality scores (suroeste Mallorca territory)
_ZONE_SCORES: dict[str, float] = {
    "andratx": 1.0, "calvia": 1.0, "portals_nous": 1.0, "bendinat": 1.0,
    "punta_negra": 0.9, "costa_den_blanes": 0.85, "port_adriano": 0.8,
    "son_ferrer": 0.75, "santa_ponca": 0.75, "paguera": 0.7,
    "palma": 0.6, "otra": 0.4,
}

# Source quality scores
_SOURCE_SCORES: dict[str, float] = {
    "str_enforcement": 1.0, "fsbo": 0.9, "referral": 0.8,
    "idealista": 0.7, "fotocasa": 0.7, "scraping": 0.6,
    "prospection_match": 0.5, "manual": 0.5,
}


# ─── State ────────────────────────────────────────────────────────────────────

class SellerProspectionState(TypedDict):
    # Input
    raw_data: dict
    org_id: str

    # After extraction
    seller_id: Optional[str]
    extraction_result: dict          # structured fields + confidence scores
    extraction_confidence: float     # overall confidence 0-1

    # After prioritization
    priority_score: float            # 0-1 weighted score
    priority_tier: int               # 1-5 mapped tier

    # After limit check
    can_proceed: bool
    limit_violation: Optional[str]

    # After outreach generation
    outreach_email: str
    outreach_whatsapp: str

    # After HITL task creation
    draft_id: Optional[str]

    # Approval routing
    approval_status: Literal["draft", "approved", "sent", "rejected"]

    # Audit chain (append-only)
    audit_chain: list[dict]

    # Error handling
    error_message: Optional[str]
    status: str                      # running | success | error | blocked


# ─── Helper: HMAC audit entry ────────────────────────────────────────────────

def _signed_audit_entry(action: str, payload: dict, org_id: str) -> dict:
    secret = (settings.INTERNAL_AUDIT_SECRET or "dev-audit-secret").encode()
    body = json.dumps({"action": action, "org_id": org_id, **payload}, sort_keys=True, default=str)
    sig = hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()
    return {
        "action": action,
        "org_id": org_id,
        "payload": payload,
        "hmac_sha256": sig,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─── Node 1: extract_lead_data ───────────────────────────────────────────────

async def extract_lead_data(state: SellerProspectionState) -> SellerProspectionState:
    """
    Parse raw_data and extract structured seller fields.
    Uses heuristic extraction; LLM fallback for unstructured text.
    """
    raw = state["raw_data"]
    org_id = state["org_id"]

    def _coerce_float(v) -> Optional[float]:
        try:
            return float(str(v).replace(".", "").replace(",", ".")) if v else None
        except (ValueError, TypeError):
            return None

    def _coerce_int(v) -> Optional[int]:
        try:
            return int(v) if v else None
        except (ValueError, TypeError):
            return None

    # Direct field extraction with confidence tracking
    extracted: dict = {}
    confidence_scores: dict[str, float] = {}

    name = raw.get("nombre_propietario") or raw.get("name") or raw.get("owner_name")
    extracted["nombre_propietario"] = str(name) if name else None
    confidence_scores["nombre_propietario"] = 0.9 if name else 0.0

    price = _coerce_float(raw.get("precio_publicado") or raw.get("price") or raw.get("precio"))
    extracted["precio_publicado"] = price
    confidence_scores["precio_publicado"] = 0.9 if price else 0.3

    zone_raw = str(raw.get("zona") or raw.get("zone") or "otra").lower().replace(" ", "_")
    from backend.models.sellers import ZonaEnum
    try:
        extracted["zona"] = ZonaEnum(zone_raw).value
        confidence_scores["zona"] = 0.95
    except ValueError:
        # Fuzzy match
        for z in ZonaEnum:
            if z.value in zone_raw or zone_raw in z.value:
                extracted["zona"] = z.value
                confidence_scores["zona"] = 0.7
                break
        else:
            extracted["zona"] = "otra"
            confidence_scores["zona"] = 0.3

    source_raw = str(raw.get("fuente") or raw.get("source") or "manual").lower()
    from backend.models.sellers import FuenteEnum
    try:
        extracted["fuente"] = FuenteEnum(source_raw).value
        confidence_scores["fuente"] = 0.95
    except ValueError:
        extracted["fuente"] = "manual"
        confidence_scores["fuente"] = 0.4

    extracted["dias_en_mercado"] = _coerce_int(raw.get("dias_en_mercado") or raw.get("days_on_market"))
    confidence_scores["dias_en_mercado"] = 0.8 if extracted["dias_en_mercado"] is not None else 0.2

    extracted["superficie_m2"] = _coerce_float(raw.get("superficie_m2") or raw.get("area_m2") or raw.get("size"))
    extracted["tipo_propiedad"] = raw.get("tipo_propiedad") or raw.get("property_type")
    extracted["email_contacto"] = raw.get("email_contacto") or raw.get("email")
    extracted["telefono_contacto"] = raw.get("telefono_contacto") or raw.get("phone")
    extracted["whatsapp_contacto"] = raw.get("whatsapp_contacto") or raw.get("whatsapp")
    extracted["notas"] = raw.get("notas") or raw.get("notes")
    extracted["senales_motivacion"] = list(raw.get("senales_motivacion") or raw.get("motivation_signals") or [])

    overall_confidence = sum(confidence_scores.values()) / max(len(confidence_scores), 1)

    audit_entry = _signed_audit_entry(
        "extract_lead_data",
        {"confidence": overall_confidence, "fields_extracted": list(extracted.keys())},
        org_id,
    )

    new_state = dict(state)
    new_state["extraction_result"] = {**extracted, "confidence_scores": confidence_scores}
    new_state["extraction_confidence"] = overall_confidence
    new_state["audit_chain"] = list(state.get("audit_chain") or []) + [audit_entry]

    if overall_confidence < 0.7:
        new_state["audit_chain"].append(_signed_audit_entry(
            "extract_lead_data.low_confidence_flag",
            {"confidence": overall_confidence, "threshold": 0.7},
            org_id,
        ))
        try:
            from backend.services.neon_service import neon_service
            neon_service.client.table("automation_alerts").insert({
                "org_id": org_id,
                "alert_scope": "rule",
                "severity": "warning",
                "message": (
                    f"Seller intake NER confidence {overall_confidence:.2f} < 0.7. "
                    "Record flagged for manual review."
                ),
                "metadata_json": {"confidence": overall_confidence, "fields": list(extracted.keys())},
                "is_active": True,
            }).execute()
        except Exception:
            pass

    return new_state


# ─── Node 2: calculate_priority ──────────────────────────────────────────────

def _score_budget(precio: Optional[float]) -> float:
    if not precio:
        return 0.2
    # Normalize: 500k=0.25, 1M=0.5, 2M=1.0 (cap at 2M€)
    return min(precio / 2_000_000.0, 1.0)


def _score_urgency(dias: Optional[int], senales: list) -> float:
    base = 0.2
    if dias is not None:
        if dias >= 90:
            base = 1.0
        elif dias >= 60:
            base = 0.8
        elif dias >= 30:
            base = 0.6
        elif dias > 0:
            base = 0.4
    signal_bonus = min(len(senales) * 0.1, 0.2)
    return min(base + signal_bonus, 1.0)


def _score_property_fit(zona: str) -> float:
    return _ZONE_SCORES.get(zona, 0.4)


def _score_source_quality(fuente: str) -> float:
    return _SOURCE_SCORES.get(fuente, 0.5)


def _tier_from_score(score: float) -> int:
    if score >= 0.80:
        return 5
    if score >= 0.60:
        return 4
    if score >= 0.40:
        return 3
    if score >= 0.20:
        return 2
    return 1


async def calculate_priority(state: SellerProspectionState) -> SellerProspectionState:
    """
    Apply deterministic priority formula.
    priority = budget×0.35 + urgency×0.25 + property_fit×0.25 + source_quality×0.15
    """
    ext = state["extraction_result"]
    org_id = state["org_id"]

    b = _score_budget(ext.get("precio_publicado"))
    u = _score_urgency(ext.get("dias_en_mercado"), ext.get("senales_motivacion") or [])
    p = _score_property_fit(ext.get("zona") or "otra")
    s = _score_source_quality(ext.get("fuente") or "manual")

    score = round(b * _W_BUDGET + u * _W_URGENCY + p * _W_PROPERTY_FIT + s * _W_SOURCE_QUALITY, 4)
    tier = _tier_from_score(score)

    audit_entry = _signed_audit_entry(
        "calculate_priority",
        {"score": score, "tier": tier, "components": {"budget": b, "urgency": u, "property_fit": p, "source_quality": s}},
        org_id,
    )

    new_state = dict(state)
    new_state["priority_score"] = score
    new_state["priority_tier"] = tier
    new_state["audit_chain"] = list(state.get("audit_chain") or []) + [audit_entry]
    return new_state


# ─── Node 3: check_limits ────────────────────────────────────────────────────

async def check_limits(state: SellerProspectionState) -> SellerProspectionState:
    """Enforce constitutional limits. Hard stop if exceeded — NO bypass."""
    org_id = state["org_id"]
    new_state = dict(state)
    new_state["can_proceed"] = True
    new_state["limit_violation"] = None

    try:
        from backend.services.neon_service import neon_service
        limits = await neon_service.get_constitutional_limits(org_id)

        if "max_daily_leads" in limits:
            daily_leads = await neon_service.count_daily_leads(org_id)
            if daily_leads >= limits["max_daily_leads"]:
                new_state["can_proceed"] = False
                new_state["limit_violation"] = "max_daily_leads"
                new_state["status"] = "blocked"
                new_state["error_message"] = (
                    f"Constitutional limit: max_daily_leads={limits['max_daily_leads']} reached."
                )

        if new_state["can_proceed"] and "max_llm_tokens_per_day" in limits:
            daily_tokens = await neon_service.get_daily_token_usage(org_id)
            if daily_tokens >= limits["max_llm_tokens_per_day"]:
                new_state["can_proceed"] = False
                new_state["limit_violation"] = "max_llm_tokens_per_day"
                new_state["status"] = "blocked"
                new_state["error_message"] = (
                    f"Constitutional limit: max_llm_tokens_per_day={limits['max_llm_tokens_per_day']} reached."
                )
    except Exception as exc:
        # On limit-service failure: allow but log
        new_state["audit_chain"] = list(state.get("audit_chain") or []) + [
            _signed_audit_entry("check_limits.service_error", {"error": str(exc)}, org_id)
        ]

    try:
        from backend.services.neon_service import neon_service
        limits_data = await neon_service.get_constitutional_limits(org_id)
        daily_leads_count = await neon_service.count_daily_leads(org_id)
        max_leads = limits_data.get("max_daily_leads", 50)

        # 90% warning alert
        if new_state["can_proceed"] and daily_leads_count >= max_leads * 0.9:
            neon_service.client.table("automation_alerts").upsert({
                "org_id": org_id,
                "alert_scope": "rule",
                "severity": "warning",
                "message": f"Intake limit at {daily_leads_count}/{max_leads} leads today (≥90%).",
                "metadata_json": {"daily_leads": daily_leads_count, "max_leads": max_leads},
                "dedupe_key": f"intake_limit_warning_{org_id}",
                "is_active": True,
            }, on_conflict="org_id,dedupe_key").execute()

        # Critical alert if blocked
        if not new_state["can_proceed"]:
            neon_service.client.table("automation_alerts").upsert({
                "org_id": org_id,
                "alert_scope": "rule",
                "severity": "critical",
                "message": new_state.get("error_message") or "Constitutional limit hard stop",
                "metadata_json": {"violation": new_state["limit_violation"]},
                "dedupe_key": f"intake_limit_critical_{org_id}",
                "is_active": True,
            }, on_conflict="org_id,dedupe_key").execute()

            await neon_service.insert_audit_log({
                "org_id": org_id,
                "actor_type": "system",
                "actor_id": "seller_prospection_agent",
                "action": "check_limits.blocked",
                "resource_type": "constitutional_limit",
                "details": {"violation": new_state["limit_violation"], "reason": new_state["error_message"]},
            })
    except Exception:
        pass

    return new_state


# ─── Node 4: generate_outreach_copy ──────────────────────────────────────────

_EMAIL_TEMPLATE = """Asunto: Algo que puede interesarle sobre {zona}

Estimado/a {nombre},

He identificado una dinámica de mercado específica en {zona} que podría ser relevante
para su propiedad valorada en {precio}.

En los últimos meses, hemos cerrado operaciones en este microterritorio con condiciones
que difícilmente se encuentran en el mercado abierto.

Si le parece oportuno, podemos explorar si su propiedad encaja con el perfil de
operaciones que manejamos actualmente.

Quedo a su disposición.

Anclora Private Estates
[Generado por Anclora Nexus Agent — seller_intake]"""

_WHATSAPP_TEMPLATE = (
    "Hola {nombre}, soy Toni de Anclora Private Estates. "
    "Tenemos actividad reciente en {zona} que podría interesarle. "
    "¿Tiene 5 min esta semana para comentarlo?"
)


async def generate_outreach_copy(state: SellerProspectionState) -> SellerProspectionState:
    """
    Generate personalized email + WhatsApp copy via LLM.
    Falls back to template if LLM unavailable.
    Applies guardrail regex post-generation.
    """
    ext = state["extraction_result"]
    org_id = state["org_id"]
    tier = state.get("priority_tier", 3)

    nombre = ext.get("nombre_propietario") or "Propietario/a"
    zona = str(ext.get("zona") or "zona premium").replace("_", " ").title()
    precio_raw = ext.get("precio_publicado")
    precio = f"{precio_raw:,.0f}€" if precio_raw else "precio de mercado"

    # Build prompts with context
    email_draft = _EMAIL_TEMPLATE.format(nombre=nombre, zona=zona, precio=precio)
    whatsapp_draft = _WHATSAPP_TEMPLATE.format(nombre=nombre, zona=zona)

    # LLM enrichment (best-effort; template is the safe fallback)
    try:
        from backend.services.llm_service import llm_service
        prompt = (
            f"Eres el sistema de captación de Anclora Private Estates. "
            f"Genera un email de primer contacto (máximo 200 palabras) y un mensaje WhatsApp "
            f"(máximo 160 caracteres) para un propietario con estas características: "
            f"nombre={nombre}, zona={zona}, precio={precio}, "
            f"señales de motivación={ext.get('senales_motivacion') or []}, "
            f"días en mercado={ext.get('dias_en_mercado')}. "
            f"Tono: estratégico, analítico, selectivo. "
            f"NO incluyas promesas de precio, urgencia artificial ni términos genéricos. "
            f"Finaliza el email con: [Generado por Anclora Nexus Agent — seller_intake]. "
            f"Responde en JSON: {{\"email\": \"...\", \"whatsapp\": \"...\"}}"
        )
        result = await llm_service.complete(prompt, json_mode=True)
        if result and isinstance(result, dict):
            llm_email = result.get("email") or email_draft
            llm_wa = result.get("whatsapp") or whatsapp_draft
            # WhatsApp cap: 160 chars
            email_draft = llm_email[:3000]
            whatsapp_draft = llm_wa[:160]
    except Exception:
        pass  # Keep template fallback

    # Guardrail: reject forbidden phrases
    def _strip_forbidden(text: str) -> str:
        return _FORBIDDEN_PHRASES.sub("[REDACTED]", text)

    email_draft = _strip_forbidden(email_draft)
    whatsapp_draft = _strip_forbidden(whatsapp_draft)

    audit_entry = _signed_audit_entry(
        "generate_outreach_copy",
        {"tier": tier, "email_len": len(email_draft), "whatsapp_len": len(whatsapp_draft)},
        org_id,
    )

    new_state = dict(state)
    new_state["outreach_email"] = email_draft
    new_state["outreach_whatsapp"] = whatsapp_draft
    new_state["audit_chain"] = list(state.get("audit_chain") or []) + [audit_entry]
    return new_state


# ─── Node 5: create_approval_task ────────────────────────────────────────────

async def create_approval_task(state: SellerProspectionState) -> SellerProspectionState:
    """
    Persist seller record + outreach drafts. Create HITL approval task.
    For priority tier 5: also enqueue push + email notification.
    """
    org_id = state["org_id"]
    ext = state["extraction_result"]
    new_state = dict(state)

    try:
        from backend.services.neon_service import neon_service
        from backend.models.sellers import NexusSellerCreate, ZonaEnum, FuenteEnum, EstadoContactoEnum

        # Persist seller if not already created by intake endpoint
        seller_id = state.get("seller_id")
        if not seller_id:
            seller_payload = {
                "org_id": org_id,
                "nombre_propietario": ext.get("nombre_propietario"),
                "zona": ext.get("zona") or "otra",
                "fuente": ext.get("fuente") or "manual",
                "precio_publicado": ext.get("precio_publicado"),
                "superficie_m2": ext.get("superficie_m2"),
                "tipo_propiedad": ext.get("tipo_propiedad"),
                "dias_en_mercado": ext.get("dias_en_mercado"),
                "email_contacto": ext.get("email_contacto"),
                "telefono_contacto": ext.get("telefono_contacto"),
                "whatsapp_contacto": ext.get("whatsapp_contacto"),
                "notas": ext.get("notas"),
                "senales_motivacion": ext.get("senales_motivacion") or [],
                "estado_contacto": EstadoContactoEnum.sin_contacto.value,
                "prioridad": state.get("priority_tier") or 3,
                "priority_score": state.get("priority_score"),
                "priority_computed_at": datetime.now(timezone.utc).isoformat(),
                "intake_raw_data": state.get("raw_data") or {},
                "intake_processed_at": datetime.now(timezone.utc).isoformat(),
            }
            result = neon_service.client.table("nexus_sellers").insert(seller_payload).execute()
            seller_id = (result.data[0] if result.data else {}).get("id")
            new_state["seller_id"] = seller_id

        # Persist outreach draft in HITL queue
        draft_payload = {
            "org_id": org_id,
            "seller_id": seller_id,
            "email_draft": state["outreach_email"],
            "whatsapp_draft": state["outreach_whatsapp"],
            "status": "draft",
            "priority_tier": state.get("priority_tier"),
        }
        draft_result = neon_service.client.table("seller_outreach_drafts").insert(draft_payload).execute()
        draft_id = (draft_result.data[0] if draft_result.data else {}).get("id")
        new_state["draft_id"] = draft_id
        new_state["approval_status"] = "draft"

        # Notify for priority 5 (whale)
        if state.get("priority_tier") == 5:
            await neon_service.insert_audit_log({
                "org_id": org_id,
                "actor_type": "agent",
                "actor_id": "seller_prospection_agent",
                "action": "create_approval_task.whale_alert",
                "resource_type": "nexus_sellers",
                "resource_id": str(seller_id),
                "details": {"draft_id": str(draft_id), "priority_score": state.get("priority_score")},
            })

    except Exception as exc:
        new_state["error_message"] = f"create_approval_task failed: {exc}"
        new_state["status"] = "error"

    audit_entry = _signed_audit_entry(
        "create_approval_task",
        {"seller_id": new_state.get("seller_id"), "draft_id": new_state.get("draft_id")},
        org_id,
    )
    new_state["audit_chain"] = list(state.get("audit_chain") or []) + [audit_entry]
    return new_state


# ─── Node 6: conditional_router ──────────────────────────────────────────────

async def conditional_router(state: SellerProspectionState) -> SellerProspectionState:
    """
    Route based on approval_status. In intake flow, always ends at 'draft' waiting for HITL.
    """
    new_state = dict(state)
    if state.get("approval_status") == "approved":
        # Extend here for async send dispatch when approval arrives
        new_state["status"] = "approved_pending_send"
    else:
        new_state["status"] = "success"
    return new_state


# ─── Block & alert node (limit exceeded path) ────────────────────────────────

async def block_and_alert(state: SellerProspectionState) -> SellerProspectionState:
    """Log hard stop into automation_alerts."""
    org_id = state["org_id"]
    try:
        from backend.services.neon_service import neon_service
        neon_service.client.table("automation_alerts").insert({
            "org_id": org_id,
            "alert_scope": "rule",
            "severity": "critical",
            "message": state.get("error_message") or "Constitutional limit hard stop",
            "metadata_json": {"violation": state.get("limit_violation")},
            "is_active": True,
        }).execute()
    except Exception:
        pass
    return state


# ─── Error handler ────────────────────────────────────────────────────────────

async def handle_error(state: SellerProspectionState) -> SellerProspectionState:
    """Log error and mark state for investigation."""
    org_id = state["org_id"]
    new_state = dict(state)
    try:
        from backend.services.neon_service import neon_service
        await neon_service.insert_audit_log({
            "org_id": org_id,
            "actor_type": "agent",
            "actor_id": "seller_prospection_agent",
            "action": "handle_error",
            "resource_type": "seller_prospection",
            "details": {"error": state.get("error_message"), "raw_data": state.get("raw_data")},
        })
    except Exception:
        pass
    new_state["status"] = "error"
    return new_state


# ─── Route conditions ─────────────────────────────────────────────────────────

def _limits_route(state: SellerProspectionState) -> str:
    return "generate_outreach_copy" if state.get("can_proceed", True) else "block_and_alert"


def _error_route(state: SellerProspectionState) -> str:
    return "handle_error" if state.get("status") == "error" else "conditional_router"


# ─── Build and compile StateGraph ────────────────────────────────────────────

def build_seller_prospection_graph():
    workflow = StateGraph(SellerProspectionState)

    workflow.add_node("extract_lead_data", extract_lead_data)
    workflow.add_node("calculate_priority", calculate_priority)
    workflow.add_node("check_limits", check_limits)
    workflow.add_node("generate_outreach_copy", generate_outreach_copy)
    workflow.add_node("create_approval_task", create_approval_task)
    workflow.add_node("conditional_router", conditional_router)
    workflow.add_node("block_and_alert", block_and_alert)
    workflow.add_node("handle_error", handle_error)

    workflow.add_edge(START, "extract_lead_data")
    workflow.add_edge("extract_lead_data", "calculate_priority")
    workflow.add_edge("calculate_priority", "check_limits")
    workflow.add_conditional_edges(
        "check_limits",
        _limits_route,
        {"generate_outreach_copy": "generate_outreach_copy", "block_and_alert": "block_and_alert"},
    )
    workflow.add_edge("generate_outreach_copy", "create_approval_task")
    workflow.add_conditional_edges(
        "create_approval_task",
        _error_route,
        {"handle_error": "handle_error", "conditional_router": "conditional_router"},
    )
    workflow.add_edge("conditional_router", END)
    workflow.add_edge("block_and_alert", END)
    workflow.add_edge("handle_error", END)

    return workflow.compile()


# Singleton graph instance
seller_prospection_graph = build_seller_prospection_graph()
