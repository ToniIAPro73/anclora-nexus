# Nexus authentication migration to Anclora Identity

## Rollout boundary

The integration is opt-in with `ANCLORA_IDENTITY_ENABLED` and
`NEXT_PUBLIC_ANCLORA_IDENTITY_ENABLED`. They must have the same value. Keep
both unset/false in Production during the Preview pilot; Identity is fail
closed when enabled and does not fall back to Supabase Auth.

Nexus uses OIDC Authorization Code + PKCE, a signed HttpOnly application
session, and the existing Neon user profile and organization membership as
the source of Nexus authorization. The Identity subject is not assumed to be
the legacy Nexus user UUID: the callback requires a verified email and maps it
to exactly one existing Nexus profile before creating a session. That keeps
existing record ownership and Neon RLS subjects intact.

Nexus API bearer tokens are short-lived ES256 JWTs signed with the existing
Nexus/Neon key. The Python API validates issuer, audience, role, key ID,
signature, expiry, and UUID subject. Existing Supabase tokens remain accepted
by the API during the staged rollout so the current Production deployment is
not cut over as part of Preview work.

## Preview configuration

Set these only in the Nexus Vercel **Preview** environment, scoped to the
`development` branch:

```text
ANCLORA_IDENTITY_ENABLED=true
NEXT_PUBLIC_ANCLORA_IDENTITY_ENABLED=true
ANCLORA_IDENTITY_ISSUER_URL=<Anclora Identity development Preview issuer URL>
ANCLORA_IDENTITY_CLIENT_ID=anclora-nexus
ANCLORA_IDENTITY_CLIENT_SECRET=<per-environment OIDC client secret>
ANCLORA_IDENTITY_REDIRECT_URI=https://<Nexus development Preview hostname>/api/auth/anclora-identity/callback
ANCLORA_IDENTITY_SESSION_SECRET=<independent random secret, 32+ bytes>
```

On the Anclora Identity **Preview** deployment, set:

```text
NEXUS_CLIENT_SECRET=<same OIDC client secret as Nexus Preview>
NEXUS_REDIRECT_URIS=https://<Nexus development Preview hostname>/api/auth/anclora-identity/callback
```

Configure a separate client secret and callback allowlist for Production only
after Preview passes and the production cutover is reviewed. Never reuse the
session-signing secret as the OIDC client secret.

Nexus Preview also needs the existing Neon Data API URL, the Nexus P-256
`NEON_JWT_PRIVATE_KEY` and `NEON_JWT_KEY_ID`, and the corresponding Neon Data
API JWKS configuration. Those values must match the key already used by the
Nexus backend and the Data API; do not generate a replacement key as part of
this OIDC change.

## QA data

Use the persistent Identity account `qa.nexus@anclora.local`. It needs an
active Identity application membership for `anclora-nexus`, plus an isolated
Nexus QA organization, `auth.users` UUID stub (the imported schema has profile
foreign keys to it), profile, and active owner membership in the existing
Nexus Neon Preview/security-review branch. Do not create these rows in the
canonical `main` branch. Do not delete the persistent QA identity afterward.

## Known scope limits before Production cutover

- The central Identity service currently provides its configured password
  login and MFA flow. Nexus Google/GitHub buttons must stay disabled until
  those providers are available and configured centrally.
- Account creation and password recovery are Identity operations. Nexus no
  longer uses its legacy signup/reset endpoints when the feature flag is on;
  application invitations and self-service account recovery need separate
  product UX before the production cutover.
- Production still uses its current Supabase Auth route until Toni reviews the
  Preview flow and explicitly approves a later production migration.
- The protected `.anclora/PRODUCTION_RUNTIME.md` still describes the prior
  Nexus auth/runtime state and should be reconciled after the Preview design
  is accepted.

## Validation sequence

1. Deploy Nexus and Identity from the reviewed `development` commits to Preview.
2. Verify the QA account can authenticate through Identity, then access Nexus
   only when both Identity app membership and the Nexus QA organization
   membership are active.
3. Verify a non-member gets a 403 at the OIDC callback, logout clears the
   Nexus session, Neon reads/writes use the mapped Nexus UUID, and backend
   bearer validation accepts valid tokens while rejecting modified/expired
   tokens.
4. Keep Production unchanged until Toni reviews the exact Preview SHAs.
