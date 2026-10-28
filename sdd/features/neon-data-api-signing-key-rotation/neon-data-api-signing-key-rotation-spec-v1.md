# Neon Data API signing-key rotation — Specification v1

## Status

Draft for development validation. Production key configuration and promotion are out of scope until Toni validates this change.

## Problem

The Nexus Render backend needs its own P-256 ES256 signing key for Neon Data API requests. The existing Vercel private key is stored as a production secret and cannot be recovered. Replacing it would interrupt Vercel signers unless Neon continues to trust the existing public key.

## Goal

Let Nexus publish the current Vercel public key and additional public signing keys in one JWKS document. Render can then use a distinct private key while Vercel keeps its current key.

## Requirements

1. Keep the existing `NEON_JWT_PRIVATE_KEY` and `NEON_JWT_KEY_ID` behavior as the primary JWKS key.
2. Accept optional `NEON_JWT_ADDITIONAL_PUBLIC_KEYS` as a JSON array of public P-256 JWKs. Every additional key must have a unique, non-empty `kid`.
3. Reject malformed keys, non-P-256 keys, duplicate key IDs, and JWKs containing private key material. Do not return partial JWKS data on invalid configuration.
4. Normalize published keys to public JWK fields with `use=sig` and `alg=ES256`; never publish private fields.
5. Keep the JWKS cache policy bounded and return sanitized configuration errors.
6. Production key generation, Render secret writes, Neon mutations, and deployment are separate gated operations after development validation.

## Acceptance criteria

- With only the existing signing key configured, the endpoint returns the same single-key JWKS shape.
- With an additional public key, the endpoint returns both keys and no private key material.
- Invalid or conflicting additional keys fail closed with HTTP 503.
- No signing secret is added to source, documentation, logs, or test fixtures.
- Nexus remains on `development`; changes stay uncommitted until Toni validates them.
