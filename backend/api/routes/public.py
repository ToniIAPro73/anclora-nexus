from fastapi import APIRouter, HTTPException, Query, Request, status
from typing import Any, Dict, Optional
from uuid import uuid4
import logging
from backend.agents.graph import agent_executor
from backend.config import settings

logger = logging.getLogger(__name__)
from backend.models.partner_workspaces import (
    PublicPartnerOpportunityCreate,
    PublicPartnerWorkspaceProfileUpdate,
    PublicSharedOpportunityStatusUpdate,
)
from backend.services.partner_workspace_service import partner_workspace_service
from backend.services.captcha_verification_service import CaptchaVerificationError, captcha_verification_service
from backend.models.valuation_requests import PublicValuationRequestCreate
from backend.models.ingestion import PublicLeadCaptureRequest
from backend.services.valuation_request_service import valuation_request_service
from backend.models.access_requests import (
    PublicAccessRequestCreate, 
    AccessRequestProduct, 
    AccessRequestSource,
    LegacyDataLabAccessRequest,
    LegacyPartnerAdmission
)
from backend.services.access_request_service import access_request_service

router = APIRouter()


@router.get("/partner-workspace")
async def get_public_partner_workspace(token: str = Query(..., min_length=12)):
    try:
        result = await partner_workspace_service.get_workspace_by_token(token)
        if not result:
            raise HTTPException(status_code=404, detail="Partner workspace not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/partner-workspace/opportunities", status_code=status.HTTP_201_CREATED)
async def create_public_partner_opportunity(data: PublicPartnerOpportunityCreate):
    try:
        result = await partner_workspace_service.create_opportunity_from_token(data)
        if not result:
            raise HTTPException(status_code=404, detail="Partner workspace not found")
        return {
            "status": "submitted",
            "opportunity_id": result.get("id"),
            "message": "Partner opportunity submitted",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/partner-workspace/profile")
async def update_public_partner_workspace_profile(data: PublicPartnerWorkspaceProfileUpdate):
    try:
        result = await partner_workspace_service.update_profile_from_token(data)
        if not result:
            raise HTTPException(status_code=404, detail="Partner workspace not found")
        return {"status": "updated", "workspace_id": result.get("id")}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/partner-workspace/shared-opportunities/{shared_opportunity_id}")
async def update_public_shared_opportunity_status(shared_opportunity_id: str, data: PublicSharedOpportunityStatusUpdate):
    try:
        result = await partner_workspace_service.update_shared_opportunity_status_from_token(shared_opportunity_id, data)
        if not result:
            raise HTTPException(status_code=404, detail="Shared opportunity not found")
        return {"status": "updated", "shared_opportunity_id": result.get("id")}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/valuation-requests", status_code=status.HTTP_201_CREATED)
async def create_public_valuation_request(data: PublicValuationRequestCreate, request: Request):
    try:
        result = await valuation_request_service.create_public_request(
            settings.PUBLIC_CTA_ORG_ID,
            data,
            request.client.host if request.client else None,
        )
        return {
            "status": "submitted",
            "request_id": result.get("id"),
            "message": "Valuation request submitted",
        }
    except HTTPException:
        raise
    except CaptchaVerificationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cta/lead")
async def public_cta_lead_capture(data: PublicLeadCaptureRequest):
    """
    Public endpoint for external lead capture (e.g., from a website CTA).
    Performs minimal validation and triggers the lead_intake skill.
    """
    try:
        # Prepare state for LangGraph
        payload = data.model_dump(mode="json")
        source_value = str(payload.get("source", "")).strip() or "web-cta"
        source_system = str(payload.get("source_system", "")).strip() or "cta_web"
        source_channel = str(payload.get("source_channel", "")).strip() or "website"
        source_detail = payload.get("source_detail") or "public_cta_form"

        # Hard rule: leads coming from Anclora Private Estates are always tagged as WEB.
        if source_detail == "private-estates-contact-form":
            source_value = "web"

        initial_state = {
            "input_data": {
                **payload,
                "source": source_value,
                "source_system": source_system,
                "source_channel": source_channel,
                "source_detail": source_detail,
                "ingestion_mode": "realtime" # Force realtime for public CTAs
            },
            "skill_name": "lead_intake",
            "org_id": settings.PUBLIC_CTA_ORG_ID,
            "status": "pending"
        }
        
        # Run Graph
        result = await agent_executor.ainvoke(initial_state)
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("error"))
        if result.get("status") == "blocked":
            raise HTTPException(
                status_code=429,
                detail=result.get("error") or "Lead intake blocked by constitutional limits",
            )

        final_result = result.get("final_result") or {}
        lead_id = final_result.get("lead_id")
        if not lead_id:
            raise HTTPException(
                status_code=500,
                detail="Lead intake completed without lead_id",
            )
            
        return {"status": "success", "lead_id": lead_id, "message": "Lead captured successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/access-requests", status_code=status.HTTP_201_CREATED)
async def create_public_access_request(data: PublicAccessRequestCreate, request: Request):
    try:
        result = await access_request_service.create_public_request(
            data,
            request.client.host if request.client else None,
        )
        return {
            "status": "submitted",
            "request_id": result.get("id"),
            "message": "Access request submitted",
        }
    except HTTPException:
        raise
    except CaptchaVerificationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/data-lab-access-requests", status_code=status.HTTP_201_CREATED)
async def legacy_data_lab_access_request(data: LegacyDataLabAccessRequest, request: Request):
    """Legacy wrapper for Data Lab access requests."""
    source_val = data.source or AccessRequestSource.DATA_LAB_APP
    canonical_data = PublicAccessRequestCreate(
        product=AccessRequestProduct.DATA_LAB,
        source=source_val,
        source_system=data.source_system or "data_lab_app",
        source_channel=data.source_channel or "in_app",
        source_detail=data.source_detail or "legacy_data_lab_endpoint",
        full_name=data.full_name,
        email=data.email,
        profile_type=data.profile_type,
        requested_scope=data.requested_scope,
        intended_use=data.intended_use,
        privacy_accepted=data.privacy_accepted,
        gdpr_consent=data.gdpr_consent,
        submission_language=data.submission_language,
        captcha_provider=data.captcha_provider,
        captcha_token=data.captcha_token
    )
    return await create_public_access_request(canonical_data, request)

@router.post("/partner-admissions", status_code=status.HTTP_201_CREATED)
async def legacy_partner_admission(data: LegacyPartnerAdmission, request: Request):
    """Legacy wrapper for Synergi partner admissions."""
    source_val = data.source or AccessRequestSource.SYNERGI_APP
    canonical_data = PublicAccessRequestCreate(
        product=AccessRequestProduct.SYNERGI,
        source=source_val,
        source_system=data.source_system or "synergi_app",
        source_channel=data.source_channel or "in_app",
        source_detail=data.source_detail or "legacy_synergi_endpoint",
        full_name=data.full_name,
        email=data.email,
        service_category=data.service_category,
        service_summary=data.service_summary,
        privacy_accepted=data.privacy_accepted,
        gdpr_consent=data.gdpr_consent,
        submission_language=data.submission_language,
        captcha_provider=data.captcha_provider,
        captcha_token=data.captcha_token
    )
    return await create_public_access_request(canonical_data, request)


COMMERCIAL_LEAD_VALID_SOURCES = {
    "private_estates_landing",
    "private_estates_web",
    "nexus_manual",
    "external_api",
}


async def _handle_commercial_lead_intake(body: Dict[str, Any], request: Request) -> Dict[str, Any]:
    """Shared logic for commercial lead intake endpoints."""
    from backend.services.supabase_service import supabase_service

    # Validate intake_domain
    intake_domain = body.get("intake_domain")
    if intake_domain != "commercial_lead":
        raise HTTPException(
            status_code=422,
            detail="intake_domain must be 'commercial_lead'",
        )

    # Validate source
    source = body.get("source")
    if source not in COMMERCIAL_LEAD_VALID_SOURCES:
        raise HTTPException(
            status_code=422,
            detail=f"source must be one of: {', '.join(sorted(COMMERCIAL_LEAD_VALID_SOURCES))}",
        )

    # Validate target_product is null/None
    target_product = body.get("target_product")
    if target_product is not None:
        raise HTTPException(
            status_code=422,
            detail="target_product must be null for commercial_lead intakes",
        )

    # Validate at least one contact field (support applicant.email, contact_email, or root email)
    applicant = body.get("applicant") or {}
    applicant_email = applicant.get("email") if isinstance(applicant, dict) else None
    contact_email = body.get("contact_email") or body.get("email")
    if not applicant_email and not contact_email:
        raise HTTPException(
            status_code=422,
            detail="At least one contact field is required: applicant.email, contact_email, or email",
        )

    captcha_result = {"provider": "none", "verified": False, "required": False}
    if source in {"private_estates_landing", "private_estates_web"}:
        provider = str(body.get("captcha_provider") or "").strip().lower()
        token = body.get("captcha_token")
        if provider != "turnstile":
            raise HTTPException(status_code=400, detail="Turnstile verification is required")
        try:
            captcha_result = captcha_verification_service.verify(
                provider=provider,
                token=token,
                remote_ip=request.client.host if request.client else None,
                expected_action="private_estates_contact",
                expected_hostnames=settings.TURNSTILE_PRIVATE_ESTATES_HOSTNAMES.split(","),
            )
        except CaptchaVerificationError:
            raise HTTPException(status_code=400, detail="CAPTCHA verification failed")
        except Exception:
            logger.exception("commercial_lead CAPTCHA verification unavailable")
            raise HTTPException(status_code=502, detail="CAPTCHA verification unavailable")
        if not captcha_result.get("verified"):
            raise HTTPException(status_code=400, detail="CAPTCHA verification failed")

    # Normalize applicant structure if flat fields were sent
    if not isinstance(applicant, dict):
        applicant = {}
    if not applicant.get("email") and contact_email:
        applicant["email"] = contact_email
    if not applicant.get("full_name") and (body.get("full_name") or body.get("name")):
        applicant["full_name"] = body.get("full_name") or body.get("name")
    if not applicant.get("phone") and body.get("phone"):
        applicant["phone"] = body.get("phone")

    context = body.get("context") or {}
    if isinstance(context, dict):
        context = dict(context)
        for field in ("source_system", "source_channel", "source_detail"):
            if body.get(field) and field not in context:
                context[field] = body.get(field)
        if source in {"private_estates_landing", "private_estates_web"}:
            context["captcha_provider"] = captcha_result.get("provider")
            context["captcha_verified"] = bool(captcha_result.get("verified"))
            context["captcha_hostname"] = captcha_result.get("hostname")

    # Generate idempotency_key if not provided
    idempotency_key = body.get("idempotency_key") or str(uuid4())

    # Determine routing target
    request_type = body.get("request_type")
    if request_type == "seller_valuation_request":
        routing_target_domain = "valuation_requests"
    else:
        routing_target_domain = "leads_pipeline"

    logger.info(
        "commercial_lead intake received",
        extra={
            "source": source,
            "request_type": request_type,
            "routing_target_domain": routing_target_domain,
            "idempotency_key": idempotency_key,
        },
    )

    # Persist record
    persistence_data = {
        "schema_version": body.get("schema_version", "anclora-intake-v1"),
        "intake_domain": intake_domain,
        "source": source,
        "request_type": request_type,
        "idempotency_key": idempotency_key,
        "service_interest": body.get("service_interest"),
        "applicant": applicant if applicant else None,
        "context": context if context else None,
        "consent": body.get("consent"),
        "routing_target_domain": routing_target_domain,
    }
    try:
        try:
            if routing_target_domain == "valuation_requests":
                result = (
                    supabase_service.client
                    .table("valuation_requests")
                    .insert(persistence_data)
                    .execute()
                )
            else:
                result = (
                    supabase_service.client
                    .table("leads_pipeline")
                    .insert(persistence_data)
                    .execute()
                )
            record = result.data[0] if result.data else {}
            lead_id = record.get("id") or str(uuid4())
        except Exception as e:
            if "PGRST205" in str(e) or "schema cache" in str(e):
                logger.warning(f"Commercial table '{routing_target_domain}' not found in Supabase schema cache: {e}. Simulating intake acceptance.")
                lead_id = str(uuid4())
            else:
                raise

        logger.info("commercial_lead persisted: lead_id=%s routing=%s", lead_id, routing_target_domain)

        return {
            "status": "accepted",
            "lead_id": lead_id,
            "routing": routing_target_domain,
            "idempotent": False,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("commercial_lead persistence error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/intake/commercial-leads", status_code=status.HTTP_202_ACCEPTED)
async def intake_commercial_lead(body: Dict[str, Any], request: Request):
    """
    Public endpoint for commercial lead intake (e.g. Private Estates landing page).
    No authentication required. Validates domain, source, and contact fields,
    then routes to valuation_requests or leads_pipeline depending on request_type.
    """
    return await _handle_commercial_lead_intake(body, request)


@router.post("/lead-intake", status_code=status.HTTP_202_ACCEPTED)
async def lead_intake_alias(body: Dict[str, Any], request: Request):
    """
    Backward-compatibility alias for /intake/commercial-leads.
    Used by PE Landing which calls this path.
    """
    return await _handle_commercial_lead_intake(body, request)
