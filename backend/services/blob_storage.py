"""Server-side Vercel Blob access for private Nexus files."""

from __future__ import annotations

from vercel.blob import sync as blob

from backend.config import settings


def _legacy_supabase_path(pathname: str, bucket: str) -> str:
    if bucket == "avatars" and pathname.startswith("avatars/"):
        return pathname[len("avatars/"):]
    return pathname


def _use_blob() -> bool:
    return settings.NEXUS_STORAGE_PROVIDER.strip().lower() == "vercel_blob"


def _blob_path(pathname: str, bucket: str) -> str:
    return f"{bucket}/{pathname.lstrip('/')}"


def _require_token() -> None:
    if not settings.BLOB_READ_WRITE_TOKEN:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN is required for Vercel Blob storage")


def put_private_blob(
    pathname: str,
    content: bytes,
    *,
    content_type: str = "application/octet-stream",
    overwrite: bool = False,
    bucket: str = "dms",
) -> str:
    if not _use_blob():
        from backend.services.supabase_service import supabase_service

        result = supabase_service.client.storage.from_(bucket).upload(
            _legacy_supabase_path(pathname, bucket),
            content,
            file_options={"content-type": content_type, "upsert": "true" if overwrite else "false"},
        )
        if isinstance(result, dict) and result.get("error"):
            raise RuntimeError(str(result["error"]))
        return pathname
    _require_token()
    result = blob.put_blob(
        _blob_path(pathname, bucket),
        content,
        access="private",
        content_type=content_type,
        allow_overwrite=overwrite,
    )
    return result.pathname


def get_private_blob(pathname: str, *, bucket: str = "dms") -> bytes:
    if not _use_blob():
        from backend.services.supabase_service import supabase_service

        return supabase_service.client.storage.from_(bucket).download(_legacy_supabase_path(pathname, bucket))
    _require_token()
    return blob.get_blob(_blob_path(pathname, bucket), access="private").body


def delete_private_blob(pathname: str, *, bucket: str = "dms") -> None:
    if not _use_blob():
        from backend.services.supabase_service import supabase_service

        supabase_service.client.storage.from_(bucket).remove([_legacy_supabase_path(pathname, bucket)])
        return
    _require_token()
    blob.delete_blob(_blob_path(pathname, bucket))
