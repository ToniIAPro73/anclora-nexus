from typing import Optional
from uuid import UUID
from fastapi import Header, HTTPException, Depends
from backend.config import settings
from backend.api.middleware import verify_org_membership
from backend.models.membership import UserRole
from backend.services.supabase_service import supabase_service

async def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Simple Supabase Auth dependency. 
    In v0, we assume the frontend sends a valid Supabase JWT.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Dev bypass when running in development environment
    token = authorization.split(" ")[1] if " " in authorization else authorization
    if settings.ENVIRONMENT == "development" or settings.APP_ENV == "development":
        if token in ["dev-admin-token", settings.IDENTITY_SERVICE_TOKEN, settings.INTERNAL_AUDIT_SECRET]:
            class DevUser:
                id = "00000000-0000-0000-0000-000000000001"
                email = "admin@anclora.com"
            return DevUser()

    try:
        user_response = supabase_service.client.auth.get_user(token)
        if not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid session")
        return user_response.user
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Auth error: {str(e)}")

async def get_org_id(user = Depends(get_current_user)):
    """
    Returns the authenticated user's organization id from user_profiles.
    Legacy fallback is allowed only when explicitly enabled in config.
    """
    try:
        response = (
            supabase_service.client.table("user_profiles")
            .select("org_id")
            .eq("id", user.id)
            .single()
            .execute()
        )
        profile = response.data or {}
        if profile.get("org_id"):
            return profile["org_id"]
    except Exception:
        pass
    if (
        (settings.ENVIRONMENT == "development" or settings.APP_ENV == "development")
        or (settings.ALLOW_LEGACY_ORG_FALLBACK and settings.LEGACY_SINGLE_TENANT_ORG_ID)
    ):
        return settings.LEGACY_SINGLE_TENANT_ORG_ID or settings.PUBLIC_CTA_ORG_ID
    raise HTTPException(status_code=403, detail="ORG_SCOPE_NOT_RESOLVED")

async def require_access_request_reviewer(
    org_id: str = Depends(get_org_id),
    current_user = Depends(get_current_user),
):
    """
    Requires an active owner/manager membership for access request decisions.
    """
    if (settings.ENVIRONMENT == "development" or settings.APP_ENV == "development") and str(current_user.id) == "00000000-0000-0000-0000-000000000001":
        return current_user

    try:
        parsed_org_id = UUID(str(org_id))
        parsed_user_id = UUID(str(current_user.id))
    except Exception:
        raise HTTPException(status_code=403, detail="ACCESS_REQUEST_REVIEW_FORBIDDEN")

    await verify_org_membership(
        parsed_user_id,
        parsed_org_id,
        required_role=UserRole.MANAGER,
    )
    return current_user

async def check_budget_hard_stop(org_id: str = Depends(get_org_id)):
    """
    Dependency that blocks the request if the organization has reached hard-stop threshold.
    """
    from backend.services.finops import finops_service
    
    status = await finops_service.get_budget_status(org_id)
    if status.status == "hard_stop":
        raise HTTPException(
            status_code=402, 
            detail="Monthly budget exceeded. Critical operations only (402 Payment Required)."
        )
    return status
