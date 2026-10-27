"""Lead Intake API route (Phase 3 — Commercial Loop).

Accepts leads from external sources (e.g. Private Estates Landing),
validates required fields, assigns initial temperature, and rejects
duplicates (same email + source_system within 24h) with HTTP 409.

Requirements: 13.1, 13.2, 13.3, 13.4
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_org_id
from backend.models.lead_intake import (
    LeadIntakeRequest,
    LeadIntakeResponse,
)
from backend.services.neon_service import neon_service

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Temperature assignment logic
# ---------------------------------------------------------------------------

# Sources that indicate warm leads (direct high-intent channels)
WARM_SOURCES = frozenset({"private-estates-landing"})

# Sources that indicate hot leads (placeholder for future expansion)
HOT_SOURCES: frozenset[str] = frozenset()


def assign_temperature(source_system: str, metadata: dict[str, Any] | None) -> str:
    """Assign initial temperature score based on source and metadata.

    Rules:
    - Hot: reserved for future high-intent signals (e.g. repeat buyer, referral)
    - Warm: leads from private-estates-landing (direct property interest)
    - Cold: all other sources
    """
    if source_system in HOT_SOURCES:
        return "hot"
    if source_system in WARM_SOURCES:
        return "warm"
    # Check metadata for referral signals (future expansion)
    if metadata and metadata.get("referral"):
        return "warm"
    return "cold"


# ---------------------------------------------------------------------------
# Deduplication check
# ---------------------------------------------------------------------------


async def check_duplicate_lead(
    org_id: str, contact_email: str | None, source_system: str
) -> dict[str, Any] | None:
    """Check if a lead with the same email + source_system exists within 24h.

    Returns the existing lead record if duplicate, None otherwise.
    """
    if not contact_email:
        # Cannot deduplicate without email
        return None

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    try:
        response = (
            neon_service.client.table("leads_pipeline")
            .select("id, temperature")
            .eq("org_id", org_id)
            .eq("contact_email", contact_email)
            .eq("source_system", source_system)
            .gte("created_at", cutoff)
            .limit(1)
            .execute()
        )
        if response.data:
            return response.data[0]
        return None
    except Exception as exc:
        logger.error(
            "Deduplication check failed: email=%s source=%s error=%s",
            contact_email,
            source_system,
            exc,
        )
        # On error, allow the lead through rather than blocking ingestion
        return None


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post(
    "/leads/intake",
    response_model=LeadIntakeResponse,
    status_code=201,
    responses={
        409: {"description": "Duplicate lead (same email + source within 24h)"},
        400: {"description": "Invalid or missing required fields"},
    },
)
async def intake_lead(
    request: LeadIntakeRequest,
    org_id: str = Depends(get_org_id),
) -> LeadIntakeResponse:
    """Accept a lead from an external source.

    Validates required fields, checks for duplicates within 24h window,
    assigns temperature, and creates a pipeline entry with status 'new'.
    """
    # Deduplication check
    existing = await check_duplicate_lead(
        org_id=org_id,
        contact_email=request.contact.email,
        source_system=request.source_system,
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Duplicate lead: same email and source system within 24 hours",
                "existing_lead_id": existing["id"],
                "status": "duplicate",
                "temperature": existing.get("temperature", "cold"),
            },
        )

    # Assign temperature
    temperature = assign_temperature(request.source_system, request.metadata)

    # Build insert payload
    lead_data: dict[str, Any] = {
        "org_id": org_id,
        "contact_name": request.contact.name,
        "contact_email": request.contact.email,
        "contact_phone": request.contact.phone,
        "source_system": request.source_system,
        "source_channel": request.source_channel,
        "temperature": temperature,
        "status": "new",
        "metadata": request.metadata,
    }

    try:
        response = (
            neon_service.client.table("leads_pipeline")
            .insert(lead_data)
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create lead")

        created_lead = response.data[0]

        logger.info(
            "Lead created: id=%s source=%s channel=%s temperature=%s org=%s",
            created_lead["id"],
            request.source_system,
            request.source_channel,
            temperature,
            org_id,
        )

        return LeadIntakeResponse(
            lead_id=created_lead["id"],
            status="created",
            temperature=temperature,
        )

    except HTTPException:
        raise
    except Exception as exc:
        # Handle unique constraint violation (backup dedup via DB constraint)
        error_msg = str(exc).lower()
        if "unique" in error_msg or "duplicate" in error_msg or "23505" in error_msg:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Duplicate lead: unique constraint violated",
                    "status": "duplicate",
                },
            )
        logger.error("Lead intake failed: %s", exc)
        raise HTTPException(status_code=500, detail="Internal error during lead creation")
