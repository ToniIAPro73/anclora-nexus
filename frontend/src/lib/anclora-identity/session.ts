import { cookies } from 'next/headers'
import { getAncloraIdentityConfig } from './env'
import { decodeSigned, encodeSigned, readNexusIdentitySession, NEXUS_IDENTITY_SESSION_COOKIE, type NexusIdentitySession } from './session-token'
export { readNexusIdentitySession, type NexusIdentitySession, NEXUS_IDENTITY_SESSION_COOKIE } from './session-token'

const OIDC_STATE_COOKIE = 'anclora-nexus-identity-state'

interface OidcState { state: string; codeVerifier: string; next: string }

export async function getNexusIdentitySession() {
  const store = await cookies()
  return readNexusIdentitySession(store.get(NEXUS_IDENTITY_SESSION_COOKIE)?.value)
}

export async function createNexusIdentitySession(session: Omit<NexusIdentitySession, 'exp'>) {
  const { sessionSecret } = getAncloraIdentityConfig()
  const store = await cookies()
  const expiresIn = 60 * 60 * 12
  store.set(NEXUS_IDENTITY_SESSION_COOKIE, encodeSigned(sessionSecret, { ...session, exp: Math.floor(Date.now() / 1000) + expiresIn }), {
    httpOnly: true, sameSite: 'lax', secure: process.env.NODE_ENV === 'production', path: '/', maxAge: expiresIn,
  })
}

export async function clearNexusIdentitySession() {
  const store = await cookies()
  store.set(NEXUS_IDENTITY_SESSION_COOKIE, '', { httpOnly: true, sameSite: 'lax', secure: process.env.NODE_ENV === 'production', path: '/', maxAge: 0, expires: new Date(0) })
}

export async function storeOidcState(payload: OidcState) {
  const { sessionSecret } = getAncloraIdentityConfig()
  const store = await cookies()
  store.set(OIDC_STATE_COOKIE, encodeSigned(sessionSecret, payload), { httpOnly: true, sameSite: 'lax', secure: process.env.NODE_ENV === 'production', path: '/', maxAge: 600 })
}

export async function consumeOidcState(): Promise<OidcState | null> {
  const { sessionSecret } = getAncloraIdentityConfig()
  const store = await cookies()
  const token = store.get(OIDC_STATE_COOKIE)?.value
  store.set(OIDC_STATE_COOKIE, '', { httpOnly: true, sameSite: 'lax', secure: process.env.NODE_ENV === 'production', path: '/', maxAge: 0, expires: new Date(0) })
  return token ? decodeSigned<OidcState>(sessionSecret, token) : null
}
