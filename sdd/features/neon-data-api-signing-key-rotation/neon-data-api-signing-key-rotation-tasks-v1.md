# Neon Data API signing-key rotation — Tasks v1

- [x] Add the public JWKS builder and validate additional P-256 JWKs.
- [x] Wire the builder into `/api/neon-jwks` with sanitized fail-closed responses.
- [x] Add targeted tests for one key, two keys, duplicate IDs, private fields, and malformed input.
- [x] Document `NEON_JWT_ADDITIONAL_PUBLIC_KEYS` as public configuration.
- [x] Run targeted tests, frontend typecheck, and diff checks.
- [x] Separate frontend user-token verification from Render's Neon service-token signer.
- [x] Add focused backend coverage for distinct signing and verification keys.
- [x] Run the focused backend auth batch (`test_neon_tokens.py`, `test_identity_provisioning.py`: 15 passed) and frontend JWKS batch (7 passed); frontend typecheck and diff checks pass.
- [ ] Review the updated development diff with Toni before production configuration.
- [ ] After code validation, stage production variables without triggering deployment; verify key names and scopes without reading secret values.
- [ ] Promote only after variables are staged; let Render deploy the revision that supports distinct signer and verifier keys.
