from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Any, Dict, Literal

from backend.api.deps import get_org_id
from backend.services.origin_editability_policy import build_policy
from backend.services.prospection_service import prospection_service
from backend.services.neon_service import neon_service

router = APIRouter()

Entity = Literal["lead", "property"]


@router.get("/policy")
async def get_policy(
    entity: Entity = Query(..., description="Entity type: lead or property"),
    source_system: str = Query("manual", description="Origin system"),
) -> Dict[str, Any]:
    return build_policy(entity, source_system)


@router.get("/policy/leads/{lead_id}")
async def get_lead_policy(lead_id: str, org_id: str = Depends(get_org_id)) -> Dict[str, Any]:
    lead = await neon_service.get_lead_scoped(org_id, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return build_policy("lead", str(lead.get("source_system") or "manual"))


@router.get("/policy/properties/{property_id}")
async def get_property_policy(property_id: str, org_id: str = Depends(get_org_id)) -> Dict[str, Any]:
    prop = await prospection_service.get_property(org_id, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return build_policy("property", str(prop.get("source_system") or "manual"))
