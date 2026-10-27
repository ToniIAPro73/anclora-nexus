import base64
import json
import time
from types import SimpleNamespace
from typing import Optional
from uuid import UUID
from fastapi import Header, HTTPException, Depends
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from backend.config import settings
from backend.api.middleware import verify_org_membership
from backend.models.membership import UserRole
from backend.services.neon_service import neon_service


def _decode_b64url(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def verify_nexus_access_token(token: str):
    """Verify short-lived ES256 access JWTs minted by the Nexus frontend."""
    try:
        encoded_header, encoded_claims, encoded_signature = token.split(".")
        header = json.loads(_decode_b64url(encoded_header))
        claims = json.loads(_decode_b64url(encoded_claims))
        if header.get("alg") != "ES256" or header.get("kid") != settings.NEON_JWT_KEY_ID:
            return None
        pem = (settings.NEON_JWT_PRIVATE_KEY or "").replace("\\n", "\n")
        if not pem:
            return None
        private_key = serialization.load_pem_private_key(pem.encode(), password=None)
        if not isinstance(private_key, ec.EllipticCurvePrivateKey) or not isinstance(private_key.curve, ec.SECP256R1):
            return None
        signature = _decode_b64url(encoded_signature)
        if len(signature) != 64:
            return None
        der_signature = encode_dss_signature(int.from_bytes(signature[:32], "big"), int.from_bytes(signature[32:], "big"))
        private_key.public_key().verify(der_signature, f"{encoded_header}.{encoded_claims}".encode("ascii"), ec.ECDSA(hashes.SHA256()))
        now = int(time.time())
        audience = claims.get("aud")
        if isinstance(audience, list):
            valid_audience = settings.NEON_JWT_AUDIENCE in audience
        else:
            valid_audience = audience == settings.NEON_JWT_AUDIENCE
        if (
            claims.get("iss") != settings.NEON_JWT_ISSUER
            or not valid_audience
            or claims.get("role") != "authenticated"
            or not isinstance(claims.get("sub"), str)
            or int(claims.get("exp", 0)) <= now
            or int(claims.get("iat", now + 61)) > now + 60
            or int(claims.get("exp", 0)) - int(claims.get("iat", 0)) > 3600
        ):
            return None
        UUID(claims["sub"])
        return SimpleNamespace(id=claims["sub"], email=None, user_metadata={})
    except (ValueError, TypeError, KeyError, InvalidSignature, json.JSONDecodeError):
        return None

async def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Accept only a Nexus short-lived ES256 access token issued after Identity OIDC.
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

    nexus_user = verify_nexus_access_token(token)
    if nexus_user:
        return nexus_user

    raise HTTPException(status_code=401, detail="Invalid Anclora Identity access token")

async def get_org_id(user = Depends(get_current_user)):
    """
    Returns the authenticated user's organization id from user_profiles.
    Legacy fallback is allowed only when explicitly enabled in config.
    """
    try:
        response = (
            neon_service.client.table("user_profiles")
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
