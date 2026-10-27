"""Document versioning and diff — /api/dms/generated/{id}/versions/*"""

import difflib
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.api.deps import get_current_user, get_org_id
from backend.api.middleware import verify_org_membership
from backend.services.document_encryption_service import DocumentEncryptionService
from backend.services.supabase_service import supabase_service
from backend.services.blob_storage import get_private_blob, put_private_blob

router = APIRouter()

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


async def require_dms_membership(
    org_id: str = Depends(get_org_id),
    current_user: Any = Depends(get_current_user),
) -> dict:
    return await verify_org_membership(UUID(str(current_user.id)), UUID(str(org_id)), None)


def _table(name: str):
    return supabase_service.client.table(name)


def _fetch_generated_doc(org_id: str, generated_id: str) -> dict[str, Any] | None:
    response = (
        _table("generated_documents")
        .select("id,org_id,status")
        .eq("id", generated_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


# ── List versions ──────────────────────────────────────────────────────────────

@router.get("/generated/{generated_id}/versions")
async def list_document_versions(
    generated_id: UUID,
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
):
    doc = _fetch_generated_doc(org_id, str(generated_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Generated document not found")

    response = (
        _table("document_versions")
        .select("id,version_number,sha256_hash,change_summary,immutable,created_by,created_at")
        .eq("generated_document_id", str(generated_id))
        .order("version_number", desc=True)
        .execute()
    )
    return response.data or []


# ── Upload a new version ───────────────────────────────────────────────────────

@router.post("/generated/{generated_id}/versions")
async def upload_document_version(
    generated_id: UUID,
    file: UploadFile = File(...),
    change_summary: str | None = None,
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
    current_user: Any = Depends(get_current_user),
):
    doc = _fetch_generated_doc(org_id, str(generated_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Generated document not found")
    if doc.get("status") == "signed":
        raise HTTPException(status_code=400, detail="Signed documents cannot be versioned")

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {file.content_type}")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    enc_svc = DocumentEncryptionService()
    encrypted_payload, iv, auth_tag = enc_svc.encrypt_file(content)
    sha256_hash = enc_svc.sha256(content)

    existing = (
        _table("document_versions")
        .select("version_number")
        .eq("generated_document_id", str(generated_id))
        .order("version_number", desc=True)
        .limit(1)
        .execute()
    )
    next_version = (existing.data[0]["version_number"] + 1) if existing.data else 1

    bucket = "dms-generated"
    storage_path = f"generated/{org_id}/{generated_id}/v{next_version}-{uuid4()}.enc"
    put_private_blob(storage_path, encrypted_payload, bucket=bucket)

    insert_payload = {
        "generated_document_id": str(generated_id),
        "org_id": org_id,
        "version_number": next_version,
        "storage_path": storage_path,
        "sha256_hash": sha256_hash,
        "encryption_iv": iv,
        "encryption_auth_tag": auth_tag,
        "change_summary": change_summary,
        "immutable": False,
        "created_by": str(current_user.id),
    }
    response = _table("document_versions").insert(insert_payload).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create document version")

    return response.data[0]


# ── Text-diff between two plain-text versions ──────────────────────────────────

@router.get("/generated/{generated_id}/versions/diff")
async def diff_document_versions(
    generated_id: UUID,
    from_version: int,
    to_version: int,
    membership: dict = Depends(require_dms_membership),
    org_id: str = Depends(get_org_id),
):
    doc = _fetch_generated_doc(org_id, str(generated_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Generated document not found")

    versions_response = (
        _table("document_versions")
        .select("version_number,storage_path,encryption_iv,encryption_auth_tag,sha256_hash")
        .eq("generated_document_id", str(generated_id))
        .in_("version_number", [from_version, to_version])
        .execute()
    )
    versions = {v["version_number"]: v for v in (versions_response.data or [])}
    if from_version not in versions or to_version not in versions:
        raise HTTPException(status_code=404, detail="One or both versions not found")

    enc_svc = DocumentEncryptionService()
    bucket = "dms-generated"

    def _decrypt_version(version: dict[str, Any]) -> str:
        raw = get_private_blob(version["storage_path"], bucket=bucket)
        text = enc_svc.decrypt_file(raw, version["encryption_iv"], version["encryption_auth_tag"])
        return text.decode("utf-8", errors="replace")

    text_from = _decrypt_version(versions[from_version])
    text_to = _decrypt_version(versions[to_version])

    diff = list(difflib.unified_diff(
        text_from.splitlines(),
        text_to.splitlines(),
        fromfile=f"v{from_version}",
        tofile=f"v{to_version}",
        lineterm="",
    ))

    # Persist the change set
    change_set_payload = {
        "org_id": org_id,
        "from_version_id": versions[from_version].get("id"),
        "to_version_id": versions[to_version].get("id"),
        "diff_payload": diff[:500],    # cap at 500 diff lines
        "risk_level": "low",
    }
    _table("document_change_sets").insert(change_set_payload).execute()

    return {
        "from_version": from_version,
        "to_version": to_version,
        "diff": diff[:500],
        "lines_changed": len([l for l in diff if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]),
    }
