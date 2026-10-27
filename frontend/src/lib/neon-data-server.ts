import 'server-only'
import { createClient } from '@supabase/supabase-js'
import { createNeonJwt } from '@/lib/neon-jwt'

const neonApiUrl = process.env.NEON_DATA_API_URL || process.env.NEXT_PUBLIC_NEON_DATA_API_URL || ''

export function createNeonDataClient(role: 'authenticated' | 'service_role', subject: string) {
  if (!neonApiUrl) {
    throw new Error('Neon Data API configuration is missing')
  }
  const { token } = createNeonJwt(role, subject, role === 'service_role' ? 900 : 300)
  const baseUrl = neonApiUrl.replace(/\/rest\/v1\/?$/, '').replace(/\/$/, '')
  return createClient(baseUrl, 'neon-data-api', {
    auth: { autoRefreshToken: false, persistSession: false, detectSessionInUrl: false },
    global: {
      headers: { Authorization: `Bearer ${token}` },
      fetch: async (input, init) => {
        const headers = new Headers(init?.headers)
        headers.delete('apikey')
        return fetch(input, { ...init, headers })
      },
    },
  })
}
