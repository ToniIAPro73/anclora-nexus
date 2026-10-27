"""Copy all Supabase Storage objects into a private Vercel Blob store.

Requires SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY and BLOB_READ_WRITE_TOKEN in
the process environment. It never deletes or modifies the Supabase source.
"""

from __future__ import annotations

import hashlib
import argparse
import json
import os
import sys
from collections.abc import Iterable
from typing import Any

from supabase import create_client
from vercel.blob import sync as blob


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def item_value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def list_bucket_objects(storage_bucket: Any, prefix: str = "") -> Iterable[tuple[str, dict[str, Any]]]:
    offset = 0
    while True:
        entries = storage_bucket.list(prefix, {"limit": 1000, "offset": offset})
        if not entries:
            return
        for entry in entries:
            name = str(item_value(entry, "name", ""))
            if not name or name in {".", ".."}:
                continue
            path = f"{prefix}/{name}".strip("/")
            object_id = item_value(entry, "id")
            metadata = item_value(entry, "metadata", {}) or {}
            if object_id is None and not item_value(entry, "updated_at"):
                yield from list_bucket_objects(storage_bucket, path)
            else:
                yield path, metadata if isinstance(metadata, dict) else {}
        if len(entries) < 1000:
            return
        offset += len(entries)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inventory the application buckets without downloading or writing objects.",
    )
    parser.add_argument(
        "--buckets",
        default=os.environ.get("NEXUS_MIGRATION_BUCKETS", "dms,avatars"),
        help="Comma-separated application buckets (default: dms,avatars).",
    )
    args = parser.parse_args()

    source = create_client(require_env("SUPABASE_URL"), require_env("SUPABASE_SERVICE_ROLE_KEY"))
    bucket_names = list(dict.fromkeys(name.strip() for name in args.buckets.split(",") if name.strip()))
    if not bucket_names:
        raise SystemExit("At least one bucket must be specified")

    source_buckets = {
        str(item_value(bucket, "id") or item_value(bucket, "name") or "")
        for bucket in source.storage.list_buckets()
    }
    missing = [name for name in bucket_names if name not in source_buckets]
    if missing:
        raise SystemExit("Configured migration bucket is missing from Supabase: " + ", ".join(missing))

    if not args.dry_run:
        require_env("BLOB_READ_WRITE_TOKEN")

    report: list[dict[str, Any]] = []
    total_bytes = 0
    total_objects = 0
    for bucket_name in bucket_names:
        storage_bucket = source.storage.from_(bucket_name)
        bucket_count = 0
        bucket_bytes = 0
        for source_path, metadata in list_bucket_objects(storage_bucket):
            bucket_count += 1
            object_bytes = int(metadata.get("size") or 0)
            bucket_bytes += object_bytes
            if not args.dry_run:
                try:
                    data = storage_bucket.download(source_path)
                    content_type = str(
                        metadata.get("mimetype")
                        or metadata.get("contentType")
                        or "application/octet-stream"
                    )
                    target_path = f"{bucket_name}/{source_path}"
                    blob.put_blob(
                        target_path,
                        data,
                        access="private",
                        content_type=content_type,
                        allow_overwrite=True,
                    )
                    downloaded = blob.get_blob(target_path, access="private").body
                    if len(data) != len(downloaded) or sha256(data) != sha256(downloaded):
                        raise RuntimeError("checksum mismatch")
                except Exception as exc:
                    raise RuntimeError(
                        f"Transfer or verification failed in bucket {bucket_name} at object {bucket_count} "
                        f"({type(exc).__name__})"
                    ) from None

        total_objects += bucket_count
        total_bytes += bucket_bytes
        report.append({"bucket": bucket_name, "objects": bucket_count, "bytes": bucket_bytes})

    print(json.dumps({
        "status": "inventory_only" if args.dry_run else "verified",
        "objects": total_objects,
        "bytes": total_bytes,
        "buckets": report,
        "source_deleted": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
