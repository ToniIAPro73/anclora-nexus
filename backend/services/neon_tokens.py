"""Short-lived ES256 JWTs for the Neon Data API."""

import base64
import json
import time
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def create_neon_jwt(
    *,
    role: str,
    subject: str,
    private_key: str,
    key_id: str,
    issuer: str,
    audience: str,
    ttl_seconds: int = 900,
    now: Optional[int] = None,
) -> str:
    """Sign a minimal, short-lived ES256 JWT consumed by Neon Data API."""
    if not all((role, subject, private_key, key_id, issuer, audience)):
        raise ValueError("Neon JWT role, subject, signing key, key id, issuer, and audience are required")
    if ttl_seconds < 30 or ttl_seconds > 3600:
        raise ValueError("Neon JWT lifetime must be between 30 and 3600 seconds")

    pem = private_key.replace("\\n", "\n").encode("utf-8")
    signing_key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(signing_key, ec.EllipticCurvePrivateKey) or not isinstance(
        signing_key.curve, ec.SECP256R1
    ):
        raise ValueError("Neon JWT signing key must be an EC P-256 private key")

    issued_at = int(time.time()) if now is None else int(now)
    header: Dict[str, Any] = {"alg": "ES256", "typ": "JWT", "kid": key_id}
    payload: Dict[str, Any] = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "role": role,
        "iat": issued_at,
        "exp": issued_at + ttl_seconds,
    }
    signing_input = (
        f"{_b64url(json.dumps(header, separators=(',', ':')).encode())}."
        f"{_b64url(json.dumps(payload, separators=(',', ':')).encode())}"
    )
    der_signature = signing_key.sign(signing_input.encode("ascii"), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der_signature)
    raw_signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return f"{signing_input}.{_b64url(raw_signature)}"
