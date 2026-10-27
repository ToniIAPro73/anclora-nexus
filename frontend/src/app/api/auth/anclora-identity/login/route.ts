import { NextResponse } from 'next/server'
import { normalizeNextPath } from '@/lib/private-area-access'
import { isAncloraIdentityEnabled, getAncloraIdentityConfig } from '@/lib/anclora-identity/env'
import { buildLoginRedirect, calculatePKCECodeChallenge, getAncloraIdentityOidcConfig, randomPKCECodeVerifier, randomState } from '@/lib/anclora-identity/oidcClient'
import { storeOidcState } from '@/lib/anclora-identity/session'

export const runtime = 'nodejs'

export async function GET(request: Request) {
  if (!isAncloraIdentityEnabled()) return NextResponse.json({ error: 'ANCLORA_IDENTITY_DISABLED' }, { status: 404 })
  const { redirectUri } = getAncloraIdentityConfig()
  const oidc = await getAncloraIdentityOidcConfig()
  const state = randomState()
  const codeVerifier = randomPKCECodeVerifier()
  const codeChallenge = await calculatePKCECodeChallenge(codeVerifier)
  const next = normalizeNextPath(new URL(request.url).searchParams.get('next'), '/dashboard')
  await storeOidcState({ state, codeVerifier, next })
  return NextResponse.redirect(buildLoginRedirect(oidc, { redirectUri, state, codeChallenge }))
}
