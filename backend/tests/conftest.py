import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Deterministic test env defaults. Several test modules set these via
# os.environ.setdefault at import time, but module import order is not
# guaranteed, so the backend.config Settings singleton must see them here,
# before any test module (or backend module) is imported. Explicitly-set
# real env vars always win.
os.environ.setdefault("NEON_DATA_API_URL", "https://test.neon.invalid/rest/v1")
os.environ.setdefault("NEON_JWT_KEY_ID", "test-key-id")
if not os.environ.get("NEON_JWT_PRIVATE_KEY"):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    _test_private_key = ec.generate_private_key(ec.SECP256R1())
    os.environ["NEON_JWT_PRIVATE_KEY"] = _test_private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
os.environ.setdefault("NEXUS_INTERNAL_API_KEY", "internal-key-test")
os.environ.setdefault("NEXUS_DOCUMENT_ENCRYPTION_KEY", "00" * 32)
os.environ.setdefault("DOCUSEAL_API_KEY", "docuseal-api-key")
os.environ.setdefault("DOCUSEAL_WEBHOOK_SECRET", "webhook-secret")
