from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from .notebooklm_service import NOTEBOOK_ID, NOTEBOOK_NAME
from .neon_service import NeonService


DEFAULT_PACK_KEY = os.getenv("INTELLIGENCE_DEFAULT_PACK_KEY", "mallorca-suroeste-2026")
DEFAULT_PACK_LABEL = os.getenv("INTELLIGENCE_DEFAULT_PACK_LABEL", NOTEBOOK_NAME)
DEFAULT_PACK_SOURCE_MODE = os.getenv("INTELLIGENCE_DEFAULT_PACK_SOURCE_MODE", "live_sync_pack")
DEFAULT_PACK_LANGUAGE = os.getenv("INTELLIGENCE_DEFAULT_PACK_LANGUAGE", "es")
DEFAULT_PACK_MARKET_SCOPE = os.getenv("INTELLIGENCE_DEFAULT_PACK_MARKET_SCOPE", "seller")


def _normalize_pack_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or f"pack-{uuid4().hex[:8]}"


def _serialize_pack(row: dict[str, Any], stats: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    stats = stats or {}
    last_synced_at = row.get("last_synced_at") or stats.get("last_synced_at")
    age_hours = None
    if last_synced_at:
        try:
            parsed = datetime.fromisoformat(str(last_synced_at).replace("Z", "+00:00"))
            age_hours = round((datetime.now(timezone.utc) - parsed).total_seconds() / 3600, 1)
        except ValueError:
            age_hours = None
    return {
        "id": row.get("id"),
        "org_id": row.get("org_id"),
        "pack_key": row.get("pack_key"),
        "pack_label": row.get("pack_label"),
        "notebook_id": row.get("notebook_id"),
        "notebook_name": row.get("notebook_name"),
        "market_scope": row.get("market_scope") or DEFAULT_PACK_MARKET_SCOPE,
        "zone_scope": row.get("zone_scope") or [],
        "language_code": row.get("language_code") or DEFAULT_PACK_LANGUAGE,
        "source_mode": row.get("source_mode") or DEFAULT_PACK_SOURCE_MODE,
        "status": row.get("status") or "active",
        "is_default": bool(row.get("is_default")),
        "metadata": row.get("metadata") or {},
        "last_synced_at": last_synced_at,
        "age_hours": age_hours,
        "insight_count": int(stats.get("insight_count") or 0),
        "zones_with_data": stats.get("zones_with_data") or [],
        "synthetic": bool(row.get("synthetic")),
    }


def _build_fallback_pack(org_id: str) -> dict[str, Any]:
    return _serialize_pack(
        {
            "id": f"legacy-{org_id}",
            "org_id": org_id,
            "pack_key": DEFAULT_PACK_KEY,
            "pack_label": DEFAULT_PACK_LABEL,
            "notebook_id": NOTEBOOK_ID,
            "notebook_name": NOTEBOOK_NAME,
            "market_scope": DEFAULT_PACK_MARKET_SCOPE,
            "zone_scope": ["general", "calvia", "andratx"],
            "language_code": DEFAULT_PACK_LANGUAGE,
            "source_mode": DEFAULT_PACK_SOURCE_MODE,
            "status": "active",
            "is_default": True,
            "metadata": {"legacy_fallback": True},
            "synthetic": True,
        }
    )


async def _collect_insight_stats(db: NeonService, org_id: str) -> dict[str, dict[str, Any]]:
    try:
        response = (
            db.client.table("notebooklm_insights")
            .select("notebook_id, zona, created_at")
            .eq("org_id", str(org_id))
            .order("created_at", desc=True)
            .limit(500)
            .execute()
        )
    except Exception:
        return {}

    stats: dict[str, dict[str, Any]] = {}
    for row in response.data or []:
        notebook_id = str(row.get("notebook_id") or "")
        if not notebook_id:
            continue
        bucket = stats.setdefault(
            notebook_id,
            {"insight_count": 0, "zones_with_data": [], "last_synced_at": None},
        )
        bucket["insight_count"] += 1
        zona = row.get("zona") or "general"
        if zona not in bucket["zones_with_data"]:
            bucket["zones_with_data"].append(zona)
        if not bucket["last_synced_at"]:
            bucket["last_synced_at"] = row.get("created_at")
    return stats


async def list_intelligence_packs(db: NeonService, org_id: str) -> list[dict[str, Any]]:
    stats = await _collect_insight_stats(db=db, org_id=org_id)
    try:
        response = (
            db.client.table("intelligence_packs")
            .select("*")
            .eq("org_id", str(org_id))
            .order("is_default", desc=True)
            .order("created_at", desc=True)
            .execute()
        )
    except Exception:
        fallback = _build_fallback_pack(org_id)
        return [_serialize_pack(fallback, stats=stats.get(fallback["notebook_id"]))]

    rows = response.data or []
    if not rows:
        fallback = _build_fallback_pack(org_id)
        return [_serialize_pack(fallback, stats=stats.get(fallback["notebook_id"]))]

    return [_serialize_pack(row, stats=stats.get(str(row.get("notebook_id") or ""))) for row in rows]


async def get_intelligence_pack(db: NeonService, org_id: str, pack_id: str) -> Optional[dict[str, Any]]:
    packs = await list_intelligence_packs(db=db, org_id=org_id)
    for pack in packs:
        if str(pack.get("id")) == str(pack_id):
            return pack
    return None


async def get_active_intelligence_pack(db: NeonService, org_id: str) -> dict[str, Any]:
    packs = await list_intelligence_packs(db=db, org_id=org_id)
    for pack in packs:
        if pack.get("is_default") and pack.get("status") != "archived":
            return pack
    for pack in packs:
        if pack.get("status") == "active":
            return pack
    return packs[0]


async def create_intelligence_pack(
    db: NeonService,
    org_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    pack_key = _normalize_pack_key(str(payload.get("pack_key") or payload.get("pack_label") or payload.get("notebook_name") or "pack"))
    is_default = bool(payload.get("is_default"))
    if is_default:
        (
            db.client.table("intelligence_packs")
            .update({"is_default": False})
            .eq("org_id", str(org_id))
            .eq("is_default", True)
            .execute()
        )

    row = {
        "org_id": str(org_id),
        "pack_key": pack_key,
        "pack_label": payload.get("pack_label") or payload.get("notebook_name") or NOTEBOOK_NAME,
        "notebook_id": payload.get("notebook_id") or NOTEBOOK_ID,
        "notebook_name": payload.get("notebook_name") or NOTEBOOK_NAME,
        "market_scope": payload.get("market_scope") or DEFAULT_PACK_MARKET_SCOPE,
        "zone_scope": payload.get("zone_scope") or [],
        "language_code": payload.get("language_code") or DEFAULT_PACK_LANGUAGE,
        "source_mode": payload.get("source_mode") or "notebooklm_manual",
        "status": payload.get("status") or "active",
        "is_default": is_default,
        "metadata": payload.get("metadata") or {},
        "last_synced_at": payload.get("last_synced_at"),
    }
    response = db.client.table("intelligence_packs").insert(row).execute()
    created = response.data[0] if response.data else row
    stats = await _collect_insight_stats(db=db, org_id=org_id)
    return _serialize_pack(created, stats=stats.get(str(created.get("notebook_id") or "")))


async def update_intelligence_pack(
    db: NeonService,
    org_id: str,
    pack_id: str,
    payload: dict[str, Any],
) -> Optional[dict[str, Any]]:
    current = await get_intelligence_pack(db=db, org_id=org_id, pack_id=pack_id)
    if not current or current.get("synthetic"):
        return None

    update_payload = {
        key: value
        for key, value in payload.items()
        if key in {
            "pack_label",
            "notebook_id",
            "notebook_name",
            "market_scope",
            "zone_scope",
            "language_code",
            "source_mode",
            "status",
            "metadata",
            "last_synced_at",
            "is_default",
        }
        and value is not None
    }

    if update_payload.get("is_default"):
        (
            db.client.table("intelligence_packs")
            .update({"is_default": False})
            .eq("org_id", str(org_id))
            .eq("is_default", True)
            .execute()
        )

    response = (
        db.client.table("intelligence_packs")
        .update(update_payload)
        .eq("org_id", str(org_id))
        .eq("id", str(pack_id))
        .execute()
    )
    updated = response.data[0] if response.data else None
    if not updated:
        return None
    stats = await _collect_insight_stats(db=db, org_id=org_id)
    return _serialize_pack(updated, stats=stats.get(str(updated.get("notebook_id") or "")))
