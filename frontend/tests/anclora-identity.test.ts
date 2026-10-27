import { afterEach, describe, expect, it } from 'vitest'
import { hasNexusApplicationAccess } from '@/lib/anclora-identity/authorization'
import { encodeSigned, readNexusIdentitySession } from '@/lib/anclora-identity/session-token'

const originalEnv = {
  enabled: process.env.ANCLORA_IDENTITY_ENABLED,
  issuer: process.env.ANCLORA_IDENTITY_ISSUER_URL,
  clientId: process.env.ANCLORA_IDENTITY_CLIENT_ID,
  clientSecret: process.env.ANCLORA_IDENTITY_CLIENT_SECRET,
  redirect: process.env.ANCLORA_IDENTITY_REDIRECT_URI,
  secret: process.env.ANCLORA_IDENTITY_SESSION_SECRET,
}

afterEach(() => {
  const pairs = [
    ['ANCLORA_IDENTITY_ENABLED', originalEnv.enabled], ['ANCLORA_IDENTITY_ISSUER_URL', originalEnv.issuer],
    ['ANCLORA_IDENTITY_CLIENT_ID', originalEnv.clientId], ['ANCLORA_IDENTITY_CLIENT_SECRET', originalEnv.clientSecret],
    ['ANCLORA_IDENTITY_REDIRECT_URI', originalEnv.redirect], ['ANCLORA_IDENTITY_SESSION_SECRET', originalEnv.secret],
  ] as const
  for (const [key, value] of pairs) {
    if (value === undefined) delete process.env[key]
    else process.env[key] = value
  }
})

describe('Nexus Anclora Identity access', () => {
  it('requires Nexus membership or the explicit group owner role', () => {
    expect(hasNexusApplicationAccess({ sub: 'id-1', application_memberships: ['anclora-nexus'] })).toBe(true)
    expect(hasNexusApplicationAccess({ sub: 'id-2', platform_roles: ['GROUP_OWNER'] })).toBe(true)
    expect(hasNexusApplicationAccess({ sub: 'id-3', application_memberships: ['data-lab'] })).toBe(false)
  })

  it('accepts only valid, unexpired signed Nexus sessions', () => {
    const secret = 'test-session-secret-at-least-32-characters'
    process.env.ANCLORA_IDENTITY_ENABLED = 'true'
    process.env.ANCLORA_IDENTITY_ISSUER_URL = 'https://identity.example.test'
    process.env.ANCLORA_IDENTITY_CLIENT_ID = 'anclora-nexus'
    process.env.ANCLORA_IDENTITY_CLIENT_SECRET = 'client-secret-at-least-16-characters'
    process.env.ANCLORA_IDENTITY_REDIRECT_URI = 'https://nexus.example.test/callback'
    process.env.ANCLORA_IDENTITY_SESSION_SECRET = secret
    const session = {
      sub: 'identity-user-id', userId: '00000000-0000-4000-8000-000000000001', email: 'qa.nexus@anclora.local',
      name: 'Nexus QA', avatarUrl: null, orgId: '00000000-0000-4000-8000-000000000002', orgRole: 'owner',
      exp: Math.floor(Date.now() / 1000) + 60,
    }
    const token = encodeSigned(secret, session)
    expect(readNexusIdentitySession(token)).toMatchObject({ userId: session.userId, orgId: session.orgId })
    expect(readNexusIdentitySession(`${token}tampered`)).toBeNull()
    expect(readNexusIdentitySession(encodeSigned(secret, { ...session, exp: 1 }))).toBeNull()
  })
})
