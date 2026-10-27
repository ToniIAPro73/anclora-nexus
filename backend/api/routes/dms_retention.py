"""Retention policy management — /api/dms/retention/*"""

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.deps import get_current_user, get_org_id
from backend.api.middleware import verify_org_membership
from backend.models.dms import TemplateDocumentType
from backend.services.document_retention_service import enforce_retention_for_org, get_retention_policy
from backend.services.neon_service import neon_service

router = APIRouter()


async def require_dms_membership(
    org_id: str = Depends(get_org_id),
    current_user: Any = Depends(get_current_user),
) -> dict:
    return await verify_org_membership(UUID(str(current_user.id)), UUID(str(org_id)), None)


def _table(name: str):
    return neon_service.client.table(name)


class RetentionPolicyCreate(BaseModel):
    template_document_type: Optional[TemplateDocumentType] = None
    retention_days: int = 2555
    auto_archive: bool = True
    auto_delete: bool = False


@router.get("/")
@router.get("", include_in_schema=False)
async def list_retention_policies(
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
):
    response = (
        _table("document_retention_policies")
        .select("*")
        .eq("org_id", org_id)
        .order("created_at")
        .execute()
    )
    return response.data or []


@router.post("/")
@router.post("", include_in_schema=False)
async def create_retention_policy(
    body: RetentionPolicyCreate,
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
):
    if body.retention_days < 365:
        raise HTTPException(status_code=400, detail="Minimum retention is 365 days")
    if body.auto_delete:
        raise HTTPException(status_code=400, detail="auto_delete is disabled — contact compliance")

    payload = {
        "org_id": org_id,
        "template_document_type": body.template_document_type.value if body.template_document_type else None,
        "retention_days": body.retention_days,
        "auto_archive": body.auto_archive,
        "auto_delete": False,
    }
    response = _table("document_retention_policies").insert(payload).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create retention policy")
    return response.data[0]


@router.get("/effective")
async def get_effective_policy(
    document_type: Optional[TemplateDocumentType] = None,
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
):
    policy = get_retention_policy(org_id, document_type.value if document_type else None)
    return policy


@router.post("/enforce")
async def run_retention_enforcement(
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
):
    result = await enforce_retention_for_org(org_id)
    return result
