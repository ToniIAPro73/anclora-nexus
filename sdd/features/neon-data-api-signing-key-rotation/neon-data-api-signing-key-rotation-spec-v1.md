# Neon Data API signing-key rotation — Specification v1

## Status

Draft for development validation. Production key configuration and promotion are out of scope until Toni validates this change.

## Problem

The Nexus Render backend needs a P-256 ES256 signing key for Neon Data API requests. The existing Vercel private key is a production secret and cannot be recovered. The backend also verifies user access tokens minted by the frontend, so using a different Neon signer as the user-token verifier would reject valid Vercel-issued sessions.

## Goal

Keep the two cryptographic roles separate: the frontend publishes its signer and additional public Neon signers through one JWKS document; Render uses its own private key for Neon service tokens and the frontend's public key plus `kid` to verify user access tokens. This configuration remains portable when the frontend moves from Vercel to Cloudflare.

## Requirements

1. Keep the existing `NEON_JWT_PRIVATE_KEY` and `NEON_JWT_KEY_ID` behavior as the primary JWKS key.
2. Accept optional `NEON_JWT_ADDITIONAL_PUBLIC_KEYS` as a JSON array of public P-256 JWKs. Every additional key must have a unique, non-empty `kid`.
3. Reject malformed keys, non-P-256 keys, duplicate key IDs, and JWKs containing private key material. Do not return partial JWKS data on invalid configuration.
4. Normalize published keys to public JWK fields with `use=sig` and `alg=ES256`; never publish private fields.
5. Keep the JWKS cache policy bounded and return sanitized configuration errors.
6. Render user-token verification can use `NEXUS_ACCESS_JWT_PUBLIC_KEY` and `NEXUS_ACCESS_JWT_KEY_ID`, independently of the private key and `kid` used to sign Neon service tokens. If the public verifier is absent, preserve the legacy same-key behavior.
7. Production key generation, Render secret writes, Vercel/Cloudflare public configuration, Neon mutations, and deployment are separate gated operations after development validation.

## Acceptance criteria

- With only the existing signing key configured, the endpoint returns the same single-key JWKS shape.
- With an additional public key, the endpoint returns both keys and no private key material.
- Invalid or conflicting additional keys fail closed with HTTP 503.
- A user token signed by the frontend remains valid when Render's Neon service signer is different, using only the frontend public verification key.
- No signing secret is added to source, documentation, logs, or test fixtures.
- Nexus remains on `development`; changes stay uncommitted until Toni validates them.
