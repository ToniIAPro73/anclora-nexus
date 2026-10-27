"""User-owned public avatar uploads backed by private Vercel Blob storage."""

from __future__ import annotations

from io import BytesIO
from pathlib import PurePosixPath
import re
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from backend.api.deps import get_current_user
from backend.config import settings
from backend.services.blob_storage import get_private_blob, put_private_blob

router = APIRouter()
_ALLOWED_AVATAR_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _matches_image_signature(content_type: str, content: bytes) -> bool:
    if content_type == "image/jpeg":
        return content.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/gif":
        return content.startswith((b"GIF87a", b"GIF89a"))
    if content_type == "image/webp":
        return content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    return False


@router.post("/avatar", response_model=dict)
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    extension = _ALLOWED_AVATAR_TYPES.get(file.content_type or "")
    if not extension:
        raise HTTPException(status_code=415, detail="Unsupported avatar image type")

    content = await file.read(settings.NEXUS_AVATAR_MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="Avatar file is empty")
    if len(content) > settings.NEXUS_AVATAR_MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Avatar exceeds maximum upload size")
    if not _matches_image_signature(file.content_type or "", content):
        raise HTTPException(status_code=415, detail="Avatar content does not match its image type")

    user_id = str(current_user.id)
    pathname = f"{user_id}/avatar-{uuid4().hex}{extension}"
    put_private_blob(pathname, content, content_type=file.content_type or "application/octet-stream", bucket="avatars")
    filename = PurePosixPath(pathname).name
    avatar_url = str(request.base_url).rstrip("/") + f"/api/profile/avatars/{user_id}/{filename}"
    return {"avatar_url": avatar_url}


@router.get("/avatars/{user_id}/{filename}")
async def get_avatar(user_id: str, filename: str):
    try:
        canonical_user_id = str(UUID(user_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="Avatar not found")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,179}\.(jpg|png|webp|gif)", filename):
        raise HTTPException(status_code=404, detail="Avatar not found")
    extension = PurePosixPath(filename).suffix.lower()
    media_type = next((mime for mime, ext in _ALLOWED_AVATAR_TYPES.items() if ext == extension), None)
    if not media_type:
        raise HTTPException(status_code=404, detail="Avatar not found")
    try:
        content = get_private_blob(f"{canonical_user_id}/{filename}", bucket="avatars")
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Avatar not found") from exc
    return StreamingResponse(
        BytesIO(content),
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff"},
    )
