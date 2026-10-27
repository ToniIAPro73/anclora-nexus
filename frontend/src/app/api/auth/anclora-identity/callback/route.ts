import { NextResponse } from 'next/server'
import { isAncloraIdentityEnabled, getAncloraIdentityConfig } from '@/lib/anclora-identity/env'
import { hasNexusApplicationAccess, type AncloraIdentityClaims } from '@/lib/anclora-identity/authorization'
import { authorizationCodeGrant, fetchUserInfo, getAncloraIdentityOidcConfig } from '@/lib/anclora-identity/oidcClient'
import { consumeOidcState, createNexusIdentitySession } from '@/lib/anclora-identity/session'
import { createNeonDataClient } from '@/lib/neon-data-server'

export const runtime = 'nodejs'

export async function GET(request: Request) {
  if (!isAncloraIdentityEnabled()) return NextResponse.json({ error: 'ANCLORA_IDENTITY_DISABLED' }, { status: 404 })
  const stateCookie = await consumeOidcState()
  if (!stateCookie) return NextResponse.json({ error: 'INVALID_OIDC_STATE' }, { status: 400 })

  const { redirectUri } = getAncloraIdentityConfig()
  const oidc = await getAncloraIdentityOidcConfig()
  const callbackUrl = new URL(redirectUri)
  new URL(request.url).searchParams.forEach((value, key) => callbackUrl.searchParams.set(key, value))

  let tokens
  try {
    tokens = await authorizationCodeGrant(oidc, callbackUrl, {
      pkceCodeVerifier: stateCookie.codeVerifier,
      expectedState: stateCookie.state,
    })
  } catch {
    return NextResponse.json({ error: 'TOKEN_EXCHANGE_FAILED' }, { status: 400 })
  }

  const idClaims = tokens.claims() as unknown as AncloraIdentityClaims | undefined
  if (!idClaims?.sub) return NextResponse.json({ error: 'INVALID_ID_TOKEN' }, { status: 400 })
  let userInfo: Partial<AncloraIdentityClaims> = {}
  if (tokens.access_token) {
    try { userInfo = await fetchUserInfo(oidc, tokens.access_token, idClaims.sub) as unknown as Partial<AncloraIdentityClaims> } catch { /* ID token claims remain authoritative. */ }
  }
  const claims = { ...idClaims, ...userInfo }
  if (claims.email_verified !== true || !claims.email || !hasNexusApplicationAccess(claims)) {
    return NextResponse.json({ error: 'NEXUS_ACCESS_DENIED' }, { status: 403 })
  }

  try {
    // Identity subjects are not Nexus's historical Postgres IDs. Resolve the
    // verified Identity email to the existing Nexus profile before issuing a
    // Neon JWT, preserving ownership and RLS for existing Nexus records.
    const admin = createNeonDataClient('service_role', 'nexus-identity-login')
    const { data: profile, error: profileError } = await admin
      .from('user_profiles')
      .select('id,email,full_name,avatar_url')
      .eq('email', claims.email.trim().toLowerCase())
      .maybeSingle()
    if (profileError || !profile) return NextResponse.json({ error: 'NEXUS_PROFILE_NOT_PROVISIONED' }, { status: 403 })

    const { data: memberships, error: membershipError } = await admin
      .from('organization_members')
      .select('org_id,role')
      .eq('user_id', profile.id)
      .eq('status', 'active')
      .order('updated_at', { ascending: false })
      .limit(1)
    const membership = Array.isArray(memberships) ? memberships[0] : null
    if (membershipError || !membership) return NextResponse.json({ error: 'NEXUS_ORGANIZATION_MEMBERSHIP_REQUIRED' }, { status: 403 })

    await createNexusIdentitySession({
      sub: claims.sub,
      userId: String(profile.id),
      email: String(profile.email),
      name: String(profile.full_name || claims.name || claims.email),
      avatarUrl: profile.avatar_url ? String(profile.avatar_url) : null,
      orgId: String(membership.org_id),
      orgRole: String(membership.role),
    })
    return NextResponse.redirect(new URL(stateCookie.next, request.url))
  } catch (error) {
    console.error('Nexus Identity callback could not resolve the app profile', error instanceof Error ? error.message : 'unknown error')
    return NextResponse.json({ error: 'NEXUS_IDENTITY_SESSION_UNAVAILABLE' }, { status: 503 })
  }
}
