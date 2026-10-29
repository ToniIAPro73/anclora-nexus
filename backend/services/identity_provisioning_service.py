import json
import logging
import re
from typing import Any, Dict, Optional
import httpx
from backend.config import settings

logger = logging.getLogger(__name__)
MAX_IDENTITY_ERROR_BODY_CHARS = 2048
SENSITIVE_RESPONSE_KEY = re.compile(
    r"(?:access[_-]?token|refresh[_-]?token|id[_-]?token|client[_-]?secret|"
    r"secret|password|authorization|cookie|api[_-]?key|private[_-]?key|"
    r"invite[_-]?(?:token|url)|activation[_-]?url|session|state)",
    re.IGNORECASE,
)
SENSITIVE_RESPONSE_VALUE = re.compile(
    r"(?i)(\b(?:authorization|access[_-]?token|refresh[_-]?token|id[_-]?token|"
    r"client[_-]?secret|secret|password|api[_-]?key|private[_-]?key|"
    r"invite[_-]?(?:token|url)|activation[_-]?url|session|state)\b\s*[\"']?\s*[:=]\s*[\"']?)"
    r"([^\"'\s,;&}]+)"
)
BEARER_CREDENTIAL = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*")
JWT_CREDENTIAL = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}(?![A-Za-z0-9_-])")
SENSITIVE_QUERY_VALUE = re.compile(r"(?i)([?&](?:token|code|state|session)=)[^&\s]+")
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]+")
EMAIL_ADDRESS = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)


def _redact_response_text(value: str) -> str:
    """Redact credential-like values and normalize text before logging/persistence."""
    value = BEARER_CREDENTIAL.sub("Bearer [REDACTED]", value)
    value = JWT_CREDENTIAL.sub("[REDACTED_JWT]", value)
    value = SENSITIVE_QUERY_VALUE.sub(r"\1[REDACTED]", value)
    value = SENSITIVE_RESPONSE_VALUE.sub(r"\1[REDACTED]", value)
    value = EMAIL_ADDRESS.sub("[REDACTED_EMAIL]", value)
    return CONTROL_CHARACTERS.sub(" ", value).strip()


def _redact_response_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if SENSITIVE_RESPONSE_KEY.search(str(key)) else _redact_response_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_response_value(item) for item in value]
    if isinstance(value, str):
        return _redact_response_text(value)
    return value


def _safe_identity_response(response: httpx.Response) -> Dict[str, str]:
    """Return a bounded, credential-redacted representation of an Identity error body."""
    content_type = response.headers.get("content-type", "").split(";", 1)[0][:100]
    try:
        payload = response.json()
    except (ValueError, json.JSONDecodeError):
        body = _redact_response_text(response.text)
    else:
        body = json.dumps(
            _redact_response_value(payload),
            ensure_ascii=False,
            separators=(",", ":"),
        )

    if len(body) > MAX_IDENTITY_ERROR_BODY_CHARS:
        body = body[:MAX_IDENTITY_ERROR_BODY_CHARS] + "…[truncated]"
    return {"content_type": content_type or "unknown", "body": body or "<empty>"}


class IdentityProvisioningError(Exception):
    """Raised when Anclora Identity returns a non-success HTTP response."""

    def __init__(self, operation: str, status_code: int, response: Dict[str, str]):
        self.operation = operation
        self.status_code = status_code
        self.response = response
        super().__init__(f"{operation} failed HTTP {status_code}: {response['body']}")

    def diagnostic(self) -> Dict[str, Any]:
        return {
            "http_status": self.status_code,
            "response": self.response,
        }


class IdentityProvisioningService:
    """
    Client service for Anclora Identity provisioning.
    Nexus calls Anclora Identity upon approving an Access Request:
    - CASO A: New identity -> Create invitation (invitation token & URL)
    - CASO B: Existing identity -> Grant direct application membership
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        service_token: Optional[str] = None,
        enabled: Optional[bool] = None,
    ):
        self._base_url = base_url
        self._service_token = service_token
        self._enabled = enabled

    @property
    def base_url(self) -> str:
        return (self._base_url or getattr(settings, "IDENTITY_SERVICE_URL", "http://localhost:4001")).rstrip("/")

    @property
    def service_token(self) -> str:
        return self._service_token or getattr(settings, "IDENTITY_SERVICE_TOKEN", "") or ""

    @property
    def is_enabled(self) -> bool:
        if self._enabled is not None:
            return self._enabled
        return getattr(settings, "IDENTITY_PROVISIONING_ENABLED", True)

    def _normalize_app_id(self, product: str) -> str:
        p = str(product).lower().strip()
        if p in ("synergi", "synergi_app"):
            return "synergi"
        if p in ("data_lab", "data-lab", "data_lab_app"):
            return "data-lab"
        if p in ("guesthub", "syncxml", "syncxml_landing", "guesthub_app"):
            return "guesthub"
        return p

    async def lookup_identity(self, email: str) -> Optional[Dict[str, Any]]:
        """Look up identity user in Anclora Identity by email."""
        url = f"{self.base_url}/api/v1/admin/identities/lookup"
        headers = {
            "Authorization": f"Bearer {self.service_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params={"email": email}, headers=headers)
            if resp.status_code == 404:
                return None
            if resp.status_code == 200:
                data = resp.json()
                if data.get("exists") and data.get("user"):
                    return data.get("user")
                return None
            raise IdentityProvisioningError(
                "Identity lookup",
                resp.status_code,
                _safe_identity_response(resp),
            )

    async def create_invitation(
        self,
        application_id: str,
        email: str,
        reviewer_id: Optional[str] = None,
        locale: str = "es",
        application_role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """CASO A: Create invitation for new identity in target application."""
        url = f"{self.base_url}/api/v1/admin/apps/{application_id}/invitations"
        headers = {
            "Authorization": f"Bearer {self.service_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "email": email,
            "invitedByIdentityUserId": reviewer_id,
            "locale": locale,
        }
        if application_role:
            payload["applicationRole"] = application_role
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code in (200, 201):
                return resp.json()
            raise IdentityProvisioningError(
                "Create invitation",
                resp.status_code,
                _safe_identity_response(resp),
            )

    async def grant_membership(
        self,
        application_id: str,
        identity_user_id: str,
        application_role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """CASO B: Grant direct membership in target application for existing identity."""
        url = f"{self.base_url}/api/v1/admin/apps/{application_id}/memberships"
        headers = {
            "Authorization": f"Bearer {self.service_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "identityUserId": identity_user_id,
        }
        if application_role:
            payload["applicationRole"] = application_role
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code in (200, 201):
                return resp.json()
            raise IdentityProvisioningError(
                "Grant membership",
                resp.status_code,
                _safe_identity_response(resp),
            )

    async def provision_approved_request(
        self,
        request: Dict[str, Any],
        reviewer_id: str,
    ) -> Dict[str, Any]:
        """
        Executes canonical provisioning logic for an approved request:
        1. Check if Identity is configured/enabled.
        2. Lookup identity by email.
        3. CASO B if exists -> grant direct membership.
        4. CASO A if not exists -> create invitation.
        """
        email = request.get("email")
        product = request.get("product")
        app_id = self._normalize_app_id(product)
        metadata = request.get("metadata") if isinstance(request.get("metadata"), dict) else {}
        qa_scope = metadata.get("qa_scope")
        qa_application_role = "qa" if qa_scope == app_id and app_id in {"guesthub", "data-lab"} else None

        # Fail-closed: when Identity is not configured or disabled,
        # never simulate invitations or memberships. Set status to 'pending' with clear error.
        if not self.is_enabled or not self.service_token:
            reason = "Identity provisioning is disabled" if not self.is_enabled else "Missing IDENTITY_SERVICE_TOKEN"
            logger.warning(
                f"Identity provisioning fail-closed: {reason} (enabled={self.is_enabled}, has_token={bool(self.service_token)})"
            )
            return {
                "provisioning_status": "pending",
                "provisioning_error": reason,
                "provisioning_case": "NOT_CONFIGURED",
                "identity_subject_id": None,
                "identity_invitation_id": None,
                "membership_id": None,
            }

        try:
            user = await self.lookup_identity(email)
            if user and user.get("id"):
                # CASO B: Existing identity user -> grant application membership
                identity_user_id = user["id"]
                membership_res = (
                    await self.grant_membership(app_id, identity_user_id, application_role=qa_application_role)
                    if qa_application_role
                    else await self.grant_membership(app_id, identity_user_id)
                )
                membership_id = membership_res.get("membershipId") or membership_res.get("membership", {}).get("id")
                return {
                    "provisioning_status": "provisioned",
                    "identity_subject_id": identity_user_id,
                    "membership_id": membership_id,
                    "provisioning_case": "CASO_B",
                }
            else:
                # CASO A: New identity -> create invitation
                invitation_params = {
                    "application_id": app_id,
                    "email": email,
                    "reviewer_id": reviewer_id,
                    "locale": request.get("submission_language", "es"),
                }
                if qa_application_role:
                    invitation_params["application_role"] = qa_application_role
                invitation_res = await self.create_invitation(**invitation_params)
                invitation = invitation_res.get("invitation", {})
                invitation_id = invitation_res.get("invitationId") or invitation.get("id")
                return {
                    "provisioning_status": "invite_ready",
                    "identity_invitation_id": invitation_id,
                    "invite_token": invitation_res.get("inviteToken") or invitation.get("token"),
                    "invite_expires_at": invitation_res.get("expiresAt") or invitation.get("expiresAt"),
                    "invite_url": invitation_res.get("inviteUrl"),
                    "provisioning_case": "CASO_A",
                }
        except Exception as e:
            error_type = type(e).__name__
            identity_error = e.diagnostic() if isinstance(e, IdentityProvisioningError) else None
            provisioning_error = (
                f"Identity {e.operation} failed HTTP {e.status_code}: {e.response['body']}"
                if isinstance(e, IdentityProvisioningError)
                else f"Identity provisioning failed ({error_type})"
            )
            logger.error(
                "Identity provisioning failed: %s",
                provisioning_error,
                extra={
                    "request_id": request.get("id"),
                    "error_type": error_type,
                    "identity_http_status": identity_error.get("http_status") if identity_error else None,
                },
            )
            return {
                "provisioning_status": "failed",
                "provisioning_error": provisioning_error,
                "identity_error": identity_error,
                "provisioning_case": "ERROR",
                "identity_subject_id": None,
                "identity_invitation_id": None,
                "membership_id": None,
            }


identity_provisioning_service = IdentityProvisioningService()
