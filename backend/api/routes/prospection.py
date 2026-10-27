"""
Prospection & Buyer Matching API Routes.
Feature: ANCLORA-PBM-001

Endpoints for properties, buyers, matches, and activity logging.
All filtered by org_id for isolation.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.deps import get_org_id, check_budget_hard_stop, get_current_user
from backend.api.middleware import verify_org_membership
from backend.services.buyer_memory_service import buyer_memory_service
from backend.services.buyer_outreach_service import buyer_outreach_service
from backend.services.neon_service import NeonService
from backend.models.prospection import (
    ActivityCreate,
    ActivityList,
    BuyerCreate,
    BuyerList,
    BuyerUpdate,
    FollowupTaskActionRequest,
    MarkReviewedActionRequest,
    MatchList,
    MatchUpdate,
    PropertyCreate,
    PropertyList,
    PropertyUpdate,
    RecomputeRequest,
    RecomputeResponse,
    WorkspaceActionResponse,
)
from backend.services.prospection_service import prospection_service

router = APIRouter()


_db_service = None


def get_db() -> NeonService:
    global _db_service
    if _db_service is None:
        _db_service = NeonService()
    return _db_service


@router.get("/workspace")
async def get_workspace(
    org_id: str = Depends(get_org_id),
    user=Depends(get_current_user),
    source_system: Optional[str] = Query(None, description="Filter by source_system"),
    property_status: Optional[str] = Query(None, alias="property_status"),
    buyer_status: Optional[str] = Query(None, alias="buyer_status"),
    match_status: Optional[str] = Query(None, alias="match_status"),
    min_property_score: Optional[float] = Query(None, ge=0, le=100),
    min_match_score: Optional[float] = Query(None, ge=0, le=100),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    """
    Unified prospection workspace payload with role scope.
    owner/manager -> full org visibility
    agent -> assigned-only visibility
    """
    try:
        parsed_org_id = UUID(org_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid org_id format: {org_id}",
        )

    try:
        member = await verify_org_membership(user.id, parsed_org_id)
        role = str(member.get("role") or "agent")
        return await prospection_service.get_workspace(
            org_id=org_id,
            role=role,
            user_id=str(user.id),
            source_system=source_system,
            property_status=property_status,
            buyer_status=buyer_status,
            match_status=match_status,
            min_property_score=min_property_score,
            min_match_score=min_match_score,
            limit=limit,
            offset=offset,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading workspace: {str(e)}",
        )


@router.post("/workspace/actions/followup-task", response_model=WorkspaceActionResponse)
async def create_workspace_followup_task(
    payload: FollowupTaskActionRequest,
    org_id: str = Depends(get_org_id),
    user=Depends(get_current_user),
) -> WorkspaceActionResponse:
    try:
        result = await prospection_service.create_workspace_followup_task(
            org_id=org_id,
            user_id=str(user.id),
            entity_type=payload.entity_type.value,
            entity_id=str(payload.entity_id),
            title=payload.title,
            description=payload.description,
            due_date=payload.due_date.isoformat() if payload.due_date else None,
            assigned_user_id=str(payload.assigned_user_id) if payload.assigned_user_id else None,
        )
        return WorkspaceActionResponse(
            action="followup_task",
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            task_id=result.get("task_id"),
            message="Follow-up task created",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating follow-up task: {str(e)}",
        )


@router.post("/workspace/actions/mark-reviewed", response_model=WorkspaceActionResponse)
async def mark_workspace_item_reviewed(
    payload: MarkReviewedActionRequest,
    org_id: str = Depends(get_org_id),
    user=Depends(get_current_user),
) -> WorkspaceActionResponse:
    try:
        await prospection_service.mark_workspace_item_reviewed(
            org_id=org_id,
            user_id=str(user.id),
            entity_type=payload.entity_type.value,
            entity_id=str(payload.entity_id),
            note=payload.note,
        )
        return WorkspaceActionResponse(
            action="mark_reviewed",
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            message="Entity marked as reviewed",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error marking reviewed: {str(e)}",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# PROPERTIES
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/properties", status_code=status.HTTP_201_CREATED)
async def create_property(
    data: PropertyCreate,
    org_id: str = Depends(get_org_id),
    _budget = Depends(check_budget_hard_stop),
) -> dict:
    """
    Create a new prospected property.

    Automatically computes high_ticket_score on creation.
    Source must be from the allowed list (compliance).
    """
    try:
        result = await prospection_service.create_property(org_id, data)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating property: {str(e)}",
        )


@router.get("/properties")
async def list_properties(
    org_id: str = Depends(get_org_id),
    zone: Optional[str] = Query(None, description="Filter by zone"),
    property_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
    min_score: Optional[float] = Query(None, ge=0, le=100, description="Minimum high_ticket_score"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    """List prospected properties ordered by high_ticket_score descending."""
    try:
        return await prospection_service.list_properties(
            org_id=org_id,
            zone=zone,
            status=property_status,
            min_score=min_score,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing properties: {str(e)}",
        )


@router.patch("/properties/{property_id}")
async def update_property(
    property_id: UUID,
    data: PropertyUpdate,
    org_id: str = Depends(get_org_id),
) -> dict:
    """Update a prospected property."""
    result = await prospection_service.update_property(
        org_id, str(property_id), data
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property {property_id} not found",
        )
    return result


@router.post("/properties/{property_id}/score")
async def rescore_property(
    property_id: UUID,
    org_id: str = Depends(get_org_id),
) -> dict:
    """Recalculate high_ticket_score for a property."""
    result = await prospection_service.rescore_property(
        org_id, str(property_id)
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property {property_id} not found",
        )
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# BUYERS
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/buyers", status_code=status.HTTP_201_CREATED)
async def create_buyer(
    data: BuyerCreate,
    org_id: str = Depends(get_org_id),
) -> dict:
    """Create a new buyer profile."""
    try:
        result = await prospection_service.create_buyer(org_id, data)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating buyer: {str(e)}",
        )


@router.get("/buyers", response_model=BuyerList)
async def list_buyers(
    org_id: str = Depends(get_org_id),
    buyer_status: Optional[str] = Query(None, alias="status"),
    source_type: Optional[str] = Query(None, description="Filter by buyer source type"),
    source_platform: Optional[str] = Query(None, description="Filter by buyer source platform"),
    min_budget: Optional[float] = Query(None, ge=0),
    max_budget: Optional[float] = Query(None, ge=0),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    """List buyer profiles ordered by motivation_score descending."""
    return await prospection_service.list_buyers(
        org_id=org_id,
        status=buyer_status,
        source_type=source_type,
        source_platform=source_platform,
        min_budget=min_budget,
        max_budget=max_budget,
        limit=limit,
        offset=offset,
    )


@router.patch("/buyers/{buyer_id}")
async def update_buyer(
    buyer_id: UUID,
    data: BuyerUpdate,
    org_id: str = Depends(get_org_id),
) -> dict:
    """Update a buyer profile."""
    result = await prospection_service.update_buyer(
        org_id, str(buyer_id), data
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Buyer {buyer_id} not found",
        )
    return result


@router.get("/buyers/{buyer_id}/memory")
async def get_buyer_memory(
    buyer_id: UUID,
    query: Optional[str] = Query(None),
    limit: int = Query(5, ge=1, le=20),
    org_id: str = Depends(get_org_id),
) -> dict:
    db = get_db()
    payload = await buyer_memory_service.search(
        db=db,
        org_id=org_id,
        buyer_id=str(buyer_id),
        query=query or "",
        limit=limit,
    )
    return payload.model_dump()


@router.post("/buyers/{buyer_id}/memory/rebuild")
async def rebuild_buyer_memory(
    buyer_id: UUID,
    org_id: str = Depends(get_org_id),
) -> dict:
    db = get_db()
    payload = await buyer_memory_service.rebuild_for_buyer(
        db=db,
        org_id=org_id,
        buyer_id=str(buyer_id),
    )
    return payload.model_dump()


@router.get("/buyers/{buyer_id}/workbench")
async def get_buyer_workbench(
    buyer_id: UUID,
    interaction_limit: int = Query(20, ge=1, le=100),
    org_id: str = Depends(get_org_id),
) -> dict:
    db = get_db()
    payload = await buyer_outreach_service.get_buyer_workbench(
        db=db,
        org_id=org_id,
        buyer_id=str(buyer_id),
        interaction_limit=interaction_limit,
    )
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Buyer not found")
    return payload


@router.post("/buyers/{buyer_id}/generate-outreach")
async def generate_buyer_outreach(
    buyer_id: UUID,
    org_id: str = Depends(get_org_id),
    _budget=Depends(check_budget_hard_stop),
) -> dict:
    db = get_db()
    try:
        return await buyer_outreach_service.generate_buyer_outreach(
            db=db,
            org_id=org_id,
            buyer_id=str(buyer_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/buyers/{buyer_id}/interactions")
async def list_buyer_interactions(
    buyer_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    org_id: str = Depends(get_org_id),
) -> list[dict]:
    db = get_db()
    return await buyer_outreach_service.get_interactions(
        db=db,
        org_id=org_id,
        buyer_id=str(buyer_id),
        limit=limit,
    )


@router.post("/buyers/{buyer_id}/interactions", status_code=status.HTTP_201_CREATED)
async def log_buyer_interaction(
    buyer_id: UUID,
    payload: dict,
    org_id: str = Depends(get_org_id),
) -> dict:
    db = get_db()
    tipo = str(payload.get("tipo") or "note")
    if tipo not in {"call", "email", "whatsapp", "note", "buyer_brief", "email_draft", "whatsapp_draft"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid interaction tipo")
    return await buyer_outreach_service.add_interaction(
        db=db,
        org_id=org_id,
        buyer_id=str(buyer_id),
        tipo=tipo,
        contenido=str(payload.get("contenido") or ""),
        estado=str(payload.get("estado") or "realizado"),
        resultado=payload.get("resultado"),
        metadata=payload.get("metadata") or {},
    )


@router.post("/buyers/{buyer_id}/send-supervised/{channel}")
async def send_buyer_supervised(
    buyer_id: UUID,
    channel: str,
    payload: Optional[dict] = None,
    org_id: str = Depends(get_org_id),
) -> dict:
    db = get_db()
    try:
        return await buyer_outreach_service.build_supervised_send_payload(
            db=db,
            org_id=org_id,
            buyer_id=str(buyer_id),
            channel=channel,
            transport=str((payload or {}).get("transport") or "auto"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/buyers/{buyer_id}/interactions/{interaction_id}/confirm-send")
async def confirm_buyer_supervised_send(
    buyer_id: UUID,
    interaction_id: UUID,
    org_id: str = Depends(get_org_id),
) -> dict:
    db = get_db()
    payload = await buyer_outreach_service.confirm_supervised_send(
        db=db,
        org_id=org_id,
        buyer_id=str(buyer_id),
        interaction_id=str(interaction_id),
    )
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interaction not found")
    return payload


# ═══════════════════════════════════════════════════════════════════════════════
# MATCHES
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/matches/recompute", response_model=RecomputeResponse)
async def recompute_matches(
    data: Optional[RecomputeRequest] = None,
    org_id: str = Depends(get_org_id),
    _budget = Depends(check_budget_hard_stop),
) -> RecomputeResponse:
    """
    Recompute match scores for all or filtered property-buyer pairs.

    Creates new matches for unmatched pairs and updates existing scores.
    """
    property_ids = [str(pid) for pid in data.property_ids] if data and data.property_ids else None
    buyer_ids = [str(bid) for bid in data.buyer_ids] if data and data.buyer_ids else None

    return await prospection_service.recompute_matches(
        org_id=org_id,
        property_ids=property_ids,
        buyer_ids=buyer_ids,
    )


@router.get("/matches", response_model=MatchList)
async def list_matches(
    org_id: str = Depends(get_org_id),
    match_status: Optional[str] = Query(None, alias="status"),
    min_score: Optional[float] = Query(None, ge=0, le=100),
    property_id: Optional[UUID] = Query(None),
    buyer_id: Optional[UUID] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    """List matches ordered by match_score descending."""
    return await prospection_service.list_matches(
        org_id=org_id,
        status=match_status,
        min_score=min_score,
        property_id=str(property_id) if property_id else None,
        buyer_id=str(buyer_id) if buyer_id else None,
        limit=limit,
        offset=offset,
    )


@router.get("/opportunities/ranking")
async def get_opportunity_ranking(
    org_id: str = Depends(get_org_id),
    limit: int = Query(25, ge=1, le=100),
    min_opportunity_score: Optional[float] = Query(None, ge=0, le=100),
    match_status: Optional[str] = Query(None, description="Filter by match status"),
) -> dict:
    """Explainable ranking of commercial opportunities based on matches."""
    try:
        return await prospection_service.get_opportunity_ranking(
            org_id=org_id,
            limit=limit,
            min_opportunity_score=min_opportunity_score,
            match_status=match_status,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading opportunity ranking: {str(e)}",
        )


@router.patch("/matches/{match_id}")
async def update_match(
    match_id: UUID,
    data: MatchUpdate,
    org_id: str = Depends(get_org_id),
) -> dict:
    """Update match status, commission estimate, or notes."""
    result = await prospection_service.update_match(
        org_id, str(match_id), data
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match {match_id} not found",
        )
    return result


@router.post("/matches/{match_id}/activity", status_code=status.HTTP_201_CREATED)
async def log_match_activity(
    match_id: UUID,
    data: ActivityCreate,
    org_id: str = Depends(get_org_id),
) -> dict:
    """Log a commercial activity for a match (call, viewing, offer, etc.)."""
    try:
        result = await prospection_service.log_activity(
            org_id=org_id,
            match_id=str(match_id),
            data=data,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/matches/{match_id}/activities", response_model=ActivityList)
async def list_match_activities(
    match_id: UUID,
    org_id: str = Depends(get_org_id),
) -> dict:
    """List all activities for a specific match."""
    return await prospection_service.list_activities(
        org_id=org_id,
        match_id=str(match_id),
    )
