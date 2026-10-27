"""Server-side Vercel Blob access for private Nexus files."""

from __future__ import annotations

from vercel.blob import sync as blob

from backend.config import settings


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
    _require_token()
    return blob.get_blob(_blob_path(pathname, bucket), access="private").body


def delete_private_blob(pathname: str, *, bucket: str = "dms") -> None:
    _require_token()
    blob.delete_blob(_blob_path(pathname, bucket))
