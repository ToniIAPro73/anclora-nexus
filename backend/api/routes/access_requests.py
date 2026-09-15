from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.deps import get_current_user, get_org_id, require_access_request_reviewer
from backend.models.access_requests import (
    AccessRequestAuditEventResponse,
    AccessRequestAnalyticsSummary,
    AccessRequestLifecycleResponse,
    AccessRequestProduct,
    AccessRequestRejectDecision,
    AccessRequestResponse,
    AccessRequestReviewDecision,
    AccessRequestSlaScanResponse,
    AccessRequestSource,
    AccessRequestStatus,
)
from backend.services.access_request_service import (
    AccessRequestInvalidTransitionError,
    AccessRequestNotFoundError,
    access_request_service,
)

router = APIRouter()


@router.get("", response_model=list[AccessRequestResponse])
async def list_access_requests(
    org_id: str = Depends(get_org_id),
    _user=Depends(get_current_user),
    status_filter: Optional[AccessRequestStatus] = Query(None, alias="status"),
    product: Optional[AccessRequestProduct] = Query(None),
    source: Optional[AccessRequestSource] = Query(None),
    request_type: Optional[str] = Query(None),
    intake_domain: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    created_from: Optional[str] = Query(None),
    created_to: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
):
    try:
        return await access_request_service.list_requests(
            org_id=org_id,
            status=status_filter,
            product=product,
            source=source,
            request_type=request_type,
            intake_domain=intake_domain,
            email=email,
            created_from=created_from,
            created_to=created_to,
            limit=limit,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/analytics/summary", response_model=AccessRequestAnalyticsSummary)
async def get_access_request_analytics_summary(
    org_id: str = Depends(get_org_id),
    _current_user=Depends(require_access_request_reviewer),
    limit: int = Query(500, ge=1, le=1000),
):
    try:
        return await access_request_service.get_analytics_summary(
            org_id=org_id,
            limit=limit,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/sla/scan", response_model=AccessRequestSlaScanResponse)
async def run_access_request_sla_scan(
    org_id: str = Depends(get_org_id),
    current_user=Depends(require_access_request_reviewer),
    limit: int = Query(500, ge=1, le=1000),
    dedupe_window_hours: int = Query(24, ge=1, le=168),
):
    try:
        return await access_request_service.run_sla_scan(
            org_id=org_id,
            reviewer_id=current_user.id,
            dedupe_window_hours=dedupe_window_hours,
            limit=limit,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{request_id}/audit", response_model=list[AccessRequestAuditEventResponse])
async def list_access_request_audit(
    request_id: str,
    org_id: str = Depends(get_org_id),
    _current_user=Depends(require_access_request_reviewer),
):
    try:
        return await access_request_service.list_audit_events(
            org_id=org_id,
            request_id=request_id,
        )
    except AccessRequestNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{request_id}/lifecycle", response_model=AccessRequestLifecycleResponse)
async def get_access_request_lifecycle(
    request_id: str,
    org_id: str = Depends(get_org_id),
    _current_user=Depends(require_access_request_reviewer),
):
    try:
        return await access_request_service.get_lifecycle(
            org_id=org_id,
            request_id=request_id,
        )
    except AccessRequestNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{request_id}/decision-email/retry", response_model=AccessRequestResponse)
async def retry_access_request_decision_email(
    request_id: str,
    org_id: str = Depends(get_org_id),
    current_user=Depends(require_access_request_reviewer),
):
    try:
        return await access_request_service.retry_decision_email(
            org_id=org_id,
            request_id=request_id,
            reviewer_id=current_user.id,
        )
    except AccessRequestNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AccessRequestInvalidTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{request_id}/provision/retry", response_model=AccessRequestResponse)
async def retry_access_request_provisioning(
    request_id: str,
    org_id: str = Depends(get_org_id),
    current_user=Depends(require_access_request_reviewer),
):
    try:
        return await access_request_service.retry_provisioning(
            org_id=org_id,
            request_id=request_id,
            reviewer_id=current_user.id,
        )
    except AccessRequestNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AccessRequestInvalidTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{request_id}", response_model=AccessRequestResponse)
async def get_access_request(
    request_id: str,
    org_id: str = Depends(get_org_id),
    _user=Depends(get_current_user),
):
    try:
        return await access_request_service.get_request(org_id=org_id, request_id=request_id)
    except AccessRequestNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{request_id}/approve", response_model=AccessRequestResponse)
async def approve_access_request(
    request_id: str,
    decision: AccessRequestReviewDecision,
    org_id: str = Depends(get_org_id),
    current_user=Depends(require_access_request_reviewer),
):
    try:
        return await access_request_service.approve_request(
            org_id=org_id,
            request_id=request_id,
            decision=decision,
            reviewer_id=current_user.id,
        )
    except AccessRequestNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AccessRequestInvalidTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{request_id}/reject", response_model=AccessRequestResponse)
async def reject_access_request(
    request_id: str,
    decision: AccessRequestRejectDecision,
    org_id: str = Depends(get_org_id),
    current_user=Depends(require_access_request_reviewer),
):
    try:
        return await access_request_service.reject_request(
            org_id=org_id,
            request_id=request_id,
            decision=decision,
            reviewer_id=current_user.id,
        )
    except AccessRequestNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AccessRequestInvalidTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
