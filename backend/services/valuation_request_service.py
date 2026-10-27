from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from backend.models.valuation_requests import PublicValuationRequestCreate
from backend.services.captcha_verification_service import captcha_verification_service
from backend.services.email_delivery_service import get_email_transport_summary, send_email_native
from backend.services.external_portal_email_service import build_valuation_submission_confirmation
from backend.services.neon_service import neon_service


class ValuationRequestService:
    async def create_public_request(
        self,
        org_id: str,
        payload: PublicValuationRequestCreate,
        remote_ip: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        data = payload.model_dump()
        captcha_result = captcha_verification_service.verify(
            provider=data.get("captcha_provider"),
            token=data.get("captcha_token"),
            remote_ip=remote_ip,
        )
        record = {
            **{key: value for key, value in data.items() if key != "captcha_token"},
            "org_id": org_id,
            "captcha_verified_at": now if captcha_result["verified"] else None,
            "status": "submitted",
            "created_at": now,
            "updated_at": now,
        }
        response = neon_service.client.table("valuation_requests").insert(record).execute()
        result = response.data[0]

        transport = get_email_transport_summary()
        confirmation = None
        if transport["native_email_enabled"]:
            mail = build_valuation_submission_confirmation(
                full_name=str(result.get("full_name") or ""),
                language=str(result.get("submission_language") or "es"),
            )
            delivery = send_email_native(
                to_email=str(result["email"]),
                subject=mail["subject"],
                body=mail["body"],
                html=mail.get("html"),
            )
            updated = (
                neon_service.client.table("valuation_requests")
                .update({"confirmation_email_sent_at": now, "updated_at": now})
                .eq("org_id", org_id)
                .eq("id", result["id"])
                .execute()
            )
            result = updated.data[0] if updated.data else result
            confirmation = {"transport": "smtp", "delivery": delivery}
        else:
            confirmation = {"transport": "unavailable"}
        result["confirmation_email"] = confirmation
        return result


valuation_request_service = ValuationRequestService()
