"""
Seller Outreach Batch Skill

Generates dossier + first-contact drafts for high-priority sellers that do not
yet have an email draft stored in seller_interactions.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

from backend.services.llm_service import LLMService
from backend.services.org_context_service import resolve_legacy_org_id
from backend.services.neon_service import NeonService
from backend.skills.whale_dossier import run_whale_dossier


async def run_seller_outreach_batch(
    data: Dict[str, Any],
    llm: LLMService,
    db: NeonService,
) -> Dict[str, Any]:
    org_id = resolve_legacy_org_id(data.get("org_id"), "seller_outreach_batch")
    prioridad_min = int(data.get("prioridad_min", 4))
    limit = int(data.get("limit", 5))

    sellers_resp = (
        db.client.table("nexus_sellers")
        .select("id,nombre_propietario,zona,prioridad")
        .eq("org_id", org_id)
        .gte("prioridad", prioridad_min)
        .in_("estado_contacto", ["sin_contacto", "primer_contacto", "en_seguimiento"])
        .order("prioridad", desc=True)
        .order("fecha_deteccion", desc=True)
        .limit(max(limit * 3, limit))
        .execute()
    )
    sellers = sellers_resp.data or []

    processed: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    for seller in sellers:
        if len(processed) >= limit:
            break

        interactions = (
            db.client.table("seller_interactions")
            .select("id")
            .eq("org_id", org_id)
            .eq("seller_id", seller["id"])
            .eq("tipo", "email_draft")
            .limit(1)
            .execute()
        )
        if interactions.data:
            skipped.append({"seller_id": seller["id"], "reason": "draft_exists"})
            continue

        result = await run_whale_dossier(
            data={"seller_id": seller["id"], "org_id": org_id},
            llm=llm,
            db=db,
        )
        if result.get("status") == "error":
            skipped.append({"seller_id": seller["id"], "reason": result.get("reason", "error")})
            continue

        processed.append(
            {
                "seller_id": seller["id"],
                "nombre": result.get("nombre"),
                "zona": result.get("zona"),
                "email_subject": result.get("email_subject"),
            }
        )

    return {
        "status": "success",
        "prioridad_min": prioridad_min,
        "limit": limit,
        "processed_count": len(processed),
        "processed": processed,
        "skipped": skipped,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
