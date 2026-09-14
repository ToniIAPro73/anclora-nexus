import logging
from typing import Any, Dict, Optional
import httpx
from backend.config import settings

logger = logging.getLogger(__name__)


class IdentityProvisioningError(Exception):
    """Raised when an interaction with Anclora Identity fails."""
    pass


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
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params={"email": email}, headers=headers)
            if resp.status_code == 404:
                return None
            if resp.status_code == 200:
                data = resp.json()
                if data.get("exists") and data.get("user"):
                    return data.get("user")
                return None
            raise IdentityProvisioningError(
                f"Identity lookup failed HTTP {resp.status_code}: {resp.text}"
            )

    async def create_invitation(
        self,
        application_id: str,
        email: str,
        reviewer_id: Optional[str] = None,
        locale: str = "es",
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
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code in (200, 201):
                return resp.json()
            raise IdentityProvisioningError(
                f"Create invitation failed HTTP {resp.status_code}: {resp.text}"
            )

    async def grant_membership(
        self,
        application_id: str,
        identity_user_id: str,
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
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code in (200, 201):
                return resp.json()
            raise IdentityProvisioningError(
                f"Grant membership failed HTTP {resp.status_code}: {resp.text}"
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

        # Fallback when Identity is not configured or disabled in current environment
        if not self.is_enabled or not self.service_token:
            logger.info(
                f"Identity provisioning fallback: enabled={self.is_enabled}, has_token={bool(self.service_token)}"
            )
            return {
                "provisioning_status": "invite_ready",
                "provisioning_case": "STANDALONE_FALLBACK",
            }

        try:
            user = await self.lookup_identity(email)
            if user and user.get("id"):
                # CASO B: Existing identity user -> grant application membership
                identity_user_id = user["id"]
                membership_res = await self.grant_membership(app_id, identity_user_id)
                membership = membership_res.get("membership", {})
                return {
                    "provisioning_status": "provisioned",
                    "identity_subject_id": identity_user_id,
                    "membership_id": membership.get("id"),
                    "provisioning_case": "CASO_B",
                }
            else:
                # CASO A: New identity -> create invitation
                invitation_res = await self.create_invitation(
                    application_id=app_id,
                    email=email,
                    reviewer_id=reviewer_id,
                    locale=request.get("submission_language", "es"),
                )
                invitation = invitation_res.get("invitation", {})
                return {
                    "provisioning_status": "invite_ready",
                    "identity_invitation_id": invitation.get("id"),
                    "invite_token": invitation.get("token"),
                    "invite_expires_at": invitation.get("expiresAt"),
                    "invite_url": invitation_res.get("inviteUrl"),
                    "provisioning_case": "CASO_A",
                }
        except Exception as e:
            logger.error(f"Identity provisioning failed for request {request.get('id')}: {e}", exc_info=True)
            return {
                "provisioning_status": "failed",
                "provisioning_error": str(e),
                "provisioning_case": "ERROR",
            }


identity_provisioning_service = IdentityProvisioningService()
