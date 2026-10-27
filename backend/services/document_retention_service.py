"""Retention policy enforcement for generated documents."""

from datetime import datetime, timedelta, timezone
from typing import Any

from backend.services.neon_service import neon_service

_DEFAULT_RETENTION_DAYS = 2555  # 7 years


def _table(name: str):
    return neon_service.client.table(name)


def get_retention_policy(org_id: str, template_document_type: str | None = None) -> dict[str, Any]:
    """Return the most specific retention policy for an org and document type."""
    queries = []
    if template_document_type:
        queries.append(
            _table("document_retention_policies")
            .select("*")
            .eq("org_id", org_id)
            .eq("template_document_type", template_document_type)
            .limit(1)
            .execute()
        )
    # Fall back to org-level policy (type IS NULL)
    queries.append(
        _table("document_retention_policies")
        .select("*")
        .eq("org_id", org_id)
        .is_("template_document_type", "null")
        .limit(1)
        .execute()
    )

    for response in queries:
        if response.data:
            return response.data[0]

    return {
        "retention_days": _DEFAULT_RETENTION_DAYS,
        "auto_archive": True,
        "auto_delete": False,
    }


def compute_retention_deadline(generated_at: str | datetime, retention_days: int) -> datetime:
    if isinstance(generated_at, str):
        generated_at = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    return generated_at + timedelta(days=retention_days)


async def enforce_retention_for_org(org_id: str) -> dict[str, Any]:
    """Archive or flag documents past their retention deadline.

    Meant to be called by a scheduled job. Returns a summary of actions taken.
    """
    now = datetime.now(timezone.utc)
    archived = 0
    flagged = 0

    # Fetch all non-archived generated documents for the org
    docs_response = (
        _table("generated_documents")
        .select("id,template_version_id,generated_at,status")
        .eq("org_id", org_id)
        .neq("status", "archived")
        .execute()
    )
    docs = docs_response.data or []

    for doc in docs:
        generated_at = doc.get("generated_at")
        if not generated_at:
            continue

        policy = get_retention_policy(org_id)
        deadline = compute_retention_deadline(generated_at, policy["retention_days"])

        if now > deadline:
            if policy.get("auto_archive"):
                _table("generated_documents").update({"status": "archived"}).eq("id", doc["id"]).eq("org_id", org_id).execute()
                archived += 1
            else:
                flagged += 1

    return {"org_id": org_id, "archived": archived, "flagged": flagged, "evaluated": len(docs)}
