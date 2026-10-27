"""
StateFox Telegram bridge.

Supervised bridge that parses raw StateFox Telegram output and imports
normalized listings into the prospection properties pipeline, optionally
deriving seller-side candidates through the unified ingestion perimeter.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.models.ingestion import SellerSignalIngestionPayload
from backend.models.prospection import PropertyCreate
from backend.services.ingestion_service import ingestion_service
from backend.services.prospection_service import prospection_service
from backend.services.statefox_adapter import classify_statefox_targets
from backend.services.neon_service import neon_service


PROPERTY_BLOCK_RE = re.compile(
    r"(?P<price>\d[\d\.]*)€\s*\|\s*(?P<title>[^|\n]+?)\s*\|\s*(?:https?://t\.me/StateFoxBot\?startapp=(?P<app_url>[^\s|]+)|\[app\])?\s*(?P<details>[^\n\r]+)",
    re.IGNORECASE,
)
PUBLIC_URL_RE = re.compile(
    r"https://es\.statefox\.com/public/ln/property/[^\s)]+",
    re.IGNORECASE,
)
ROOMS_RE = re.compile(r"(?P<bedrooms>\d+)\s*hab", re.IGNORECASE)
BATHS_RE = re.compile(r"(?P<bathrooms>\d+)\s*bañ", re.IGNORECASE)
AREA_RE = re.compile(r"(?P<area>\d+)\s*m2", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:(?:\+34|0034)[\s.-]*)?(?:\d[\s.-]*){9}(?!\d)")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+", re.IGNORECASE)

STATEFOX_SELLER_CONNECTOR = "statefox:telegram-bridge"
KNOWN_ZONES = {
    "andratx": "andratx",
    "calvia": "calvia",
    "calvià": "calvia",
    "son ferrer": "son_ferrer",
    "santa ponca": "santa_ponca",
    "paguera": "paguera",
    "portals nous": "portals_nous",
    "bendinat": "bendinat",
    "punta negra": "punta_negra",
    "costa d'en blanes": "costa_den_blanes",
    "costa den blanes": "costa_den_blanes",
    "port adriano": "port_adriano",
    "palma": "palma",
}
SELLER_SIGNAL_KEYWORDS = {
    "directo_propietario": ("directo propietario", "trato directo", "owner direct"),
    "sin_agencia": ("sin agencia", "no agencia", "particular"),
    "urgencia": ("urgente", "urge vender", "venta rapida", "venta rápida"),
    "herencia": ("herencia", "herederos"),
    "divorcio": ("divorcio", "separacion", "separación"),
}


def _price_to_float(raw: str) -> float:
    return float(raw.replace(".", "").replace(",", "."))


def _guess_property_type(title: str) -> str:
    lowered = title.lower()
    if lowered.startswith("ático"):
        return "atico"
    if lowered.startswith("estudio"):
        return "estudio"
    if lowered.startswith("piso"):
        return "piso"
    return "propiedad"


def _extract_phone(raw: str) -> Optional[str]:
    match = PHONE_RE.search(raw or "")
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(0))
    if digits.startswith("34") and len(digits) > 9:
        digits = digits[-9:]
    return digits if len(digits) >= 9 else None


def _extract_email(raw: str) -> Optional[str]:
    match = EMAIL_RE.search(raw or "")
    return match.group(0).strip().lower() if match else None


def _detect_seller_signals(raw: str) -> List[str]:
    lowered = (raw or "").lower()
    signals: List[str] = []
    for signal, keywords in SELLER_SIGNAL_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            signals.append("fsbo" if signal in {"directo_propietario", "sin_agencia"} else signal)
    if "whatsapp" in lowered:
        signals.append("whatsapp_disponible")
    return list(dict.fromkeys(signals))


def _resolve_zone(listing: Dict[str, Any], fallback_zone: Optional[str]) -> Optional[str]:
    if fallback_zone:
        return fallback_zone.strip().lower().replace("-", "_").replace(" ", "_")

    haystack = " ".join(
        str(part)
        for part in (
            listing.get("title"),
            listing.get("raw_details"),
            listing.get("public_url"),
        )
        if part
    ).lower()
    for token, normalized in KNOWN_ZONES.items():
        if token in haystack:
            return normalized
    return None


def _normalize_source_url(listing: Dict[str, Any]) -> Optional[str]:
    return listing.get("public_url") or listing.get("app_url")


def _build_listing_notes(listing: Dict[str, Any]) -> str:
    details = str(listing.get("raw_details") or "").strip()
    return f"StateFox Telegram Bridge supervised import | {details}" if details else "StateFox Telegram Bridge supervised import"


def _build_seller_signal(listing: Dict[str, Any], *, zone: Optional[str], city: Optional[str]) -> Dict[str, Any]:
    source_url = _normalize_source_url(listing)
    seller_signals = list(listing.get("seller_signals") or [])
    telefono_contacto = listing.get("telefono_contacto")
    whatsapp_contacto = listing.get("whatsapp_contacto")
    email_contacto = listing.get("email_contacto")
    resolved_zone = _resolve_zone(listing, zone)
    return {
        "external_id": source_url or listing["title"],
        "nombre_propietario": listing.get("nombre_propietario"),
        "anuncio_url": source_url,
        "email_contacto": email_contacto,
        "telefono_contacto": telefono_contacto,
        "whatsapp_contacto": whatsapp_contacto,
        "zona": resolved_zone,
        "fuente": "scraping",
        "precio_publicado": listing.get("price"),
        "superficie_m2": listing.get("area_m2"),
        "tipo_propiedad": listing.get("property_type"),
        "notas": _build_listing_notes(listing),
        "senales_motivacion": seller_signals,
        "datos_extraidos": {
            "city": city,
            "source_system": "manual",
            "source_portal": "other",
            "source_provider": "statefox",
            "public_url": listing.get("public_url"),
            "app_url": listing.get("app_url"),
            "raw_details": listing.get("raw_details"),
            "direct_owner": listing.get("direct_owner"),
            "no_agency": listing.get("no_agency"),
            "telefono_contacto": telefono_contacto,
            "whatsapp_contacto": whatsapp_contacto,
            "email_contacto": email_contacto,
            "ingested_via": "statefox_telegram_bridge",
        },
    }


def parse_statefox_raw(raw_text: str) -> Dict[str, Any]:
    public_urls = PUBLIC_URL_RE.findall(raw_text or "")
    listings: List[Dict[str, Any]] = []

    for idx, match in enumerate(PROPERTY_BLOCK_RE.finditer(raw_text or "")):
        details = match.group("details").strip()
        title = match.group("title").strip()
        listing: Dict[str, Any] = {
            "title": title,
            "price": _price_to_float(match.group("price")),
            "property_type": _guess_property_type(title),
            "app_url": (
                f"https://t.me/StateFoxBot?startapp={match.group('app_url')}"
                if match.group("app_url")
                else None
            ),
            "public_url": public_urls[idx] if idx < len(public_urls) else None,
            "raw_details": details,
            "seller_signals": _detect_seller_signals(details),
        }

        rooms = ROOMS_RE.search(details)
        baths = BATHS_RE.search(details)
        area = AREA_RE.search(details)
        if rooms:
            listing["bedrooms"] = int(rooms.group("bedrooms"))
        if baths:
            listing["bathrooms"] = int(baths.group("bathrooms"))
        if area:
            listing["area_m2"] = float(area.group("area"))

        phone = _extract_phone(details)
        email = _extract_email(details)
        lowered_details = details.lower()
        if phone:
            if "whatsapp" in lowered_details:
                listing["whatsapp_contacto"] = phone
            listing["telefono_contacto"] = phone
        if email:
            listing["email_contacto"] = email

        listing["direct_owner"] = any(
            keyword in lowered_details for keyword in ("directo propietario", "trato directo", "propietario", "particular")
        )
        listing["no_agency"] = any(
            keyword in lowered_details for keyword in ("sin agencia", "no agencia", "particular")
        )
        listing["notes"] = _build_listing_notes(listing)
        listing["source_url"] = _normalize_source_url(listing)
        listing["routing"] = classify_statefox_targets(listing)

        listings.append(listing)

    return {
        "listings": listings,
        "count": len(listings),
        "has_reproducible_app_links": any(item.get("app_url") for item in listings),
        "has_public_urls": any(item.get("public_url") for item in listings),
        "seller_candidate_count": sum(1 for item in listings if item.get("routing", {}).get("create_seller")),
    }


def _property_exists(org_id: str, source_url: Optional[str]) -> bool:
    if not source_url:
        return False
    for table in ("properties", "prospected_properties"):
        try:
            result = (
                neon_service.client.table(table)
                .select("id")
                .eq("org_id", org_id)
                .eq("source_url", source_url)
                .limit(1)
                .execute()
            )
            if result.data:
                return True
        except Exception:
            continue
    return False


async def import_statefox_listings(
    org_id: str,
    raw_text: str,
    zone: Optional[str] = None,
    city: Optional[str] = "Mallorca",
) -> Dict[str, Any]:
    parsed = parse_statefox_raw(raw_text)
    created: List[Dict[str, Any]] = []
    skipped: List[str] = []
    sellers_imported_count = 0
    sellers_duplicates_count = 0
    sellers_rejected_count = 0
    sellers_failed_count = 0
    trace_id = str(uuid4())
    snapshot_id = f"statefox-bridge:{trace_id}"

    for listing in parsed["listings"]:
        source_url = _normalize_source_url(listing)
        property_id = None
        property_duplicate = _property_exists(org_id, source_url)
        if property_duplicate:
            skipped.append(source_url or listing["title"])
        else:
            property_payload = PropertyCreate(
                source="statefox",
                source_url=source_url,
                title=listing["title"],
                zone=_resolve_zone(listing, zone),
                city=city,
                price=listing["price"],
                property_type=listing.get("property_type"),
                bedrooms=listing.get("bedrooms"),
                bathrooms=listing.get("bathrooms"),
                area_m2=listing.get("area_m2"),
                source_system="manual",
                source_portal="other",
                notes=listing.get("notes"),
            )
            row = await prospection_service.create_property(org_id, property_payload)
            property_id = row.get("id")

        routing = dict(listing.get("routing") or classify_statefox_targets(listing))
        seller_result = None
        if routing.get("create_seller"):
            seller_result = await ingestion_service.ingest_seller_signals(
                SellerSignalIngestionPayload(
                    org_id=org_id,
                    connector_name=STATEFOX_SELLER_CONNECTOR,
                    trace_id=trace_id,
                    snapshot_id=snapshot_id,
                    signals=[_build_seller_signal(listing, zone=zone, city=city)],
                )
            )
            sellers_imported_count += seller_result.get("created", 0)
            sellers_duplicates_count += seller_result.get("duplicates", 0)
            sellers_rejected_count += seller_result.get("rejected", 0)
            sellers_failed_count += seller_result.get("failed", 0)

        created.append(
            {
                "id": property_id,
                "title": listing["title"],
                "source_url": source_url,
                "property_created": not property_duplicate,
                "routing": routing,
                "seller_result": seller_result,
            }
        )

    return {
        "parsed_count": parsed["count"],
        "imported_count": sum(1 for item in created if item.get("property_created")),
        "skipped_count": len(skipped),
        "seller_candidate_count": parsed["seller_candidate_count"],
        "sellers_imported_count": sellers_imported_count,
        "sellers_duplicates_count": sellers_duplicates_count,
        "sellers_rejected_count": sellers_rejected_count,
        "sellers_failed_count": sellers_failed_count,
        "created": created,
        "skipped": skipped,
        "has_reproducible_app_links": parsed["has_reproducible_app_links"],
        "trace_id": trace_id,
        "snapshot_id": snapshot_id,
    }
