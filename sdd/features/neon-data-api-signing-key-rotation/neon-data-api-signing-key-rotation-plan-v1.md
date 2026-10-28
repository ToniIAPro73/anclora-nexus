# Neon Data API signing-key rotation — Plan v1

1. Add a pure JWKS builder that preserves the current primary-key behavior and validates optional additional public JWKs.
2. Keep the HTTP route fail closed and sanitize errors.
3. Separate backend user-token verification (frontend public key and `kid`) from Neon service-token signing (Render private key and `kid`), retaining the legacy same-key fallback.
4. Add focused unit coverage for primary-only, dual-key, invalid-key, and independent backend signing/verifying keys.
5. Document the public-only key variables and provider-portable rollout sequence, including the planned Cloudflare move.
6. Run focused backend/frontend validation. Do not generate or configure production keys until this implementation is validated.
7. Before the governed promotion, stage the Render URL, separate service signer, and frontend public verifier with a no-deploy save; stage the additional public JWK in the current frontend host's production Config. Do not trigger Render's production branch while it still contains the legacy verifier implementation.
8. Promote the exact reviewed source so the frontend JWKS publisher and Render verifier split arrive together; let the configured Render production branch deploy that revision. During the Cloudflare cutover, transfer the same variable roles to Cloudflare bindings/secrets and keep the JWKS URL stable.
