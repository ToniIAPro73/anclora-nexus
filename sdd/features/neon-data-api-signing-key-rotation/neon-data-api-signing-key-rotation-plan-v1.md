# Neon Data API signing-key rotation — Plan v1

1. Add a pure JWKS builder that preserves the current primary-key behavior and validates optional additional public JWKs.
2. Keep the HTTP route fail closed and sanitize errors.
3. Add focused unit coverage for primary-only, dual-key, and invalid-key cases.
4. Document the public-only configuration variable and the production rollout sequence.
5. Run focused tests and TypeScript validation. Do not generate or configure production keys in this implementation step.
