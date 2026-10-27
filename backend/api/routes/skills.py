"""
Operational skill runner routes.

These routes expose the small set of skills needed by frontend cron jobs and
manual ops without going through the legacy graph dispatcher.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException

from backend.config import settings
from backend.api.deps import get_current_user
from backend.services.finops import finops_service
from backend.services.org_context_service import resolve_legacy_org_id_http
from backend.services.llm_service import llm_service
from backend.services.neon_service import neon_service
from backend.skills.fsbo_scraper import run_fsbo_scraper
from backend.skills.notebooklm_sync import run_notebooklm_sync
from backend.skills.prospection_weekly import run_prospection_weekly
from backend.skills.recap_weekly import run_recap_weekly
from backend.skills.seller_outreach_batch import run_seller_outreach_batch
from backend.skills.seller_signal_source_run import run_seller_signal_source_run
from backend.skills.seller_signal_ingest import run_seller_signal_ingest


router = APIRouter()


async def _resolve_org_id(
    authorization: Optional[str],
    x_cron_secret: Optional[str],
    requested_org_id: Optional[str],
) -> str:
    # Internal cron path: shared secret instead of Neon JWT
    if settings.CRON_SECRET and x_cron_secret == settings.CRON_SECRET:
        return resolve_legacy_org_id_http(requested_org_id, "skills-run-cron")

    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        user = await get_current_user(authorization)
        response = (
            neon_service.client.table("user_profiles")
            .select("org_id")
            .eq("id", user.id)
            .single()
            .execute()
        )
        profile = response.data or {}
        return str(profile.get("org_id") or resolve_legacy_org_id_http(requested_org_id, "skills-run-auth"))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Auth error: {str(exc)}")


@router.post("/skills/run")
async def run_skill(
    payload: Dict[str, Any],
    authorization: Optional[str] = Header(None),
    x_cron_secret: Optional[str] = Header(None),
):
    skill_name = payload.get("skill")
    skill_data = payload.get("data", {})

    if not skill_name:
        raise HTTPException(status_code=400, detail="Missing 'skill' field in payload")

    org_id = await _resolve_org_id(
        authorization=authorization,
        x_cron_secret=x_cron_secret,
        requested_org_id=skill_data.get("org_id"),
    )
    budget_status = await finops_service.get_budget_status(org_id)
    if budget_status.status == "hard_stop":
        raise HTTPException(
            status_code=402,
            detail="Monthly budget exceeded. Critical operations only (402 Payment Required).",
        )

    merged_data = {**skill_data, "org_id": skill_data.get("org_id", org_id)}

    skill_map = {
        "prospection_weekly": run_prospection_weekly,
        "recap_weekly": run_recap_weekly,
        "notebooklm_sync": run_notebooklm_sync,
        "seller_signal_ingest": run_seller_signal_ingest,
        "seller_signal_source_run": run_seller_signal_source_run,
        "seller_outreach_batch": run_seller_outreach_batch,
        "fsbo_scraper": run_fsbo_scraper,
    }

    runner = skill_map.get(skill_name)
    if not runner:
        raise HTTPException(status_code=404, detail=f"Unsupported skill: {skill_name}")

    try:
        return await runner(merged_data, llm_service, neon_service)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
