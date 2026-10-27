"""Generated documents API — /api/dms/generated/*"""

from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_current_user, get_org_id
from backend.api.middleware import verify_org_membership
from backend.models.dms import DocumentStatus, GeneratedDocumentCreate, GeneratedDocumentResponse
from backend.services.document_encryption_service import DocumentEncryptionService
from backend.services.document_generation_service import (
    fetch_template_required_fields,
    generate_from_template,
)
from backend.services.supabase_service import supabase_service
from backend.services.blob_storage import put_private_blob

router = APIRouter()


async def require_dms_membership(
    org_id: str = Depends(get_org_id),
    current_user: Any = Depends(get_current_user),
) -> dict:
    return await verify_org_membership(UUID(str(current_user.id)), UUID(str(org_id)), None)


def _table(name: str):
    return supabase_service.client.table(name)


def _fetch_generated(org_id: str, generated_id: str):
    response = (
        _table("generated_documents")
        .select("*")
        .eq("id", generated_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


# ── Generate document from template ───────────────────────────────────────────

@router.post("/folders/{folder_id}/generate", response_model=GeneratedDocumentResponse)
async def generate_document(
    folder_id: UUID,
    body: GeneratedDocumentCreate,
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
    current_user: Any = Depends(get_current_user),
):
    # Verify folder exists
    folder = (
        _table("real_estate_deal_folders")
        .select("id,org_id")
        .eq("id", str(folder_id))
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not folder.data:
        raise HTTPException(status_code=404, detail="Folder not found")

    # Fetch template version and its canonical text
    version_response = (
        _table("document_template_versions")
        .select("id,canonical_text,immutable,template_id")
        .eq("id", str(body.template_version_id))
        .limit(1)
        .execute()
    )
    if not version_response.data:
        raise HTTPException(status_code=404, detail="Template version not found")
    version = version_response.data[0]

    if not version.get("canonical_text"):
        raise HTTPException(
            status_code=422,
            detail="Template version has no canonical text. Upload a .txt version to enable generation.",
        )

    # Fetch field definitions
    field_defs = fetch_template_required_fields(str(body.template_version_id), org_id)
    required_field_keys = [f["field_key"] for f in field_defs if f.get("required")]

    # Apply defaults from field definitions for any missing values
    payload_with_defaults = dict(body.generation_payload)
    for f in field_defs:
        key = f["field_key"]
        if key not in payload_with_defaults and f.get("default_value") is not None:
            payload_with_defaults[key] = f["default_value"]

    # Render template
    result = generate_from_template(
        version["canonical_text"],
        payload_with_defaults,
        required_fields=required_field_keys,
    )

    # Block generation if critical placeholders remain
    if not result.is_complete:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Document has unfilled required fields or placeholders.",
                "unfilled": result.unfilled_placeholders[:20],
            },
        )

    # Encrypt rendered text and store
    enc_svc = DocumentEncryptionService()
    content_bytes = result.rendered_text.encode("utf-8")
    encrypted_payload, iv, auth_tag = enc_svc.encrypt_file(content_bytes)
    sha256_hash = enc_svc.sha256(content_bytes)

    bucket = "dms-generated"
    storage_path = f"generated/{org_id}/{folder_id}/{uuid4()}.enc"
    put_private_blob(storage_path, encrypted_payload, bucket=bucket)

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    insert_payload = {
        "folder_id": str(folder_id),
        "org_id": org_id,
        "template_version_id": str(body.template_version_id),
        "title": body.title,
        "status": DocumentStatus.draft.value,
        "generation_payload": payload_with_defaults,
        "storage_path": storage_path,
        "sha256_hash": sha256_hash,
        "encryption_iv": iv,
        "encryption_auth_tag": auth_tag,
        "generated_by": str(current_user.id),
        "generated_at": now,
    }
    response = _table("generated_documents").insert(insert_payload).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to persist generated document")

    # Create initial version entry
    doc = response.data[0]
    _table("document_versions").insert({
        "generated_document_id": str(doc["id"]),
        "org_id": org_id,
        "version_number": 1,
        "storage_path": storage_path,
        "sha256_hash": sha256_hash,
        "encryption_iv": iv,
        "encryption_auth_tag": auth_tag,
        "change_summary": "Initial generation",
        "immutable": False,
        "created_by": str(current_user.id),
    }).execute()

    return doc


# ── List generated documents for a folder ─────────────────────────────────────

@router.get("/folders/{folder_id}/generated", response_model=list[GeneratedDocumentResponse])
async def list_generated_documents(
    folder_id: UUID,
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
):
    folder = (
        _table("real_estate_deal_folders")
        .select("id")
        .eq("id", str(folder_id))
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not folder.data:
        raise HTTPException(status_code=404, detail="Folder not found")

    response = (
        _table("generated_documents")
        .select("*")
        .eq("folder_id", str(folder_id))
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


# ── Get single generated document ─────────────────────────────────────────────

@router.get("/{generated_id}", response_model=GeneratedDocumentResponse)
async def get_generated_document(
    generated_id: UUID,
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
):
    doc = _fetch_generated(org_id, str(generated_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Generated document not found")
    return doc


# ── Update status (approve / archive) ─────────────────────────────────────────

@router.patch("/{generated_id}/status")
async def update_generated_document_status(
    generated_id: UUID,
    new_status: DocumentStatus,
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
):
    doc = _fetch_generated(org_id, str(generated_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Generated document not found")

    # Signed documents cannot change status
    if doc.get("status") == DocumentStatus.signed.value:
        raise HTTPException(status_code=400, detail="Signed documents cannot change status")

    response = (
        _table("generated_documents")
        .update({"status": new_status.value})
        .eq("id", str(generated_id))
        .eq("org_id", org_id)
        .execute()
    )
    return response.data[0] if response.data else {"ok": True}
