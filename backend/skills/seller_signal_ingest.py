"""
Seller Signal Ingest Skill

Normalizes seller-side signals and persists them into nexus_sellers.
This acts as the operational bridge between an external scraper/feed and the
internal seller acquisition pipeline.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.models.sellers import EstadoContactoEnum, FuenteEnum, NexusSellerCreate, ZonaEnum
from backend.services.llm_service import LLMService
from backend.services.org_context_service import resolve_legacy_org_id
from backend.services.sellers_service import create_seller
from backend.services.neon_service import NeonService

ZONE_MAP = {
    "andratx": "andratx",
    "calvia": "calvia",
    "calvià": "calvia",
    "son_ferrer": "son_ferrer",
    "santa_ponca": "santa_ponca",
    "santa ponca": "santa_ponca",
    "paguera": "paguera",
    "portals_nous": "portals_nous",
    "portals nous": "portals_nous",
    "bendinat": "bendinat",
    "punta_negra": "punta_negra",
    "punta negra": "punta_negra",
    "costa_den_blanes": "costa_den_blanes",
    "costa d'en blanes": "costa_den_blanes",
    "port_adriano": "port_adriano",
    "port adriano": "port_adriano",
    "palma": "palma",
}

SOURCE_MAP = {
    "idealista": "idealista",
    "fotocasa": "fotocasa",
    "fsbo": "fsbo",
    "str_enforcement": "str_enforcement",
    "manual": "manual",
    "referral": "referral",
    "scraping": "scraping",
}


def _normalize_zone(raw: Optional[str]) -> str:
    if not raw:
        return "otra"
    normalized = raw.strip().lower().replace("-", "_")
    return ZONE_MAP.get(normalized, "otra")


def _normalize_source(raw: Optional[str]) -> str:
    if not raw:
        return "scraping"
    normalized = raw.strip().lower()
    return SOURCE_MAP.get(normalized, "scraping")


def _derive_priority(signal: Dict[str, Any]) -> int:
    price = float(signal.get("precio_publicado") or 0)
    dom = int(signal.get("dias_en_mercado") or 0)
    triggers = [str(item).lower() for item in (signal.get("senales_motivacion") or [])]

    score = 3
    if price >= 2_500_000:
        score += 1
    if dom >= 180:
        score += 1
    if any(token in triggers for token in {"fsbo", "herencia", "bajada_precio", "str_enforcement"}):
        score += 1

    return min(5, max(1, score))


def _build_dedupe_query(db: NeonService, org_id: str, signal: Dict[str, Any]):
    anuncio_url = signal.get("anuncio_url")
    website_url = signal.get("website_url")
    direccion = signal.get("direccion")
    zona = _normalize_zone(signal.get("zona"))

    if anuncio_url:
        return (
            db.client.table("nexus_sellers")
            .select("id")
            .eq("org_id", org_id)
            .eq("anuncio_url", anuncio_url)
            .limit(1)
        )
    if website_url:
        return (
            db.client.table("nexus_sellers")
            .select("id")
            .eq("org_id", org_id)
            .eq("website_url", website_url)
            .limit(1)
        )
    return (
        db.client.table("nexus_sellers")
        .select("id")
        .eq("org_id", org_id)
        .eq("direccion", direccion)
        .eq("zona", zona)
        .limit(1)
    )


async def run_seller_signal_ingest(
    data: Dict[str, Any],
    llm: LLMService,
    db: NeonService,
) -> Dict[str, Any]:
    signals = data.get("signals") or []
    org_id = resolve_legacy_org_id(data.get("org_id"), "seller_signal_ingest")
    snapshot_id = data.get("snapshot_id", "manual")

    if not isinstance(signals, list) or not signals:
        return {
            "status": "skipped",
            "reason": "No seller signals provided.",
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }

    created = 0
    skipped = 0
    failures: List[Dict[str, Any]] = []
    created_ids: List[str] = []

    for signal in signals:
        try:
            existing = _build_dedupe_query(db, org_id, signal).execute()
            if existing.data:
                skipped += 1
                continue

            zona_value = _normalize_zone(signal.get("zona"))
            fuente_value = _normalize_source(signal.get("fuente"))
            prioridad = int(signal.get("prioridad") or _derive_priority(signal))

            payload = NexusSellerCreate(
                nombre_propietario=signal.get("nombre_propietario"),
                empresa=signal.get("empresa"),
                website_url=signal.get("website_url"),
                anuncio_url=signal.get("anuncio_url"),
                email_contacto=signal.get("email_contacto"),
                telefono_contacto=signal.get("telefono_contacto"),
                whatsapp_contacto=signal.get("whatsapp_contacto"),
                direccion=signal.get("direccion"),
                zona=ZonaEnum(zona_value),
                fuente=FuenteEnum(fuente_value),
                precio_publicado=signal.get("precio_publicado"),
                precio_estimado=signal.get("precio_estimado"),
                superficie_m2=signal.get("superficie_m2"),
                tipo_propiedad=signal.get("tipo_propiedad"),
                dias_en_mercado=signal.get("dias_en_mercado"),
                datos_extraidos={
                    **(signal.get("datos_extraidos") or {}),
                    "snapshot_id": snapshot_id,
                    "ingested_via": "seller_signal_ingest",
                },
                estado_contacto=EstadoContactoEnum.sin_contacto,
                prioridad=prioridad,
                notas=signal.get("notas"),
                senales_motivacion=signal.get("senales_motivacion") or [],
            )
            row = await create_seller(db=db, org_id=org_id, data=payload)
            if row.get("id"):
                created_ids.append(str(row["id"]))
            created += 1
        except Exception as exc:
            failures.append(
                {
                    "direccion": signal.get("direccion"),
                    "anuncio_url": signal.get("anuncio_url"),
                    "error": str(exc),
                }
            )

    return {
        "status": "success",
        "snapshot_id": snapshot_id,
        "signals_received": len(signals),
        "sellers_created": created,
        "signals_skipped": skipped,
        "created_ids": created_ids,
        "failures": failures,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
