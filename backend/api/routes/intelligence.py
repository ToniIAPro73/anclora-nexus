"""
Anclora Intelligence API Routes
Endpoints for Intelligence orchestrator and NotebookLM territorial insights cache.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

# Import Intelligence
from backend.intelligence import create_orchestrator
from backend.services.notebooklm_service import (
    NOTEBOOK_ID,
    NOTEBOOK_NAME,
    get_latest_insights,
    get_territorial_summary,
    get_vulnerabilidades,
    save_insight,
)
from backend.services.intelligence_packs_service import (
    create_intelligence_pack,
    get_active_intelligence_pack,
    get_intelligence_pack,
    list_intelligence_packs,
    update_intelligence_pack,
)
from backend.services.ai_runtime import get_runtime_summary
from backend.services.neon_service import NeonService
from backend.services.territorial_sync_service import (
    get_territorial_pipeline_status,
    get_territorial_sync_status,
)
from backend.services.statefox_discovery_service import get_statefox_discovery
from backend.services.statefox_bridge_service import parse_statefox_raw, import_statefox_listings
from backend.services.statefox_live_capture_service import get_statefox_live_capture, import_latest_statefox_capture
from ..deps import check_budget_hard_stop
from ..deps import get_current_user, get_org_id

# Create router
router = APIRouter()

# ═══════════════════════════════════════════════════════════════
# SCHEMAS (Pydantic models for request/response)
# ═══════════════════════════════════════════════════════════════

class QueryRequest(BaseModel):
    """Request model for Intelligence query."""
    message: str
    user_id: Optional[str] = "anonymous"
    
    class Config:
        example = {
            "message": "¿Es buen momento para solicitar excedencia en CGI?",
            "user_id": "toni"
        }


class QueryResponse(BaseModel):
    """Response model for Intelligence query."""
    correlation_id: str
    status: str
    query_plan: Optional[Dict[str, Any]]
    governor_decision: Optional[Dict[str, Any]]
    synthesizer_output: Optional[Dict[str, Any]]
    execution_times: Optional[Dict[str, float]]
    error: Optional[str] = None
    timestamp: str


class StatefoxParseRequest(BaseModel):
    raw_text: str
    zone: Optional[str] = None
    city: Optional[str] = "Mallorca"


class StatefoxLiveCaptureImportRequest(BaseModel):
    zone: Optional[str] = None
    city: Optional[str] = "Mallorca"


class IntelligencePackCreateRequest(BaseModel):
    pack_label: str
    notebook_id: str
    notebook_name: str
    pack_key: Optional[str] = None
    market_scope: str = "seller"
    zone_scope: List[str] = []
    language_code: str = "es"
    source_mode: str = "notebooklm_manual"
    status: str = "active"
    is_default: bool = False
    metadata: Dict[str, Any] = {}


class IntelligencePackUpdateRequest(BaseModel):
    pack_label: Optional[str] = None
    notebook_id: Optional[str] = None
    notebook_name: Optional[str] = None
    market_scope: Optional[str] = None
    zone_scope: Optional[List[str]] = None
    language_code: Optional[str] = None
    source_mode: Optional[str] = None
    status: Optional[str] = None
    is_default: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None
    last_synced_at: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# GLOBAL ORCHESTRATOR INSTANCE
# ═══════════════════════════════════════════════════════════════

_orchestrator = None

def get_orchestrator():
    """Get or create orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = create_orchestrator()
    return _orchestrator


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.post("/query", response_model=QueryResponse)
async def process_query(
    request: QueryRequest,
    _budget = Depends(check_budget_hard_stop)
):
    """
    Process a query through Intelligence pipeline.
    
    Takes a user message, routes it through Router → Governor → Synthesizer,
    and returns a structured decision with reasoning.
    
    Args:
        request: QueryRequest with message and optional user_id
    
    Returns:
        QueryResponse with full Intelligence output
    """
    
    try:
        # Get orchestrator
        orchestrator = get_orchestrator()
        
        # Process query
        result, error = orchestrator.process_query(
            message=request.message,
            user_id=request.user_id
        )
        
        if error:
            raise HTTPException(status_code=400, detail=f"Intelligence error: {error}")
        
        if not result:
            raise HTTPException(status_code=500, detail="Intelligence returned empty result")
        
        # Map result to response
        response = QueryResponse(
            correlation_id=result.get("correlation_id"),
            status=result.get("processing_status", "unknown"),
            query_plan=result.get("query_plan"),
            governor_decision=result.get("governor_decision"),
            synthesizer_output=result.get("synthesizer_output"),
            execution_times=result.get("execution_times"),
            error=result.get("error"),
            timestamp=result.get("timestamp", datetime.now(timezone.utc).isoformat()),
        )
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get("/status")
async def intelligence_status():
    """
    Get Intelligence system status.
    
    Returns:
        Status information about the Intelligence system
    """
    
    return {
        "service": "Anclora Intelligence",
        "version": "1.0.0",
        "status": "ready",
        "components": {
            "router": "ready",
            "governor": "ready",
            "synthesizer": "ready",
            "orchestrator": "ready",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/info")
async def intelligence_info():
    """
    Get Intelligence system information.
    
    Returns:
        Information about Intelligence capabilities and limits
    """
    
    return {
        "name": "Anclora Intelligence v1.0",
        "description": "Strategic Intelligence orchestrator for Anclora Real Estate",
        "phase": "1",
        "capabilities": {
            "query_processing": True,
            "strategic_mode": "2.0-notebooklm-integration",
            "domains_enabled": ["market", "brand", "tax", "transition", "system", "territorial"],
            "domains_disabled": ["growth", "lab"],
            "max_domains_per_query": 3,
            "retrieval_enabled": True,
            "notebooklm_notebook": NOTEBOOK_NAME,
            "notebooklm_notebook_id": NOTEBOOK_ID,
            "ai_runtime_profile": get_runtime_summary().get("profile"),
        },
        "limits": {
            "max_message_length": 5000,
            "max_response_time_ms": 120000,
            "rate_limit": "unlimited (dev)",
        },
        "endpoints": {
            "query": "POST /api/intelligence/query",
            "status": "GET /api/intelligence/status",
            "info": "GET /api/intelligence/info",
            "runtime_profile": "GET /api/intelligence/runtime-profile",
        },
    }


@router.get("/runtime-profile")
async def intelligence_runtime_profile():
    """
    Return the active AI runtime profile and task-to-model routing.

    This contract is part of ANCLORA-AIRP-001 and exists so QA/operations
    can verify that Groq + Cloudflare routing is correctly configured
    without relying on hidden environment variables.
    """
    return {
        "runtime": get_runtime_summary(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════

@router.get("/health")
async def intelligence_health():
    """
    Health check for Intelligence service.

    Returns:
        Health status
    """

    return {
        "service": "Anclora Intelligence",
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════════════════════════════
# NOTEBOOKLM TERRITORIAL INSIGHTS ENDPOINTS
# ═══════════════════════════════════════════════════════════════

_db_service = None

def get_db() -> NeonService:
    global _db_service
    if _db_service is None:
        _db_service = NeonService()
    return _db_service


async def _resolve_pack(
    db: NeonService,
    org_id: str,
    pack_id: Optional[str],
) -> dict[str, Any]:
    pack = await (get_intelligence_pack(db=db, org_id=org_id, pack_id=pack_id) if pack_id else get_active_intelligence_pack(db=db, org_id=org_id))
    if not pack:
        raise HTTPException(status_code=404, detail="Intelligence pack not found")
    return pack


@router.get("/territorial-insights")
async def get_territorial_insights(
    insight_type: Optional[str] = Query(None, description="Filter by type: territorial, cma, competitive, whale_audit, buyer_profile, market_signal"),
    zona: Optional[str] = Query(None, description="Filter by zone: andratx, calvia, son_ferrer, santa_ponca, paguera, portals_nous, bendinat, punta_negra, costa_den_blanes, general"),
    pack_id: Optional[str] = Query(None, description="Optional intelligence pack id"),
    limit: int = Query(10, ge=1, le=50),
    org_id: str = Depends(get_org_id),
):
    """
    Retrieve territorial intelligence insights cached from NotebookLM.

    These insights are generated by Claude Code querying the configured
    NotebookLM territorial notebook via MCP, then stored in Neon for
    the frontend dashboard to consume.

    Returns:
        List of intelligence insights, ordered by most recent first.
    """
    try:
        db = get_db()
        active_pack = await _resolve_pack(db=db, org_id=org_id, pack_id=pack_id)
        insights = await get_latest_insights(
            db=db,
            org_id=org_id,
            insight_type=insight_type,
            zona=zona,
            notebook_id=active_pack.get("notebook_id"),
            limit=limit,
        )
        return {
            "insights": insights,
            "count": len(insights),
            "notebook": active_pack.get("notebook_name") or NOTEBOOK_NAME,
            "pack": active_pack,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving insights: {str(e)}")


@router.get("/territorial-summary")
async def get_territorial_summary_endpoint(
    pack_id: Optional[str] = Query(None, description="Optional intelligence pack id"),
    org_id: str = Depends(get_org_id),
):
    """
    Retrieve the latest territorial insight per zone for the Radar Territorial
    dashboard widget. Returns a dict with zone names as keys.
    """
    try:
        db = get_db()
        active_pack = await _resolve_pack(db=db, org_id=org_id, pack_id=pack_id)
        summary = await get_territorial_summary(db=db, org_id=org_id, notebook_id=active_pack.get("notebook_id"))
        return {
            "summary": summary,
            "zones_with_data": list(summary.keys()),
            "pack": active_pack,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving summary: {str(e)}")


@router.get("/vulnerabilidades")
async def get_vulnerabilidades_endpoint(
    pack_id: Optional[str] = Query(None, description="Optional intelligence pack id"),
    org_id: str = Depends(get_org_id),
):
    """
    Retrieve the most recent territorial vulnerabilities/opportunities insight.
    Corresponds to the content of public/docs/vulnerabilidades.md but served via API.
    """
    try:
        db = get_db()
        active_pack = await _resolve_pack(db=db, org_id=org_id, pack_id=pack_id)
        vuln = await get_vulnerabilidades(db=db, org_id=org_id, notebook_id=active_pack.get("notebook_id"))
        if not vuln:
            return {
                "message": "No territorial vulnerability analysis available yet. "
                           "Run NotebookLM sync to generate insights.",
                "pack": active_pack,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        return {
            "insight": vuln,
            "pack": active_pack,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving vulnerabilities: {str(e)}")


@router.get("/territorial-sync-status")
async def get_territorial_sync_status_endpoint():
    """
    Return the control-plane status of the territorial NotebookLM sync pack.

    This exposes validation, freshness, coverage and source references so the
    frontend and operations can verify that the sync pack remains the primary
    territorial source without manually inspecting repo files.
    """
    try:
        status = get_territorial_sync_status()
        pipeline_status = get_territorial_pipeline_status()
        return {
            "sync_status": status,
            "pipeline_status": pipeline_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving territorial sync status: {str(e)}")


@router.get("/packs")
async def get_intelligence_packs_endpoint(org_id: str = Depends(get_org_id)):
    try:
        db = get_db()
        items = await list_intelligence_packs(db=db, org_id=org_id)
        active_pack = await get_active_intelligence_pack(db=db, org_id=org_id)
        return {
            "items": items,
            "active_pack": active_pack,
            "count": len(items),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving intelligence packs: {str(e)}")


@router.post("/packs")
async def create_intelligence_pack_endpoint(
    payload: IntelligencePackCreateRequest,
    org_id: str = Depends(get_org_id),
):
    try:
        db = get_db()
        pack = await create_intelligence_pack(db=db, org_id=org_id, payload=payload.model_dump())
        return {
            "item": pack,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating intelligence pack: {str(e)}")


@router.patch("/packs/{pack_id}")
async def update_intelligence_pack_endpoint(
    pack_id: str,
    payload: IntelligencePackUpdateRequest,
    org_id: str = Depends(get_org_id),
):
    try:
        db = get_db()
        pack = await update_intelligence_pack(
            db=db,
            org_id=org_id,
            pack_id=pack_id,
            payload=payload.model_dump(exclude_unset=True),
        )
        if not pack:
            raise HTTPException(status_code=404, detail="Intelligence pack not found")
        return {
            "item": pack,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating intelligence pack: {str(e)}")


@router.get("/statefox-discovery")
async def get_statefox_discovery_endpoint():
    """
    Return discovery evidence and import strategy for the StateFox Telegram
    surface observed by operations.
    """
    try:
        return {
            "discovery": get_statefox_discovery(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving StateFox discovery: {str(e)}")


@router.post("/statefox-bridge/parse")
async def parse_statefox_bridge(payload: StatefoxParseRequest):
    try:
        parsed = parse_statefox_raw(payload.raw_text)
        return {
            "parsed": parsed,
            "zone": payload.zone,
            "city": payload.city,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing StateFox payload: {str(e)}")


@router.post("/statefox-bridge/import")
async def import_statefox_bridge(
    payload: StatefoxParseRequest,
    org_id: str = Depends(get_org_id),
    _budget=Depends(check_budget_hard_stop),
):
    try:
        result = await import_statefox_listings(
            org_id=org_id,
            raw_text=payload.raw_text,
            zone=payload.zone,
            city=payload.city,
        )
        return {
            "result": result,
            "org_id": org_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error importing StateFox payload: {str(e)}")


@router.get("/statefox-bridge/live-capture")
async def get_statefox_live_capture_endpoint():
    try:
        return {
            "live_capture": get_statefox_live_capture(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading StateFox live capture: {str(e)}")


@router.post("/statefox-bridge/live-capture/import")
async def import_statefox_live_capture_endpoint(
    payload: StatefoxLiveCaptureImportRequest,
    org_id: str = Depends(get_org_id),
    _budget=Depends(check_budget_hard_stop),
):
    try:
        result = await import_latest_statefox_capture(
            org_id=org_id,
            zone=payload.zone,
            city=payload.city,
        )
        return {
            "result": result,
            "org_id": org_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error importing latest StateFox live capture: {str(e)}")
