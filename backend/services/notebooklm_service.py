"""
NotebookLM Intelligence Cache Service

Manages storage and retrieval of intelligence insights in Neon.
NotebookLM MCP is not directly callable from the production backend
(it uses browser session cookies). Claude Code queries NotebookLM and
writes the results here for the API to serve.

Flow: Claude Code (MCP) → NotebookLM → Save here → API serves from Neon
"""

import os
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from .neon_service import NeonService


NOTEBOOK_ID = os.getenv("NOTEBOOKLM_NOTEBOOK_ID", "9f003773-16c5-4fb4-ab37-7b6c230ab4da")
NOTEBOOK_NAME = os.getenv(
    "NOTEBOOKLM_NOTEBOOK_NAME",
    "Inteligencia Territorial Suroeste Mallorca 2026",
)

VALID_INSIGHT_TYPES = {
    "territorial", "cma", "competitive", "whale_audit",
    "buyer_profile", "market_signal"
}

VALID_ZONAS = {
    "andratx", "calvia", "son_ferrer", "santa_ponca",
    "paguera", "portals_nous", "bendinat", "punta_negra",
    "costa_den_blanes", "port_adriano", "palma", "general"
}


async def save_insight(
    db: NeonService,
    org_id: str,
    query: str,
    response: str,
    insight_type: str,
    zona: Optional[str] = None,
    metadata: Optional[dict] = None,
    notebook_id: str = NOTEBOOK_ID,
    notebook_name: str = NOTEBOOK_NAME,
) -> dict:
    """
    Save a NotebookLM query result to Neon for API consumption.

    Args:
        db: NeonService instance
        org_id: Organization UUID
        query: The question asked to NotebookLM
        response: The answer from NotebookLM
        insight_type: One of: territorial, cma, competitive, whale_audit,
                      buyer_profile, market_signal
        zona: Geographic zone (optional)
        metadata: Additional metadata (urgency, related_seller_id, etc.)
        notebook_id: NotebookLM notebook UUID
        notebook_name: Notebook display name

    Returns:
        Created insight record
    """
    if insight_type not in VALID_INSIGHT_TYPES:
        raise ValueError(
            f"Invalid insight_type '{insight_type}'. "
            f"Valid: {VALID_INSIGHT_TYPES}"
        )

    if zona and zona not in VALID_ZONAS:
        raise ValueError(
            f"Invalid zona '{zona}'. Valid: {VALID_ZONAS}"
        )

    row = {
        "org_id": str(org_id),
        "notebook_id": notebook_id,
        "notebook_name": notebook_name,
        "query": query,
        "response": response,
        "insight_type": insight_type,
        "zona": zona,
        "metadata": metadata or {},
    }

    result = db.client.table("notebooklm_insights").insert(row).execute()
    return result.data[0] if result.data else row


async def get_latest_insights(
    db: NeonService,
    org_id: str,
    insight_type: Optional[str] = None,
    zona: Optional[str] = None,
    notebook_id: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """
    Retrieve the most recent intelligence insights from Neon.

    Args:
        db: NeonService instance
        org_id: Organization UUID
        insight_type: Filter by type (optional)
        zona: Filter by geographic zone (optional)
        limit: Maximum number of results (default 10)

    Returns:
        List of insight records ordered by created_at DESC
    """
    query = (
        db.client.table("notebooklm_insights")
        .select("*")
        .eq("org_id", str(org_id))
        .order("created_at", desc=True)
        .limit(limit)
    )

    if insight_type:
        query = query.eq("insight_type", insight_type)

    if zona:
        query = query.eq("zona", zona)

    if notebook_id:
        query = query.eq("notebook_id", notebook_id)

    result = query.execute()
    return result.data or []


async def get_territorial_summary(
    db: NeonService,
    org_id: str,
    notebook_id: Optional[str] = None,
) -> dict:
    """
    Retrieve the latest territorial insight per zone for the Radar Territorial
    dashboard widget.

    Returns:
        Dict with zones as keys and their latest insight as value
    """
    result = (
        db.client.table("notebooklm_insights")
        .select("zona, response, created_at, metadata")
        .eq("org_id", str(org_id))
        .eq("insight_type", "territorial")
    )
    if notebook_id:
        result = result.eq("notebook_id", notebook_id)
    result = result.order("created_at", desc=True).limit(50).execute()

    # Keep only the most recent insight per zone
    summary: dict = {}
    for row in (result.data or []):
        zona = row.get("zona") or "general"
        if zona not in summary:
            summary[zona] = row

    return summary


async def get_vulnerabilidades(
    db: NeonService,
    org_id: str,
    notebook_id: Optional[str] = None,
) -> Optional[dict]:
    """
    Retrieve the most recent territorial vulnerabilities/opportunities insight.
    This corresponds to the vulnerabilidades.md content but served via API.
    """
    result = (
        db.client.table("notebooklm_insights")
        .select("*")
        .eq("org_id", str(org_id))
        .eq("insight_type", "territorial")
        .eq("zona", "general")
    )
    if notebook_id:
        result = result.eq("notebook_id", notebook_id)
    result = result.order("created_at", desc=True).limit(1).execute()

    data = result.data or []
    return data[0] if data else None
