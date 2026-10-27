#!/usr/bin/env python3
"""Seed the 18 x 11 DMS template variants from Markdown sources.

This seeder is intentionally idempotent. It uses the current production schema:
one ``document_templates`` row per language variant and one version row with
the Markdown body as ``canonical_text``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from backend.services.neon_service import neon_service


SEEDS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SEEDS_DIR.parents[1]
TEMPLATES_DIR = SEEDS_DIR / "templates"
MANIFEST_PATH = SEEDS_DIR / "template_manifest.json"
FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_markdown(path: Path) -> tuple[dict[str, Any], str, str]:
    content = path.read_text(encoding="utf-8")
    match = FRONT_MATTER_RE.match(content)
    if not match:
        return {}, content, content
    metadata = yaml.safe_load(match.group(1)) or {}
    body = content[match.end():].strip()
    return metadata, body, content


def load_manifest() -> dict[str, dict[str, Any]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {family["template_key"]: family for family in manifest["families"]}


def sha256_hex(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name) or default
    if value:
        return value
    raise RuntimeError(f"Missing required environment variable: {name}")


def clean_nullable(value: Any) -> Any:
    return None if value == "" else value


def normalize_translation_status(value: Any, language: str) -> str:
    raw = str(value or "").strip()
    if raw == "approved_source":
        return "approved"
    allowed = {
        "draft",
        "machine_translated",
        "human_review_required",
        "legal_review_required",
        "approved",
        "published",
        "retired",
    }
    if raw in allowed:
        return raw
    return "approved" if language == "es" else "machine_translated"


def upsert_template(client: Any, payload: dict[str, Any], dry_run: bool) -> str:
    query = (
        client.table("document_templates")
        .select("id")
        .eq("template_key", payload["template_key"])
        .eq("language", payload["language"])
        .eq("system_template", True)
        .limit(1)
        .execute()
    )
    if dry_run:
        return query.data[0]["id"] if query.data else "__dry_run_template_id__"
    if query.data:
        template_id = query.data[0]["id"]
        client.table("document_templates").update(payload).eq("id", template_id).execute()
        return template_id
    response = client.table("document_templates").insert(payload).execute()
    if not response.data:
        raise RuntimeError(f"Insert failed for {payload['template_key']}:{payload['language']}")
    return response.data[0]["id"]


def upsert_version(client: Any, template_id: str, payload: dict[str, Any], dry_run: bool) -> None:
    if dry_run:
        return
    query = (
        client.table("document_template_versions")
        .select("id")
        .eq("template_id", template_id)
        .eq("version_number", payload["version_number"])
        .eq("language", payload["language"])
        .limit(1)
        .execute()
    )
    if query.data:
        client.table("document_template_versions").update(payload).eq("id", query.data[0]["id"]).execute()
        return
    client.table("document_template_versions").insert(payload).execute()


def seed(org_id: str, dry_run: bool) -> int:
    load_dotenv(REPO_ROOT / ".env")
    client = neon_service.client
    families = load_manifest()
    count = 0

    for path in sorted(TEMPLATES_DIR.glob("*/tpl-*.md")):
        metadata, body, full_content = parse_markdown(path)
        template_key = metadata.get("template_key")
        language = metadata.get("language") or path.parent.name
        if template_key not in families:
            raise RuntimeError(f"Missing manifest family for {template_key} in {path}")

        family = families[template_key]
        display_name = family.get("display_name", {}).get(language) or metadata.get("display_name")
        template_payload = {
            "org_id": org_id,
            "name": display_name or template_key.replace("-", " ").title(),
            "template_key": template_key,
            "ape_code": (family.get("ape_code") or metadata.get("ape_code")) if language == "es" else None,
            "template_family": metadata.get("template_family") or template_key,
            "template_document_type": family["template_document_type"],
            "description": metadata.get("description"),
            "jurisdiction": metadata.get("jurisdiction") or "ES-IB",
            "language": language,
            "is_global": True,
            "status": metadata.get("status") or "draft",
            "system_template": True,
            "operation_types": family.get("operation_types") or [],
            "phase": metadata.get("phase") or family.get("phase") or "general",
            "signable": bool(family.get("signable", metadata.get("signable", True))),
            "requires_legal_review": bool(
                family.get("requires_legal_review", metadata.get("requires_legal_review", True))
            ),
            "requires_advisor_validation": bool(
                family.get("requires_advisor_validation", metadata.get("requires_advisor_validation", True))
            ),
            "effective_from": clean_nullable(metadata.get("effective_from")),
            "effective_until": clean_nullable(metadata.get("effective_until")),
        }
        template_id = upsert_template(client, template_payload, dry_run)

        version_payload = {
            "template_id": template_id,
            "org_id": org_id,
            "version_number": 1,
            "storage_path": metadata.get("storage_path") or f"templates/{language}/{path.name}",
            "sha256_hash": sha256_hex(full_content),
            "encryption_iv": "",
            "encryption_auth_tag": "",
            "canonical_text": body,
            "change_summary": f"Initial canonical seed - {metadata.get('version') or '0.1.0'}",
            "immutable": False,
            "template_key": template_key,
            "language": language,
            "locale": metadata.get("locale"),
            "translation_status": normalize_translation_status(
                metadata.get("translation_status"),
                language,
            ),
            "legal_review_status": metadata.get("legal_review_status") or "pending",
            "source_language": metadata.get("source_language") or "es",
            "source_version": str(metadata.get("source_version") or metadata.get("version") or "0.1.0"),
            "version_semver": str(metadata.get("version") or "0.1.0"),
            "status": metadata.get("status") or "draft",
        }
        upsert_version(client, template_id, version_payload, dry_run)
        count += 1
        action = "DRY" if dry_run else "UPSERT"
        print(f"{action}: {template_key}:{language}")

    return count


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org-id", default=os.environ.get("LEGACY_SINGLE_TENANT_ORG_ID"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    org_id = args.org_id or env("PUBLIC_CTA_ORG_ID")
    count = seed(org_id, args.dry_run)
    print(f"Seeded {count} template variants")
    return 0


if __name__ == "__main__":
    sys.exit(main())
