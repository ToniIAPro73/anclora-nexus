# Neon Data API signing-key rotation — Tasks v1

- [x] Add the public JWKS builder and validate additional P-256 JWKs.
- [x] Wire the builder into `/api/neon-jwks` with sanitized fail-closed responses.
- [x] Add targeted tests for one key, two keys, duplicate IDs, private fields, and malformed input.
- [x] Document `NEON_JWT_ADDITIONAL_PUBLIC_KEYS` as public configuration.
- [x] Run targeted tests, frontend typecheck, and diff checks.
- [ ] Present the development changes to Toni; defer secret generation, provider configuration, commit, push, and promotion until review.
