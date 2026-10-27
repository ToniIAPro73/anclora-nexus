"""
Seller Signal Source Runner

Operational skill that chooses the best available seller-side source:
1. Firecrawl FSBO live scraping
2. StateFox supervised live capture
3. Snapshot fallback
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.services.llm_service import LLMService
from backend.services.seller_signal_source_service import run_seller_signal_source_pipeline
from backend.services.neon_service import NeonService


async def run_seller_signal_source_run(
    data: Dict[str, Any],
    llm: Optional[LLMService],
    db: Optional[NeonService],
) -> Dict[str, Any]:
    zonas: Optional[List[str]] = data.get("zonas")
    zone: Optional[str] = data.get("zone")
    city = str(data.get("city") or "Mallorca")
    enrich_listings = bool(data.get("enrich_listings", False))
    enable_snapshot_fallback = bool(data.get("enable_snapshot_fallback", True))
    org_id = str(data["org_id"])

    return await run_seller_signal_source_pipeline(
        org_id=org_id,
        zonas=zonas,
        zone=zone,
        city=city,
        enrich_listings=enrich_listings,
        enable_snapshot_fallback=enable_snapshot_fallback,
    )
