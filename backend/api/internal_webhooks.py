import logging
from hashlib import sha256
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import ValidationError
from backend.config import settings
from backend.services.syncxml_pilot_service import syncxml_pilot_service
from backend.services.neon_service import neon_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal/webhooks", tags=["Internal Webhooks"])

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

def _validate_service_key(api_key: Optional[str], *expected_values: Optional[str]) -> str:
    if not api_key:
        raise HTTPException(status_code=403, detail="Missing API Key")
    token = api_key.replace("Bearer ", "").strip()
    expected = {
        value for value in expected_values
        if isinstance(value, str) and value
    }
    if not expected or token not in expected:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return token


def get_api_key(api_key: str = Security(api_key_header)):
    return _validate_service_key(
        api_key,
        settings.GUESTHUB_WEBHOOK_SECRET,
        settings.NEXUS_INTERNAL_API_KEY,
    )


def get_data_lab_api_key(api_key: str = Security(api_key_header)):
    return _validate_service_key(
        api_key,
        settings.DATA_LAB_WEBHOOK_SECRET,
        settings.NEXUS_INTERNAL_API_KEY,
    )


def _webhook_trace(payload: dict) -> Dict[str, Any]:
    raw_email = str(payload.get("email") or "").strip().lower()
    email_hash = sha256(raw_email.encode("utf-8")).hexdigest()[:12] if raw_email else None
    raw_payload = payload.get("raw") or {}
    return {
        "requestId": payload.get("requestId"),
        "idempotency_key": payload.get("idempotency_key") or raw_payload.get("idempotency_key"),
        "source": payload.get("source"),
        "email_hash": email_hash,
    }


# Live inbound contract: the product posts to /api/internal/webhooks/syncxml-pilot.
# The guesthub-pilot alias is registered for the rename transition (same handler);
# both paths accept the same payload and legacy SYNCXML_PILOT_* error codes.
@router.post("/syncxml-pilot")
@router.post("/guesthub-pilot")
async def syncxml_pilot_webhook(payload: dict, api_key: str = Depends(get_api_key)):
    trace = _webhook_trace(payload)
    logger.info("SyncXML pilot webhook received", extra=trace)
    try:
        result = await syncxml_pilot_service.process_incoming_lead(payload)
    except ValidationError as exc:
        logger.warning(
            "SyncXML pilot webhook rejected by contract validation",
            extra={**trace, "error_type": type(exc).__name__},
        )
        raise HTTPException(
            status_code=422,
            detail={
                "code": "SYNCXML_PILOT_WEBHOOK_INVALID_PAYLOAD",
                "requestId": trace["requestId"],
                "idempotency_key": trace["idempotency_key"],
            },
        ) from exc
    except Exception as exc:
        logger.error(
            "SyncXML pilot webhook persistence failed",
            extra={**trace, "error_type": type(exc).__name__},
        )
        raise HTTPException(
            status_code=500,
            detail={
                "code": "SYNCXML_PILOT_WEBHOOK_PERSISTENCE_FAILED",
                "requestId": trace["requestId"],
                "idempotency_key": trace["idempotency_key"],
            },
        ) from exc

    if result and result.get("blocked"):
        logger.warning(
            "SyncXML pilot webhook blocked before persistence",
            extra={**trace, "block_reason": result.get("reason"), "block_action": result.get("action")},
        )
        raise HTTPException(
            status_code=503,
            detail={
                "code": result.get("reason") or "SYNCXML_PILOT_WEBHOOK_BLOCKED",
                "requestId": trace["requestId"],
                "idempotency_key": trace["idempotency_key"],
                "action": result.get("action"),
            },
        )

    request_id = result.get("id") if result else None
    if not request_id:
        logger.error("SyncXML pilot webhook did not return a persisted request id", extra=trace)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "SYNCXML_PILOT_WEBHOOK_NOT_PERSISTED",
                "requestId": trace["requestId"],
                "idempotency_key": trace["idempotency_key"],
            },
        )

    return {"status": "accepted", "request_id": request_id}


def _upsert_intake_access_request(
    *,
    email: str,
    full_name: str,
    product: str,
    source: str,
    request_type: str,
    idempotency_key: Optional[str],
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Insert a v1 intake contract record into access_requests, with idempotency."""
    org_id = settings.LEGACY_SINGLE_TENANT_ORG_ID or settings.PUBLIC_CTA_ORG_ID

    # Idempotency: return the existing record if already processed
    if idempotency_key:
        existing = (
            neon_service.client
            .table("access_requests")
            .select("id,status")
            .eq("idempotency_key", idempotency_key)
            .limit(1)
            .execute()
        )
        if existing.data:
            return {"id": existing.data[0]["id"], "idempotent": True}

    record: Dict[str, Any] = {
        "org_id": org_id,
        "email": email,
        "full_name": full_name,
        "product": product,
        "source": source,
        "status": "pending",
        "schema_version": "anclora-intake-v1",
        "intake_domain": "access_request",
        "request_type": request_type,
        "routing_target_domain": "access_requests",
        "idempotency_key": idempotency_key,
    }
    if extra:
        record.update(extra)

    result = neon_service.client.table("access_requests").insert(record).execute()
    if not result.data:
        raise RuntimeError("Failed to persist access request from intake forward")
    return {"id": result.data[0]["id"], "idempotent": False}


@router.post("/synergi-admission")
async def synergi_admission_webhook(payload: dict, api_key: str = Depends(get_api_key)):
    """Receive Anclora Intake Contract v1 payload from Synergi (partner admission)."""
    applicant = payload.get("applicant") or {}
    context = (payload.get("context") or {}).get("admission") or {}
    email = applicant.get("email") or ""
    full_name = applicant.get("name") or ""

    if not email or not full_name:
        raise HTTPException(status_code=422, detail="applicant.email and applicant.name are required")

    try:
        result = _upsert_intake_access_request(
            email=email,
            full_name=full_name,
            product="synergi",
            source=payload.get("source") or "synergi_app",
            request_type=payload.get("request_type") or "partner_admission",
            idempotency_key=payload.get("idempotency_key"),
            extra={
                "company_name": applicant.get("organization_name"),
                "admin_notes": context.get("service_summary"),
            },
        )
    except Exception as exc:
        logger.error("synergi_admission_webhook persistence failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to persist partner admission") from exc

    return {"status": "accepted", "request_id": result.get("id"), "idempotent": result.get("idempotent", False)}


@router.post("/data-lab-access")
async def data_lab_access_webhook(payload: dict, api_key: str = Depends(get_data_lab_api_key)):
    """Receive Anclora Intake Contract v1 payload from Data Lab (access request)."""
    applicant = payload.get("applicant") or {}
    metadata = (payload.get("context") or {}).get("request_metadata") or {}
    email = applicant.get("email") or ""
    full_name = applicant.get("name") or ""

    if not email or not full_name:
        raise HTTPException(status_code=422, detail="applicant.email and applicant.name are required")

    try:
        result = _upsert_intake_access_request(
            email=email,
            full_name=full_name,
            product="data_lab",
            source=payload.get("source") or "data_lab_app",
            request_type=payload.get("request_type") or "access_request",
            idempotency_key=payload.get("idempotency_key"),
            extra={
                "intended_use": metadata.get("intended_use"),
                "company_name": applicant.get("organization_name"),
            },
        )
    except Exception as exc:
        logger.error("data_lab_access_webhook persistence failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to persist data lab access request") from exc

    return {"status": "accepted", "request_id": result.get("id"), "idempotent": result.get("idempotent", False)}


@router.post("/dms-retention-sweep")
async def dms_retention_sweep(api_key: str = Depends(get_api_key)):
    """Trigger retention enforcement for all active orgs.

    Called by an external cron (Vercel Cron, GitHub Actions schedule, etc.)
    with the NEXUS_INTERNAL_API_KEY as Bearer token.
    """
    from backend.services.document_retention_service import enforce_retention_for_org

    # Fetch all distinct org IDs that have generated documents
    try:
        orgs_response = (
            neon_service.client
            .table("generated_documents")
            .select("org_id")
            .neq("status", "archived")
            .execute()
        )
        org_ids = list({row["org_id"] for row in (orgs_response.data or [])})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list orgs: {exc}") from exc

    results = []
    errors = []
    for org_id in org_ids:
        try:
            result = await enforce_retention_for_org(org_id)
            results.append(result)
        except Exception as exc:
            errors.append({"org_id": org_id, "error": str(exc)})

    return {
        "orgs_processed": len(results),
        "errors": errors,
        "summary": results,
    }
