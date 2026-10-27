'use client'

import { NeonPostgrestClient } from '@neondatabase/postgrest-js'

export interface IdentityUser {
  id: string
  email?: string
  user_metadata?: Record<string, unknown>
  app_metadata?: Record<string, unknown>
}

export interface IdentitySession {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  expires_at: number
  refresh_token: string
  user: IdentityUser
}

export type IdentityAuthEvent = 'INITIAL_SESSION' | 'SIGNED_IN' | 'SIGNED_OUT' | 'TOKEN_REFRESHED' | 'USER_UPDATED'
type AuthPayload = { user: IdentityUser | null; session: IdentitySession | null }

let cachedToken: { value: string; expiresAt: number } | null = null
let tokenRequest: Promise<string> | null = null

async function getNeonToken(): Promise<string> {
  if (cachedToken && cachedToken.expiresAt > Date.now() + 30_000) return cachedToken.value
  if (!tokenRequest) {
    tokenRequest = fetch('/api/neon-token', { method: 'POST', cache: 'no-store', credentials: 'same-origin' })
      .then(async (response) => {
        if (!response.ok) throw new Error('Unable to authorize Neon database access')
        const result = await response.json() as { token: string; expiresAt: number }
        cachedToken = { value: result.token, expiresAt: result.expiresAt * 1000 }
        return result.token
      })
      .finally(() => { tokenRequest = null })
  }
  return tokenRequest
}

const database = new NeonPostgrestClient({
  dataApiUrl: process.env.NEXT_PUBLIC_NEON_DATA_API_URL || '',
  options: {
    global: {
      fetch: async (input, init) => {
        const token = await getNeonToken()
        const headers = new Headers(init?.headers)
        headers.set('Authorization', `Bearer ${token}`)
        return fetch(input, { ...init, headers })
      },
    },
  },
})

async function getAuthPayload(): Promise<AuthPayload> {
  const response = await fetch('/api/auth/session', { cache: 'no-store', credentials: 'same-origin' })
  if (!response.ok) return { user: null, session: null }
  return await response.json() as AuthPayload
}

const identityAuth = {
  async getSession() {
    const { session } = await getAuthPayload()
    return { data: { session }, error: null }
  },
  async getUser() {
    const { user } = await getAuthPayload()
    return { data: { user }, error: null }
  },
  async signOut() {
    const response = await fetch('/api/auth/anclora-identity/logout', { method: 'POST', credentials: 'same-origin' })
    cachedToken = null
    window.dispatchEvent(new Event('anclora-auth-change'))
    return { error: response.ok ? null : new Error('Unable to end Nexus session') }
  },
  onAuthStateChange(callback: (event: IdentityAuthEvent, session: IdentitySession | null) => void) {
    const listener = () => { void this.getSession().then(({ data }) => callback(data.session ? 'SIGNED_IN' : 'SIGNED_OUT', data.session)) }
    if (typeof window !== 'undefined') window.addEventListener('anclora-auth-change', listener)
    return { data: { subscription: { unsubscribe() { if (typeof window !== 'undefined') window.removeEventListener('anclora-auth-change', listener) } } } }
  },
  async signInWithOAuth() {
    window.location.assign('/api/auth/anclora-identity/login')
    return { data: null, error: null }
  },
}

if (typeof window !== 'undefined') {
  window.addEventListener('anclora-auth-change', () => { cachedToken = null })
}

export { identityAuth }
export default Object.assign(database, { auth: identityAuth })
