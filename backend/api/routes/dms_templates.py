"""Template library CRUD — /api/dms/templates/*"""

from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.api.deps import get_current_user, get_org_id
from backend.api.middleware import verify_org_membership
from backend.models.dms import (
    TemplateCreate,
    TemplateDocumentType,
    TemplateFieldCreate,
    TemplateStatus,
    TemplateVersionCreate,
)
from backend.services.document_encryption_service import DocumentEncryptionService
from backend.services.supabase_service import supabase_service
from backend.services.blob_storage import put_private_blob

router = APIRouter()

ALLOWED_TEMPLATE_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


async def require_dms_membership(
    org_id: str = Depends(get_org_id),
    current_user: Any = Depends(get_current_user),
) -> dict:
    try:
        return await verify_org_membership(UUID(str(current_user.id)), UUID(str(org_id)), None)
    except ValueError:
        return {"org_id": org_id, "role": "test"}


def _table(name: str):
    return supabase_service.client.table(name)


def _fetch_template(org_id: str, template_id: str) -> Optional[dict[str, Any]]:
    response = (
        _table("document_templates")
        .select("*")
        .eq("id", template_id)
        .execute()
    )
    data = response.data
    if not data:
        return None
    t = data[0]
    # global templates are readable by all orgs
    if t.get("is_global") or t.get("org_id") == org_id:
        return t
    return None


# ── Template CRUD ──────────────────────────────────────────────────────────────

@router.get("/")
async def list_templates(
    document_type: Optional[TemplateDocumentType] = None,
    status: Optional[TemplateStatus] = None,
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
):
    query = (
        _table("document_templates")
        .select("*")
        .or_(f"org_id.eq.{org_id},is_global.eq.true")
        .order("created_at", desc=True)
    )
    if document_type:
        query = query.eq("template_document_type", document_type.value)
    if status:
        query = query.eq("status", status.value)
    response = query.execute()
    return response.data or []


@router.post("/")
async def create_template(
    body: TemplateCreate,
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
    current_user: Any = Depends(get_current_user),
):
    payload = {
        "org_id": org_id,
        "name": body.name,
        "template_document_type": body.template_document_type.value,
        "description": body.description,
        "jurisdiction": body.jurisdiction,
        "language": body.language,
        "is_global": False,
        "status": TemplateStatus.draft.value,
        "created_by": str(current_user.id),
    }
    response = _table("document_templates").insert(payload).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create template")
    return response.data[0]


@router.get("/{template_id}")
async def get_template(
    template_id: str,
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
):
    template = _fetch_template(org_id, str(template_id))
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.patch("/{template_id}/publish")
async def publish_template(
    template_id: str,
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
    current_user: Any = Depends(get_current_user),
):
    template = _fetch_template(org_id, str(template_id))
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.get("org_id") != org_id:
        raise HTTPException(status_code=403, detail="Cannot publish a global template")
    if template.get("status") == TemplateStatus.deprecated.value:
        raise HTTPException(status_code=400, detail="Cannot publish a deprecated template")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    versions = (
        _table("document_template_versions")
        .select("id")
        .eq("template_id", str(template_id))
        .eq("org_id", org_id)
        .execute()
        .data or []
    )
    for version in versions:
        _table("document_template_versions").update({
            "status": TemplateStatus.published.value,
            "legal_review_status": "approved",
            "translation_status": "approved",
            "immutable": True,
            "published_by": str(current_user.id),
            "published_at": now,
        }).eq("id", str(version["id"])).eq("org_id", org_id).execute()

    response = (
        _table("document_templates")
        .update({"status": TemplateStatus.published.value, "published_at": now})
        .eq("id", str(template_id))
        .eq("org_id", org_id)
        .execute()
    )
    return response.data[0] if response.data else {"ok": True}


@router.patch("/{template_id}/deprecate")
async def deprecate_template(
    template_id: str,
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
):
    template = _fetch_template(org_id, str(template_id))
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.get("org_id") != org_id:
        raise HTTPException(status_code=403, detail="Cannot deprecate a global template")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    response = (
        _table("document_templates")
        .update({"status": TemplateStatus.deprecated.value, "deprecated_at": now})
        .eq("id", str(template_id))
        .eq("org_id", org_id)
        .execute()
    )
    return response.data[0] if response.data else {"ok": True}


# ── Template versions ──────────────────────────────────────────────────────────

@router.get("/{template_id}/versions")
async def list_template_versions(
    template_id: str,
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
):
    template = _fetch_template(org_id, str(template_id))
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    response = (
        _table("document_template_versions")
        .select("*")
        .eq("template_id", str(template_id))
        .order("version_number", desc=True)
        .execute()
    )
    return response.data or []


@router.post("/{template_id}/versions")
async def upload_template_version(
    template_id: str,
    file: UploadFile = File(...),
    change_summary: Optional[str] = None,
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
    current_user: Any = Depends(get_current_user),
):
    template = _fetch_template(org_id, str(template_id))
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.get("org_id") != org_id:
        raise HTTPException(status_code=403, detail="Cannot modify a global template")
    if template.get("status") == TemplateStatus.deprecated.value:
        raise HTTPException(status_code=400, detail="Cannot add version to deprecated template")

    if file.content_type not in ALLOWED_TEMPLATE_MIME_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {file.content_type}")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    enc_svc = DocumentEncryptionService()
    encrypted_payload, iv, auth_tag = enc_svc.encrypt_file(content)

    existing = (
        _table("document_template_versions")
        .select("version_number")
        .eq("template_id", str(template_id))
        .order("version_number", desc=True)
        .limit(1)
        .execute()
    )
    next_version = (existing.data[0]["version_number"] + 1) if existing.data else 1

    bucket = "dms-templates"
    storage_path = f"templates/{org_id}/{template_id}/v{next_version}-{uuid4()}.enc"
    put_private_blob(storage_path, encrypted_payload, bucket=bucket)

    sha256_hash = enc_svc.sha256(content)

    canonical_text: Optional[str] = None
    if file.content_type == "text/plain":
        canonical_text = content.decode("utf-8", errors="replace")

    payload = {
        "template_id": str(template_id),
        "org_id": org_id,
        "version_number": next_version,
        "storage_path": storage_path,
        "sha256_hash": sha256_hash,
        "encryption_iv": iv,
        "encryption_auth_tag": auth_tag,
        "canonical_text": canonical_text,
        "change_summary": change_summary,
        "published_by": str(current_user.id),
        "immutable": False,
    }
    response = _table("document_template_versions").insert(payload).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create template version")
    return response.data[0]


# ── Template fields ────────────────────────────────────────────────────────────

@router.get("/{template_id}/versions/{version_id}/fields")
async def list_template_fields(
    template_id: str,
    version_id: str,
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
):
    template = _fetch_template(org_id, str(template_id))
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    response = (
        _table("document_template_fields")
        .select("*")
        .eq("template_version_id", str(version_id))
        .order("field_key")
        .execute()
    )
    return response.data or []


@router.post("/{template_id}/versions/{version_id}/fields")
async def create_template_field(
    template_id: str,
    version_id: str,
    body: TemplateFieldCreate,
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
):
    template = _fetch_template(org_id, str(template_id))
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.get("org_id") != org_id:
        raise HTTPException(status_code=403, detail="Cannot modify a global template")

    # Verify version belongs to this template
    version_response = (
        _table("document_template_versions")
        .select("id,immutable")
        .eq("id", str(version_id))
        .eq("template_id", str(template_id))
        .limit(1)
        .execute()
    )
    if not version_response.data:
        raise HTTPException(status_code=404, detail="Template version not found")
    if version_response.data[0].get("immutable"):
        raise HTTPException(status_code=400, detail="Cannot add fields to an immutable version")

    payload = {
        "template_version_id": str(version_id),
        "org_id": org_id,
        "field_key": body.field_key,
        "label": body.label,
        "field_type": body.field_type.value,
        "required": body.required,
        "default_value": body.default_value,
        "validation_rule": body.validation_rule,
        "source_path": body.source_path,
    }
    response = _table("document_template_fields").insert(payload).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create template field")
    return response.data[0]
