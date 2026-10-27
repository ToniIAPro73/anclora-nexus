"""
Nexus Sellers API Routes

CRUD endpoints for the seller acquisition pipeline.
Sellers are detected prospects (FSBOs, stagnant listings, STR enforcement victims)
before they appear on the open market.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from backend.models.sellers import (
    NexusSellerCreate,
    NexusSellerUpdate,
    NexusSellerResponse,
    SellerStatsResponse,
    EstadoUpdate,
    EstadoContactoEnum,
    ZonaEnum,
    FuenteEnum,
    # Intake pipeline
    SellerIntakeRequest,
    SellerIntakeResponse,
    SellerPrioritizeRequest,
    SellerPrioritizeResponse,
    PendingApprovalResponse,
    ApproveAndSendRequest,
    ApproveAndSendResponse,
)
from backend.services import sellers_service
from backend.services.seller_memory_service import seller_memory_service
from backend.services.neon_service import NeonService
from backend.services.llm_service import llm_service
from ..deps import check_budget_hard_stop, get_current_user, get_org_id
from backend.skills.whale_dossier import run_whale_dossier


class InteractionCreate(BaseModel):
    tipo: str  # llamada | email | whatsapp | reunion | nota | email_draft
    contenido: str
    estado: str = "realizado"
    resultado: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SupervisedSendRequest(BaseModel):
    transport: Optional[str] = "auto"

router = APIRouter()

_db_service = None

def get_db() -> NeonService:
    global _db_service
    if _db_service is None:
        _db_service = NeonService()
    return _db_service


# ═══════════════════════════════════════════════════════════════
# LIST & STATS
# ═══════════════════════════════════════════════════════════════

@router.get("/", response_model=List[dict])
async def list_sellers(
    zona: Optional[str] = Query(None, description="Filter by zone"),
    estado: Optional[str] = Query(None, description="Filter by contact state"),
    fuente: Optional[str] = Query(None, description="Filter by source"),
    prioridad_min: Optional[int] = Query(None, ge=1, le=5, description="Minimum priority"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    org_id: str = Depends(get_org_id),
):
    """
    List Nexus Sellers with optional filters.

    Ordered by priority (descending) and detection date (most recent first).
    """
    try:
        db = get_db()
        sellers = await sellers_service.get_sellers(
            db=db,
            org_id=org_id,
            zona=zona,
            estado=estado,
            fuente=fuente,
            prioridad_min=prioridad_min,
            limit=limit,
            offset=offset,
        )
        return sellers
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing sellers: {str(e)}")


@router.get("/stats", response_model=dict)
async def seller_stats(org_id: str = Depends(get_org_id)):
    """
    Aggregated pipeline metrics for Nexus Sellers.

    Returns counts by estado, zona, fuente, plus whale count and conversion rate.
    """
    try:
        db = get_db()
        stats = await sellers_service.get_seller_stats(
            db=db,
            org_id=org_id,
        )
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error computing stats: {str(e)}")


# ═══════════════════════════════════════════════════════════════
# CREATE
# ═══════════════════════════════════════════════════════════════

@router.post("/", response_model=dict, status_code=201)
async def create_seller(
    data: NexusSellerCreate,
    _budget=Depends(check_budget_hard_stop),
    org_id: str = Depends(get_org_id),
):
    """
    Create a new Nexus Seller prospect.

    Used for manual entry or automated scraping pipelines.
    The prioridad field uses the same 1-5 scale as leads:
    - 5 = Whale (respond <15 min)
    - 4 = High value (respond <2h)
    - 3 = Potential (respond <24h)
    - 1-2 = Cold / follow-up
    """
    try:
        db = get_db()
        seller = await sellers_service.create_seller(
            db=db,
            org_id=org_id,
            data=data,
        )
        return seller
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating seller: {str(e)}")


# ═══════════════════════════════════════════════════════════════
# ENUMS (for frontend dropdowns) — must be before /{seller_id}
# ═══════════════════════════════════════════════════════════════

@router.get("/meta/enums")
async def get_enums():
    """Return valid enum values for all Nexus Seller fields."""
    return {
        "zonas": [z.value for z in ZonaEnum],
        "fuentes": [f.value for f in FuenteEnum],
        "estados_contacto": [e.value for e in EstadoContactoEnum],
        "prioridades": {
            "5": "Whale — respond <15 min",
            "4": "High value — respond <2h",
            "3": "Potential — respond <24h",
            "2": "Follow-up — respond <48h",
            "1": "Cold — long-term nurturing",
        },
    }


# ═══════════════════════════════════════════════════════════════
# GET / UPDATE / ESTADO
# ═══════════════════════════════════════════════════════════════

@router.get("/{seller_id}", response_model=dict)
async def get_seller(seller_id: str, org_id: str = Depends(get_org_id)):
    """Get a single Nexus Seller by ID."""
    try:
        db = get_db()
        seller = await sellers_service.get_seller(
            db=db,
            org_id=org_id,
            seller_id=seller_id,
        )
        if not seller:
            raise HTTPException(status_code=404, detail="Seller not found")
        return seller
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving seller: {str(e)}")


@router.get("/{seller_id}/workbench", response_model=dict)
async def get_seller_workbench(
    seller_id: str,
    interaction_limit: int = Query(20, ge=1, le=100),
    org_id: str = Depends(get_org_id),
):
    """
    Return the seller workbench payload used by Gravity Claw:
    seller record, recent interactions and latest generated artifacts.
    """
    try:
        db = get_db()
        workbench = await sellers_service.get_seller_workbench(
            db=db,
            org_id=org_id,
            seller_id=seller_id,
            interaction_limit=interaction_limit,
        )
        if not workbench:
            raise HTTPException(status_code=404, detail="Seller not found")
        return workbench
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error building seller workbench: {str(e)}")


@router.get("/{seller_id}/dossier-export", response_model=dict)
async def get_seller_dossier_export(seller_id: str, org_id: str = Depends(get_org_id)):
    """
    Return a normalized export/share payload for the seller dossier.
    """
    try:
        db = get_db()
        payload = await sellers_service.build_seller_dossier_export(
            db=db,
            org_id=org_id,
            seller_id=seller_id,
        )
        if not payload:
            raise HTTPException(status_code=404, detail="Seller not found")
        return payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error building dossier export: {str(e)}")


@router.patch("/{seller_id}/estado", response_model=dict)
async def update_seller_estado(
    seller_id: str,
    data: EstadoUpdate,
    org_id: str = Depends(get_org_id),
):
    """
    Update the contact state of a Nexus Seller.

    Valid transitions (pipeline progression):
    sin_contacto → primer_contacto → en_seguimiento →
    reunion_agendada → propuesta_enviada → mandato_exclusivo

    Or at any point: → descartado

    Automatically sets fecha_primer_contacto / fecha_ultimo_contacto /
    fecha_mandato based on the new state.
    """
    try:
        db = get_db()
        seller = await sellers_service.update_seller_estado(
            db=db,
            org_id=org_id,
            seller_id=seller_id,
            estado=data.estado_contacto.value,
            notas=data.notas,
        )
        if not seller:
            raise HTTPException(status_code=404, detail="Seller not found")
        return seller
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating seller estado: {str(e)}")


@router.patch("/{seller_id}", response_model=dict)
async def update_seller_record(
    seller_id: str,
    data: NexusSellerUpdate,
    org_id: str = Depends(get_org_id),
):
    """Update seller contact channels and general editable fields."""
    try:
        db = get_db()
        seller = await sellers_service.update_seller(
            db=db,
            org_id=org_id,
            seller_id=seller_id,
            data=data,
        )
        if not seller:
            raise HTTPException(status_code=404, detail="Seller not found")
        return seller
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating seller: {str(e)}")


# ═══════════════════════════════════════════════════════════════
# GRAVITY CLAW — WHALE DOSSIER (Phase 4)
# ═══════════════════════════════════════════════════════════════

@router.post("/{seller_id}/generate-dossier", response_model=dict)
async def generate_whale_dossier(
    seller_id: str,
    _budget=Depends(check_budget_hard_stop),
    org_id: str = Depends(get_org_id),
):
    """
    Generate a hyper-personalized captation dossier for a Whale seller.

    Uses zone territorial intelligence from NotebookLM cache + the current
    runtime profile to produce:
    - Argumentario: captation pitch with local market data
    - Email draft
    - WhatsApp draft
    - Call brief
    - Context brief to resume the conversation later

    All artifacts are saved to seller_interactions. The argumentario is also
    stored in nexus_sellers.argumentario.

    Recommended for sellers with prioridad >= 4 (High value / Whale).
    """
    try:
        db = get_db()
        result = await run_whale_dossier(
            data={"seller_id": seller_id, "org_id": org_id},
            llm=llm_service,
            db=db,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("reason", "Error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating dossier: {str(e)}")


# ═══════════════════════════════════════════════════════════════
# INTERACTION MEMORY (Gravity Claw Phase 4)
# ═══════════════════════════════════════════════════════════════

@router.get("/{seller_id}/interactions", response_model=list)
async def list_seller_interactions(
    seller_id: str,
    limit: int = Query(20, ge=1, le=100),
    org_id: str = Depends(get_org_id),
):
    """
    List all interactions for a seller (most recent first).

    Returns: calls, emails, WhatsApp messages, meetings, notes, AI drafts.
    """
    try:
        db = get_db()
        interactions = await sellers_service.get_interactions(
            db=db,
            org_id=org_id,
            seller_id=seller_id,
            limit=limit,
        )
        return interactions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing interactions: {str(e)}")


@router.get("/{seller_id}/memory", response_model=dict)
async def get_seller_memory(
    seller_id: str,
    query: str = Query("seguimiento captacion objeciones siguiente paso", min_length=3),
    limit: int = Query(5, ge=1, le=20),
    org_id: str = Depends(get_org_id),
):
    """
    Retrieve explainable semantic memory matches for a seller.
    """
    try:
        db = get_db()
        payload = await seller_memory_service.search(
            db=db,
            org_id=org_id,
            seller_id=seller_id,
            query=query,
            limit=limit,
        )
        return payload.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving seller memory: {str(e)}")


@router.post("/{seller_id}/memory/rebuild", response_model=dict)
async def rebuild_seller_memory(seller_id: str, org_id: str = Depends(get_org_id)):
    """
    Rebuild semantic memory records for a seller from historical interactions.
    """
    try:
        db = get_db()
        payload = await seller_memory_service.rebuild_for_seller(
            db=db,
            org_id=org_id,
            seller_id=seller_id,
        )
        return payload.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rebuilding seller memory: {str(e)}")


@router.post("/{seller_id}/interactions", response_model=dict, status_code=201)
async def log_seller_interaction(
    seller_id: str,
    data: InteractionCreate,
    org_id: str = Depends(get_org_id),
):
    """
    Log a manual interaction with a seller.

    Use this to record calls, WhatsApp messages, meetings, or free-form notes.
    AI-generated drafts are created automatically via /generate-dossier.
    """
    valid_tipos = {"llamada", "email", "whatsapp", "reunion", "nota", "email_draft"}
    if data.tipo not in valid_tipos:
        raise HTTPException(status_code=422, detail=f"tipo must be one of {valid_tipos}")
    try:
        db = get_db()
        interaction = await sellers_service.add_interaction(
            db=db,
            org_id=org_id,
            seller_id=seller_id,
            tipo=data.tipo,
            contenido=data.contenido,
            estado=data.estado,
            resultado=data.resultado,
            metadata=data.metadata,
        )
        return interaction
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error logging interaction: {str(e)}")


@router.post("/{seller_id}/send-supervised/{channel}", response_model=dict)
async def build_supervised_send(
    seller_id: str,
    channel: str,
    request: Optional[SupervisedSendRequest] = None,
    org_id: str = Depends(get_org_id),
):
    """
    Prepare a real supervised send via mailto or wa.me and log the launch intent.
    """
    try:
        db = get_db()
        payload = await sellers_service.build_supervised_send_payload(
            db=db,
            org_id=org_id,
            seller_id=seller_id,
            channel=channel,
            transport=(request.transport if request else "auto") or "auto",
        )
        return payload
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error preparing supervised send: {str(e)}")


@router.post("/{seller_id}/interactions/{interaction_id}/confirm-send", response_model=dict)
async def confirm_supervised_send(
    seller_id: str,
    interaction_id: str,
    org_id: str = Depends(get_org_id),
):
    """
    Confirm that a human operator completed the external send action.
    """
    try:
        db = get_db()
        payload = await sellers_service.confirm_supervised_send(
            db=db,
            org_id=org_id,
            seller_id=seller_id,
            interaction_id=interaction_id,
        )
        if not payload:
            raise HTTPException(status_code=404, detail="Interaction not found")
        return payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error confirming supervised send: {str(e)}")


# ═══════════════════════════════════════════════════════════════
# INTAKE PIPELINE (ANCLORA-SIP-001)
# ═══════════════════════════════════════════════════════════════


@router.post("/intake", response_model=SellerIntakeResponse, status_code=202)
async def seller_intake(
    payload: SellerIntakeRequest,
    _budget=Depends(check_budget_hard_stop),
    org_id: str = Depends(get_org_id),
):
    """
    Raw seller lead intake — ANCLORA-SIP-001.

    Accepts unstructured data from any source (StateFox webhook, FSBO scraper, web form).
    Triggers the SellerProspectionGraph: extract → prioritize → limit check → outreach copy → HITL queue.
    Returns preliminary priority and draft_id for HITL approval.
    """
    from datetime import datetime, timezone
    try:
        db = get_db()
        result = await sellers_service.intake_seller_raw(
            db=db,
            org_id=org_id,
            raw_data=payload.raw_data,
        )
        if result.get("limit_violation"):
            raise HTTPException(
                status_code=429,
                detail=f"Constitutional limit reached: {result['limit_violation']}",
            )
        return SellerIntakeResponse(
            seller_id=result.get("seller_id"),
            draft_id=result.get("draft_id"),
            status=result.get("status") or "success",
            priority_score=result.get("priority_score"),
            priority_tier=result.get("priority_tier"),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing seller intake: {str(e)}")


@router.post("/prioritize", response_model=SellerPrioritizeResponse)
async def prioritize_sellers(
    payload: SellerPrioritizeRequest,
    org_id: str = Depends(get_org_id),
):
    """
    Batch prioritization — ANCLORA-SIP-001.

    Applies deterministic formula to sellers without a priority_score:
      priority = budget×0.35 + urgency×0.25 + property_fit×0.25 + source_quality×0.15
    Scores are reproducible (same input → same output). Tier: 0-0.19=1 … 0.80-1.0=5.
    """
    from datetime import datetime, timezone
    try:
        db = get_db()
        scored = await sellers_service.batch_prioritize_sellers(
            db=db,
            org_id=org_id,
            batch_size=payload.batch_size,
        )
        from backend.models.sellers import SellerPrioritizeItem
        return SellerPrioritizeResponse(
            scored=[SellerPrioritizeItem(**s) for s in scored],
            total_processed=len(scored),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running batch prioritization: {str(e)}")


@router.get("/pending-approval", response_model=PendingApprovalResponse)
async def list_pending_approval(
    priority_tier: Optional[int] = Query(None, ge=1, le=5, description="Filter by priority tier"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    org_id: str = Depends(get_org_id),
):
    """
    HITL approval queue — ANCLORA-SIP-001.

    Returns outreach drafts pending human approval, ordered by priority DESC, created_at DESC.
    Each item includes email_draft and whatsapp_draft for review before send.
    """
    try:
        db = get_db()
        result = await sellers_service.list_pending_approval(
            db=db,
            org_id=org_id,
            priority_tier=priority_tier,
            limit=limit,
            offset=offset,
        )
        from backend.models.sellers import PendingApprovalItem
        return PendingApprovalResponse(
            items=[PendingApprovalItem(**item) for item in result["items"]],
            total=result["total"],
            limit=result["limit"],
            offset=result["offset"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing pending approvals: {str(e)}")


@router.post("/approve-and-send", response_model=ApproveAndSendResponse, status_code=202)
async def approve_and_send(
    payload: ApproveAndSendRequest,
    org_id: str = Depends(get_org_id),
    user=Depends(get_current_user),
):
    """
    Approve outreach draft and queue for send — ANCLORA-SIP-001 HITL workflow.

    Allows optional override of email/whatsapp bodies before approval.
    Returns 202 Accepted + job_id for async send processing.
    Logs approved_by + timestamp to audit_log.
    """
    try:
        db = get_db()
        result = await sellers_service.approve_and_send_outreach(
            db=db,
            org_id=org_id,
            draft_id=payload.draft_id,
            approved_email_body=payload.approved_email_body,
            approved_whatsapp_body=payload.approved_whatsapp_body,
            agent_comments=payload.agent_comments,
            user_id=str(user.id) if user else None,
        )
        return ApproveAndSendResponse(
            status=result["status"],
            job_id=result["job_id"],
            draft_id=result["draft_id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error approving outreach draft: {str(e)}")


@router.post("/{seller_id}/generate-outreach", response_model=dict)
async def generate_seller_outreach(
    seller_id: str,
    _budget=Depends(check_budget_hard_stop),
    org_id: str = Depends(get_org_id),
):
    """
    Generate personalized outreach copy for a seller — delegates to generate-dossier.
    Alias endpoint for pipeline compatibility.
    """
    try:
        db = get_db()
        result = await run_whale_dossier(
            data={"seller_id": seller_id, "org_id": org_id},
            llm=llm_service,
            db=db,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("reason", "Error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating seller outreach: {str(e)}")
