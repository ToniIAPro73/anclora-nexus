import { createHmac, timingSafeEqual } from 'node:crypto'
import { getAncloraIdentityConfig } from './env'

export const NEXUS_IDENTITY_SESSION_COOKIE = 'anclora-nexus-identity-session'

export interface NexusIdentitySession {
  sub: string
  userId: string
  email: string
  name: string
  avatarUrl: string | null
  orgId: string
  orgRole: string
  exp: number
}

export function encodeSigned<T>(secret: string, payload: T) {
  const body = Buffer.from(JSON.stringify(payload)).toString('base64url')
  const signature = createHmac('sha256', secret).update(body).digest('base64url')
  return `${body}.${signature}`
}

export function decodeSigned<T>(secret: string, token: string): T | null {
  const [body, signature] = token.split('.')
  if (!body || !signature) return null
  const expected = Buffer.from(createHmac('sha256', secret).update(body).digest('base64url'), 'base64url')
  const received = Buffer.from(signature, 'base64url')
  if (expected.length !== received.length || !timingSafeEqual(expected, received)) return null
  try { return JSON.parse(Buffer.from(body, 'base64url').toString('utf8')) as T } catch { return null }
}

export function readNexusIdentitySession(token?: string | null): NexusIdentitySession | null {
  if (!token) return null
  const { sessionSecret } = getAncloraIdentityConfig()
  const session = decodeSigned<NexusIdentitySession>(sessionSecret, token)
  if (!session || !session.exp || session.exp <= Math.floor(Date.now() / 1000)) return null
  return session
}
