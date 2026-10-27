from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_org_id
from backend.services.lead_outreach_service import lead_outreach_service
from backend.services.neon_service import neon_service

router = APIRouter()


@router.post("/leads/{lead_id}/generate-outreach")
async def generate_lead_outreach(lead_id: str, org_id: str = Depends(get_org_id)):
    try:
        return await lead_outreach_service.generate_lead_outreach(
            db=neon_service,
            org_id=org_id,
            lead_id=lead_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leads/{lead_id}/interactions")
async def list_lead_interactions(lead_id: str, org_id: str = Depends(get_org_id)):
    try:
        return await lead_outreach_service.get_interactions(
            db=neon_service,
            org_id=org_id,
            lead_id=lead_id,
            limit=50,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/leads/{lead_id}/send-supervised/email")
async def send_lead_supervised_email(
    lead_id: str,
    payload: Dict[str, Any] | None = None,
    org_id: str = Depends(get_org_id),
):
    try:
        return await lead_outreach_service.build_supervised_send_payload(
            db=neon_service,
            org_id=org_id,
            lead_id=lead_id,
            transport=str((payload or {}).get("transport") or "auto"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/leads/{lead_id}/interactions/{interaction_id}/confirm-send")
async def confirm_lead_supervised_send(lead_id: str, interaction_id: str, org_id: str = Depends(get_org_id)):
    try:
        payload = await lead_outreach_service.confirm_supervised_send(
            db=neon_service,
            org_id=org_id,
            lead_id=lead_id,
            interaction_id=interaction_id,
        )
        if not payload:
            raise HTTPException(status_code=404, detail="Interaction not found")
        return payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
