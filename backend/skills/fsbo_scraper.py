"""
FSBO Scraper Skill — Gravity Claw Phase 3

Scrapes Idealista 'particulares' (FSBO) listings by zone using Firecrawl
and feeds detected sellers into nexus_sellers via seller_signal_ingest.

Usage via /api/skills/run:
  {
    "skill": "fsbo_scraper",
    "data": {
      "zonas": ["andratx", "calvia", "santa_ponca"],   // omit for all zones
      "enrich_listings": false                          // true = +1 credit per listing
    }
  }

Credit cost (Firecrawl free plan: 500/month):
  - 1 credit per zone search page
  - +1 credit per listing if enrich_listings=True
  Typical monthly cost for SW Mallorca: ~50-150 credits
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

from backend.models.ingestion import SellerSignalIngestionPayload
from backend.services.ingestion_service import ingestion_service
from backend.services.firecrawl_service import (
    IDEALISTA_ZONE_URLS,
    scrape_zone,
    scrape_listing,
)
from backend.services.llm_service import LLMService
from backend.services.org_context_service import resolve_legacy_org_id
from backend.services.neon_service import NeonService
FSBO_CONNECTOR = "firecrawl:idealista-fsbo"

# Priority zones — scrape these by default if no zones specified
DEFAULT_ZONES = [
    "andratx",
    "calvia",
    "santa_ponca",
    "son_ferrer",
    "paguera",
    "portals_nous",
    "costa_den_blanes",
]


async def run_fsbo_scraper(
    data: Dict[str, Any],
    llm: LLMService | None,
    db: NeonService | None,
) -> Dict[str, Any]:
    """
    Scrape Idealista FSBO listings by zone and ingest them into nexus_sellers.

    Args:
        data: {
            "zonas": ["andratx", "calvia"],  # optional, defaults to DEFAULT_ZONES
            "enrich_listings": False,         # set True to scrape each listing individually
            "org_id": "uuid"
        }

    Returns:
        Summary dict with zones scraped, sellers created, credits used.
    """
    org_id = resolve_legacy_org_id(data.get("org_id"), "fsbo_scraper")
    zonas: List[str] = data.get("zonas") or DEFAULT_ZONES
    enrich_listings: bool = bool(data.get("enrich_listings", False))

    snapshot_id = f"fsbo_scraper_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}"

    total_signals: List[Dict[str, Any]] = []
    zone_results = []
    total_credits = 0
    errors = []

    for zona in zonas:
        try:
            zone_result = await scrape_zone(zona)
            signals = zone_result.get("signals", [])
            credits = zone_result.get("credits_used", 0)
            total_credits += credits

            if zone_result.get("error"):
                errors.append({"zona": zona, "error": zone_result["error"]})
                zone_results.append({"zona": zona, "status": "error", "error": zone_result["error"]})
                continue

            # Optional: enrich each listing individually for contact info
            if enrich_listings and signals:
                enriched = []
                for signal in signals:
                    url = signal.get("anuncio_url")
                    if not url:
                        enriched.append(signal)
                        continue
                    try:
                        detailed = await scrape_listing(url, zona=zona)
                        if detailed:
                            # Merge: detailed data wins for contact info, keep original signals
                            merged = {**signal, **detailed}
                            merged["senales_motivacion"] = list(
                                set(signal.get("senales_motivacion", []) + detailed.get("senales_motivacion", []))
                            )
                            enriched.append(merged)
                        else:
                            enriched.append(signal)
                        total_credits += 1
                    except Exception as enrich_err:
                        enriched.append(signal)  # Keep basic signal on enrichment failure
                        errors.append({"zona": zona, "url": url, "error": str(enrich_err)})
                signals = enriched

            total_signals.extend(signals)
            zone_results.append({
                "zona": zona,
                "status": "ok",
                "listings_found": zone_result.get("listings_found", 0),
                "signals_extracted": len(signals),
                "credits_used": credits + (len(signals) if enrich_listings else 0),
                "source_url": zone_result.get("source_url"),
            })

        except Exception as exc:
            errors.append({"zona": zona, "error": str(exc)})
            zone_results.append({"zona": zona, "status": "error", "error": str(exc)})

    # Feed all signals into seller_signal_ingest (handles dedup + DB insert)
    ingest_result = {}
    if total_signals:
        ingest_result = await ingestion_service.ingest_seller_signals(
            SellerSignalIngestionPayload(
                org_id=org_id,
                connector_name=FSBO_CONNECTOR,
                snapshot_id=snapshot_id,
                signals=total_signals,
            )
        )

    return {
        "skill": "fsbo_scraper",
        "snapshot_id": snapshot_id,
        "zonas_scrapeadas": len(zone_results),
        "zone_results": zone_results,
        "total_signals_found": len(total_signals),
        "created": ingest_result.get("created", 0),
        "duplicates": ingest_result.get("duplicates", 0),
        "rejected": ingest_result.get("rejected", 0),
        "failed": ingest_result.get("failed", 0),
        "sellers_created": ingest_result.get("created", 0),
        "sellers_skipped_dedup": ingest_result.get("duplicates", 0),
        "total_credits_used": total_credits,
        "enrich_listings": enrich_listings,
        "errors": errors,
        "trace_id": ingest_result.get("trace_id"),
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
