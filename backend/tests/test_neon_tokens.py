import base64
import json
import unittest

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from backend.services.neon_tokens import create_neon_jwt
from backend.api.deps import verify_nexus_access_token
from backend.config import settings


def _decode_part(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class NeonTokenTests(unittest.TestCase):
    @staticmethod
    def _pem(private_key):
        return private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()

    def test_create_neon_jwt_uses_es256_and_expected_scope(self):
        private_key = ec.generate_private_key(ec.SECP256R1())
        token = create_neon_jwt(
            role="authenticated",
            subject="00000000-0000-4000-8000-000000000001",
            private_key=self._pem(private_key),
            key_id="nexus-test-key",
            issuer="anclora-nexus-test",
            audience="authenticated",
            ttl_seconds=120,
            now=1000,
        )
        encoded_header, encoded_claims, encoded_signature = token.split(".")
        header = json.loads(_decode_part(encoded_header))
        claims = json.loads(_decode_part(encoded_claims))
        signature = _decode_part(encoded_signature)
        r = int.from_bytes(signature[:32], "big")
        s = int.from_bytes(signature[32:], "big")

        self.assertEqual(header, {"alg": "ES256", "typ": "JWT", "kid": "nexus-test-key"})
        self.assertEqual(claims, {
            "iss": "anclora-nexus-test",
            "aud": "authenticated",
            "sub": "00000000-0000-4000-8000-000000000001",
            "role": "authenticated",
            "iat": 1000,
            "exp": 1120,
        })
        private_key.public_key().verify(
            encode_dss_signature(r, s),
            f"{encoded_header}.{encoded_claims}".encode("ascii"),
            ec.ECDSA(hashes.SHA256()),
        )

    def test_create_neon_jwt_rejects_non_p256_key(self):
        private_key = ec.generate_private_key(ec.SECP384R1())
        with self.assertRaisesRegex(ValueError, "P-256"):
            create_neon_jwt(
                role="service_role",
                subject="backend",
                private_key=self._pem(private_key),
                key_id="nexus-test-key",
                issuer="anclora-nexus-test",
                audience="authenticated",
            )

    def test_create_neon_jwt_rejects_long_lifetime(self):
        private_key = ec.generate_private_key(ec.SECP256R1())
        with self.assertRaisesRegex(ValueError, "between 30 and 3600"):
            create_neon_jwt(
                role="service_role",
                subject="backend",
                private_key=self._pem(private_key),
                key_id="nexus-test-key",
                issuer="anclora-nexus-test",
                audience="authenticated",
                ttl_seconds=3601,
            )

    def test_backend_verifies_signed_nexus_access_token(self):
        private_key = ec.generate_private_key(ec.SECP256R1())
        previous = (settings.NEON_JWT_PRIVATE_KEY, settings.NEON_JWT_KEY_ID, settings.NEON_JWT_ISSUER, settings.NEON_JWT_AUDIENCE)
        try:
            settings.NEON_JWT_PRIVATE_KEY = self._pem(private_key)
            settings.NEON_JWT_KEY_ID = 'nexus-test-key'
            settings.NEON_JWT_ISSUER = 'anclora-nexus-test'
            settings.NEON_JWT_AUDIENCE = 'authenticated'
            token = create_neon_jwt(
                role='authenticated', subject='00000000-0000-4000-8000-000000000001',
                private_key=self._pem(private_key), key_id='nexus-test-key',
                issuer='anclora-nexus-test', audience='authenticated', ttl_seconds=120,
            )
            user = verify_nexus_access_token(token)
            self.assertEqual(user.id, '00000000-0000-4000-8000-000000000001')
            header, claims, signature = token.split('.')
            tampered_signature = ('A' if signature[0] != 'A' else 'B') + signature[1:]
            self.assertIsNone(verify_nexus_access_token(f'{header}.{claims}.{tampered_signature}'))
        finally:
            settings.NEON_JWT_PRIVATE_KEY, settings.NEON_JWT_KEY_ID, settings.NEON_JWT_ISSUER, settings.NEON_JWT_AUDIENCE = previous
