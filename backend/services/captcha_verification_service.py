from __future__ import annotations

import json
from typing import Any, Dict, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from backend.config import settings


class CaptchaVerificationError(RuntimeError):
    pass


class CaptchaVerificationService:
    def _provider_enabled(self, provider: str | None) -> bool:
        p = (provider or "").strip().lower()
        return p in ["recaptcha", "turnstile"]

    def verify(self, *, provider: Optional[str], token: Optional[str], remote_ip: Optional[str] = None) -> Dict[str, Any]:
        if not self._provider_enabled(provider):
            return {"provider": "none", "verified": False, "required": False}

        p = (provider or "").strip().lower()

        if p == "recaptcha":
            if not settings.RECAPTCHA_SECRET_KEY:
                raise CaptchaVerificationError("reCAPTCHA secret key is not configured")
            verify_url = settings.RECAPTCHA_VERIFY_URL
            secret = settings.RECAPTCHA_SECRET_KEY
        else:  # turnstile
            if not settings.TURNSTILE_SECRET_KEY:
                if settings.ENVIRONMENT == "development" or settings.APP_ENV == "development":
                    return {"provider": "turnstile", "verified": True, "required": False, "hostname": "dev.localhost"}
                raise CaptchaVerificationError("Turnstile secret key is not configured")
            verify_url = settings.TURNSTILE_VERIFY_URL
            secret = settings.TURNSTILE_SECRET_KEY

        if not token:
            raise CaptchaVerificationError(f"Missing {p} token")

        payload = {
            "secret": secret,
            "response": token,
        }
        if remote_ip:
            payload["remoteip"] = remote_ip

        request = Request(
            verify_url,
            data=urlencode(payload).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

        with urlopen(request, timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))

        if not bool(body.get("success")):
            raise CaptchaVerificationError(f"{p} verification failed")

        return {
            "provider": p,
            "verified": True,
            "required": True,
            "score": body.get("score"),
            "hostname": body.get("hostname"),
        }


captcha_verification_service = CaptchaVerificationService()
