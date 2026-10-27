"""Legal review decisions — /api/dms/legal-review/*"""

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.api.deps import get_current_user, get_org_id
from backend.api.middleware import verify_org_membership
from backend.services.advisor_contract_validator_service import advisor_contract_validator_service
from backend.services.neon_service import neon_service

router = APIRouter()


async def require_dms_membership(
    org_id: str = Depends(get_org_id),
    current_user: Any = Depends(get_current_user),
) -> dict:
    return await verify_org_membership(UUID(str(current_user.id)), UUID(str(org_id)), None)


def _table(name: str):
    return neon_service.client.table(name)


class AutoReviewRequest(BaseModel):
    document_text: str
    document_type: Optional[str] = "generico"
    canonical_template: Optional[str] = None
    jurisdiction: str = "España"
    language: str = "es"


class ManualDecisionRequest(BaseModel):
    status: str   # approved | rejected | escalated
    notes: Optional[str] = None


# ── Trigger auto review via Advisor AI ────────────────────────────────────────

@router.post("/generated/{generated_id}/review/auto")
async def trigger_auto_review(
    generated_id: UUID,
    body: AutoReviewRequest,
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
    current_user: Any = Depends(get_current_user),
):
    # Verify document belongs to org
    doc_response = (
        _table("generated_documents")
        .select("id,org_id,title,template_version_id")
        .eq("id", str(generated_id))
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not doc_response.data:
        raise HTTPException(status_code=404, detail="Generated document not found")
    doc = doc_response.data[0]

    # Call Advisor AI /api/legal-documents/validate
    ai_result = await advisor_contract_validator_service.validate_legal_document(
        document_text=body.document_text,
        document_type=body.document_type or "generico",
        canonical_template=body.canonical_template,
        jurisdiction=body.jurisdiction,
        language=body.language,
        document_id=str(generated_id),
        org_id=org_id,
    )

    risk_level = ai_result.get("risk_level", "medium")
    block_signing = ai_result.get("block_signing", False)
    advisor_available = ai_result.get("advisor_available", False)

    review_status = "approved"
    if not advisor_available:
        review_status = "pending"
    elif block_signing:
        review_status = "escalated"

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    insert_payload = {
        "generated_document_id": str(generated_id),
        "org_id": org_id,
        "review_type": "auto",
        "status": review_status,
        "risk_level": risk_level,
        "block_signing": block_signing,
        "reviewer_id": None,
        "advisor_ai_request_id": ai_result.get("document_id"),
        "advisor_ai_response": ai_result,
        "decided_at": now if advisor_available else None,
    }
    response = _table("legal_review_decisions").insert(insert_payload).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to save review decision")

    # Update document status
    new_doc_status = "review_required" if block_signing else "approved"
    if not advisor_available:
        new_doc_status = "review_required"
    _table("generated_documents").update({"status": new_doc_status}).eq("id", str(generated_id)).eq("org_id", org_id).execute()

    return response.data[0]


# ── Manual review decision ─────────────────────────────────────────────────────

@router.post("/generated/{generated_id}/review/manual")
async def submit_manual_review(
    generated_id: UUID,
    body: ManualDecisionRequest,
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
    current_user: Any = Depends(get_current_user),
):
    valid_statuses = {"approved", "rejected", "escalated"}
    if body.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"status must be one of {valid_statuses}")

    doc_response = (
        _table("generated_documents")
        .select("id,org_id")
        .eq("id", str(generated_id))
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not doc_response.data:
        raise HTTPException(status_code=404, detail="Generated document not found")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    insert_payload = {
        "generated_document_id": str(generated_id),
        "org_id": org_id,
        "review_type": "manual",
        "status": body.status,
        "risk_level": "medium",
        "block_signing": body.status != "approved",
        "reviewer_id": str(current_user.id),
        "notes": body.notes,
        "decided_at": now,
    }
    response = _table("legal_review_decisions").insert(insert_payload).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to save review decision")

    # Reflect decision in document status
    doc_status_map = {"approved": "approved", "rejected": "review_required", "escalated": "review_required"}
    _table("generated_documents").update({"status": doc_status_map[body.status]}).eq("id", str(generated_id)).eq("org_id", org_id).execute()

    return response.data[0]


# ── List review history ────────────────────────────────────────────────────────

@router.get("/generated/{generated_id}/review")
async def list_review_decisions(
    generated_id: UUID,
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
):
    doc_response = (
        _table("generated_documents")
        .select("id")
        .eq("id", str(generated_id))
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not doc_response.data:
        raise HTTPException(status_code=404, detail="Generated document not found")

    response = (
        _table("legal_review_decisions")
        .select("*")
        .eq("generated_document_id", str(generated_id))
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


# ── Legal review queue (org-wide) ─────────────────────────────────────────────

@router.get("/legal-review/queue")
async def list_legal_review_queue(
    status: Optional[str] = Query(None, description="Filter by review status (pending, approved, rejected, ...)"),
    limit: int = Query(50, ge=1, le=200),
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
):
    """Return all legal review decisions for the org, enriched with document metadata."""
    q = (
        _table("legal_review_decisions")
        .select(
            "id,generated_document_id,review_type,status,risk_level,block_signing,"
            "reviewer_id,notes,decided_at,created_at,"
            "generated_documents!legal_review_decisions_generated_document_id_fkey("
            "id,title,status,folder_id,language"
            ")"
        )
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if status:
        q = q.eq("status", status)
    rows = q.execute().data or []

    # Flatten nested document join
    result = []
    for row in rows:
        doc = row.pop("generated_documents", None) or {}
        result.append({**row, "document": doc if doc else None})
    return result
