"""
Whale Dossier Skill — Gravity Claw Phase 4

Generates a compact seller workbench for a high-priority seller:
  - Captation dossier / argumentario
  - Email draft
  - WhatsApp draft
  - Call brief
  - Context brief for resuming the conversation later

All artifacts are persisted into seller_interactions so the commercial
workflow can resume without losing context.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict

from backend.services.llm_service import LLMService
from backend.services.org_context_service import resolve_legacy_org_id
from backend.services.seller_memory_service import seller_memory_service
from backend.services.neon_service import NeonService
from backend.services.notebooklm_service import get_latest_insights

ZONA_LABELS = {
    "andratx": "Andratx",
    "calvia": "Calvià",
    "son_ferrer": "Son Ferrer",
    "santa_ponca": "Santa Ponça",
    "paguera": "Paguera",
    "portals_nous": "Portals Nous",
    "bendinat": "Bendinat",
    "punta_negra": "Punta Negra",
    "costa_den_blanes": "Costa d'en Blanes",
    "port_adriano": "Port Adriano",
    "palma": "Palma",
    "otra": "Zona exclusiva",
}


async def run_whale_dossier(
    data: Dict[str, Any],
    llm: LLMService,
    db: NeonService,
) -> Dict[str, Any]:
    """
    Generate a captation dossier + multichannel outreach drafts for a Whale seller.

    Args:
        data: {"seller_id": "uuid", "org_id": "uuid" (optional)}
        llm: LLMService instance
        db: NeonService instance

    Returns:
        {
          "seller_id": "...",
          "argumentario": "...",
          "email_subject": "...",
          "email_body": "...",
          "whatsapp_body": "...",
          "call_brief": "...",
          "context_brief": "...",
          "zona_insight_used": True/False,
          "processed_at": "...",
        }
    """
    seller_id = data.get("seller_id")
    org_id = resolve_legacy_org_id(data.get("org_id"), "whale_dossier")

    if not seller_id:
        return {"status": "error", "reason": "Missing seller_id"}

    # ── 1. Load seller ────────────────────────────────────────────────────────
    seller_resp = (
        db.client.table("nexus_sellers")
        .select("*")
        .eq("org_id", org_id)
        .eq("id", seller_id)
        .maybe_single()
        .execute()
    )
    seller = seller_resp.data if seller_resp else None
    if not seller:
        return {"status": "error", "reason": f"Seller {seller_id} not found"}

    zona = seller.get("zona", "general")
    zona_label = ZONA_LABELS.get(zona, zona)
    nombre = seller.get("nombre_propietario") or "Propietario"
    precio = seller.get("precio_publicado")
    precio_str = f"€{precio:,.0f}".replace(",", ".") if precio else "precio no especificado"
    dom = seller.get("dias_en_mercado")
    dom_str = f"{dom} días en mercado" if dom else "tiempo en mercado no disponible"
    tipo = seller.get("tipo_propiedad") or "propiedad"
    senales = seller.get("senales_motivacion") or []
    senales_str = ", ".join(senales) if senales else "FSBO / estancamiento de mercado"

    # ── 2. Load zone intelligence ─────────────────────────────────────────────
    insights = await get_latest_insights(
        db=db,
        org_id=org_id,
        insight_type="territorial",
        zona=zona,
        limit=1,
    )
    # Fallback to general if no zone-specific insight
    if not insights:
        insights = await get_latest_insights(
            db=db, org_id=org_id, insight_type="territorial", zona="general", limit=1
        )

    zona_intel = insights[0]["response"] if insights else (
        f"Zona {zona_label} en el Suroeste de Mallorca. "
        "Alta demanda de compradores internacionales alemanes y suizos."
    )
    zona_intel_snippet = zona_intel[:600]
    zona_insight_used = bool(insights)

    recent_interactions_resp = (
        db.client.table("seller_interactions")
        .select("tipo, estado, contenido, resultado, metadata, created_at")
        .eq("org_id", org_id)
        .eq("seller_id", seller_id)
        .order("created_at", desc=True)
        .limit(6)
        .execute()
    )
    recent_interactions = recent_interactions_resp.data or []
    recent_interactions_text = "\n".join(
        [
            f"- {item.get('created_at')}: {item.get('tipo')} / {item.get('estado')} / "
            f"{(item.get('contenido') or '')[:180]}"
            for item in recent_interactions
        ]
    ) or "- Sin historial previo."
    memory = await seller_memory_service.search(
        db=db,
        org_id=org_id,
        seller_id=seller_id,
        query="seguimiento objeciones exclusividad siguiente paso captacion",
        limit=3,
    )
    memory_text = memory.retrieval_summary or "Sin memoria semántica reusable."

    # ── 3. Generate argumentario ──────────────────────────────────────────────
    argumentario_prompt = f"""Eres Toni Amengual, agente inmobiliario de eXp Global Spain \
especializado en el Suroeste de Mallorca (Andratx, Calvià, Santa Ponça, Portals, Punta Negra).

Genera un argumentario de captación personalizado y sofisticado para este propietario.

DATOS DEL PROPIETARIO:
- Nombre: {nombre}
- Zona: {zona_label}
- Tipo de propiedad: {tipo}
- Precio publicado: {precio_str}
- Días en mercado: {dom_str}
- Señales de motivación detectadas: {senales_str}

INTELIGENCIA TERRITORIAL DE {zona_label.upper()}:
{zona_intel_snippet}

MEMORIA COMERCIAL RECUPERADA:
{memory_text}

REGLAS:
- 3 párrafos máximo, cada uno con un argumento concreto
- Mencionar datos reales del mercado (usa los datos de inteligencia territorial)
- Posicionar el acceso a compradores internacionales de eXp como diferencial clave
- Tono sofisticado, no agresivo — como un asesor de confianza, no un vendedor
- Finalizar con una propuesta de valor clara

[Generado por Anclora Nexus Agent — whale_dossier]"""

    argumentario = await llm.generate_copy(argumentario_prompt)

    # ── 4. Generate email draft ───────────────────────────────────────────────
    email_prompt = f"""Eres Toni Amengual, agente inmobiliario de eXp Global Spain en Mallorca.

Escribe un email de primer contacto para este propietario. Debe ser conciso y abrir la puerta \
a una conversación, no vender directamente.

ARGUMENTARIO BASE:
{argumentario[:400]}

MEMORIA COMERCIAL:
{memory_text}

DATOS:
- Propietario: {nombre}
- Zona: {zona_label}
- Propiedad: {tipo} a {precio_str}

INSTRUCCIONES:
- Asunto: breve, personal, menciona la zona — NUNCA suene a spam
- Cuerpo: 4-5 líneas máximo
- Sin presión de ventas — proponer una llamada corta de 15 minutos
- Firma: Toni Amengual | Agente Inmobiliario eXp Global Spain | Suroeste Mallorca

Responde ÚNICAMENTE con JSON válido:
{{"subject": "...", "body": "..."}}"""

    email_raw = await llm.analyze(email_prompt)

    email_subject = "Consulta sobre su propiedad en " + zona_label
    email_body = email_raw

    try:
        parsed = _parse_json_payload(email_raw)
        email_subject = parsed.get("subject", email_subject)
        email_body = parsed.get("body", email_raw)
    except Exception:
        pass  # Keep raw text as body

    whatsapp_prompt = f"""Eres Toni Amengual. Redacta un primer mensaje de WhatsApp
profesional, breve y elegante para este propietario.

DATOS:
- Nombre: {nombre}
- Zona: {zona_label}
- Propiedad: {tipo} a {precio_str}
- Contexto comercial: {senales_str}

ARGUMENTARIO BASE:
{argumentario[:450]}

MEMORIA COMERCIAL:
{memory_text}

REGLAS:
- 4 líneas máximo
- tono cercano y premium
- no sonar invasivo
- cerrar proponiendo una llamada corta

Responde ÚNICAMENTE con JSON válido:
{{"body": "..."}}"""

    whatsapp_raw = await llm.analyze(whatsapp_prompt)
    whatsapp_body = whatsapp_raw
    try:
        whatsapp_body = _parse_json_payload(whatsapp_raw).get("body", whatsapp_raw)
    except Exception:
        pass

    call_brief_prompt = f"""Eres un sales strategist inmobiliario premium.

Genera un briefing de llamada de 6 bullets para Toni antes de llamar a este seller.

SELLER:
- Nombre: {nombre}
- Zona: {zona_label}
- Tipo: {tipo}
- Precio: {precio_str}
- Tiempo en mercado: {dom_str}
- Señales: {senales_str}

INTELIGENCIA TERRITORIAL:
{zona_intel_snippet}

HISTORIAL RECIENTE:
{recent_interactions_text}

MEMORIA COMERCIAL:
{memory_text}

Incluye:
- hipótesis de motivación
- argumento local principal
- objeción probable
- respuesta sugerida
- CTA de cierre de llamada
"""
    call_brief = await llm.generate_copy(call_brief_prompt)

    context_brief_prompt = f"""Resume el estado actual de este seller para que Toni pueda
retomar la conversación sin leer todo el historial.

SELLER:
- Nombre: {nombre}
- Zona: {zona_label}
- Tipo: {tipo}
- Precio: {precio_str}
- Tiempo en mercado: {dom_str}
- Señales: {senales_str}

ARGUMENTARIO:
{argumentario[:500]}

EMAIL DRAFT:
Asunto: {email_subject}
Cuerpo: {email_body[:400]}

HISTORIAL RECIENTE:
{recent_interactions_text}

MEMORIA COMERCIAL:
{memory_text}

Devuelve:
- un resumen ejecutivo de máximo 6 líneas
- próximos pasos concretos
- canal recomendado siguiente
"""
    context_brief = await llm.generate_copy(context_brief_prompt)

    # ── 5. Save argumentario to seller record ─────────────────────────────────
    db.client.table("nexus_sellers").update({
        "argumentario": argumentario,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("org_id", org_id).eq("id", seller_id).execute()

    # ── 6. Save interactions ──────────────────────────────────────────────────
    now = datetime.now(timezone.utc).isoformat()

    db.client.table("seller_interactions").insert([
        {
            "org_id": org_id,
            "seller_id": seller_id,
            "tipo": "dossier",
            "estado": "realizado",
            "contenido": argumentario,
            "metadata": {
                "zona_insight_used": zona_insight_used,
                "zona": zona,
                "artifact": "captation_dossier",
            },
        },
        {
            "org_id": org_id,
            "seller_id": seller_id,
            "tipo": "email_draft",
            "estado": "borrador",
            "contenido": email_body,
            "metadata": {
                "subject": email_subject,
                "zona": zona,
                "artifact": "email_draft",
            },
        },
        {
            "org_id": org_id,
            "seller_id": seller_id,
            "tipo": "whatsapp",
            "estado": "borrador",
            "contenido": whatsapp_body,
            "metadata": {
                "zona": zona,
                "artifact": "whatsapp_draft",
            },
        },
        {
            "org_id": org_id,
            "seller_id": seller_id,
            "tipo": "nota",
            "estado": "borrador",
            "contenido": call_brief,
            "metadata": {
                "zona": zona,
                "artifact": "call_brief",
            },
        },
        {
            "org_id": org_id,
            "seller_id": seller_id,
            "tipo": "nota",
            "estado": "realizado",
            "contenido": context_brief,
            "metadata": {
                "zona": zona,
                "artifact": "context_brief",
            },
        },
    ]).execute()

    return {
        "seller_id": seller_id,
        "nombre": nombre,
        "zona": zona_label,
        "argumentario": argumentario,
        "email_subject": email_subject,
        "email_body": email_body,
        "whatsapp_body": whatsapp_body,
        "call_brief": call_brief,
        "context_brief": context_brief,
        "zona_insight_used": zona_insight_used,
        "processed_at": now,
    }


def _parse_json_payload(raw: str) -> Dict[str, Any]:
    clean = raw.strip()
    if "```json" in clean:
        clean = clean.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in clean:
        clean = clean.split("```", 1)[1].split("```", 1)[0].strip()
    parsed = json.loads(clean)
    return parsed if isinstance(parsed, dict) else {"body": raw}
