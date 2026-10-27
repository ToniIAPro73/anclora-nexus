from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict
from backend.services.neon_service import neon_service
from backend.agents.graph import agent_executor
from backend.api.deps import get_org_id

router = APIRouter()

@router.post("/leads/intake")
async def manual_lead_intake(data: Dict[str, Any], org_id: str = Depends(get_org_id)):
    """
    Trigger manual lead intake processing via LangGraph.
    """
    try:
        # Prepare state for LangGraph
        initial_state = {
            "input_data": data,
            "skill_name": "lead_intake",
            "org_id": org_id,
            "status": "pending"
        }

        # Run Graph
        result = await agent_executor.ainvoke(initial_state)

        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("error"))

        return result.get("final_result")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/skills/run")
async def run_skill(payload: Dict[str, Any], org_id: str = Depends(get_org_id)):
    """
    Trigger any skill execution.
    Payload: { "skill": "skill_name", "data": { ... } }
    """
    skill_name = payload.get("skill")
    skill_data = payload.get("data", {})

    if not skill_name:
         raise HTTPException(status_code=400, detail="Missing 'skill' field in payload")

    try:
        initial_state = {
            "input_data": skill_data,
            "skill_name": skill_name,
            "org_id": org_id,
            "status": "pending"
        }

        result = await agent_executor.ainvoke(initial_state)

        if result.get("status") == "error":
             raise HTTPException(status_code=500, detail=result.get("error"))

        return result.get("final_result")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/weekly")
async def get_weekly_stats(org_id: str = Depends(get_org_id)):
    """
    Fetch weekly metrics for the QuickStats widget.
    """
    try:
        # Fetch recent leads
        leads = await neon_service.get_recent_leads(days=7, org_id=org_id)
        # Fetch recent recap
        recaps = neon_service.client.table("weekly_recaps")\
            .select("*")\
            .eq("org_id", org_id)\
            .order("created_at", descending=True)\
            .limit(1)\
            .execute()

        latest_recap = recaps.data[0] if recaps.data else {}

        # Calculate stats
        stats = {
            "leads_this_week": len(leads),
            "response_rate": "85%", # Placeholder until we have more data
            "active_mandates": 12, # Placeholder
            "latest_insights": latest_recap.get("insights", "No hay recaps recientes.")
        }

        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/leads/{lead_id}")
async def update_lead(lead_id: str, data: Dict[str, Any], org_id: str = Depends(get_org_id)):
    """
    Update lead with org scope and server-side origin editability enforcement.
    """
    try:
        result = await neon_service.update_lead_scoped(org_id, lead_id, data)
        if not result:
            raise HTTPException(status_code=404, detail="Lead not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
