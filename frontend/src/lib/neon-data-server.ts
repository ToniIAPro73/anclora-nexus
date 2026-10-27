import 'server-only'
import { NeonPostgrestClient } from '@neondatabase/postgrest-js'
import { createNeonJwt } from '@/lib/neon-jwt'

const dataApiUrl = process.env.NEON_DATA_API_URL || process.env.NEXT_PUBLIC_NEON_DATA_API_URL || ''

function createClient(role: 'authenticated' | 'service_role', subject: string) {
  if (!dataApiUrl) throw new Error('Neon Data API configuration is missing')
  const { token } = createNeonJwt(role, subject, role === 'service_role' ? 900 : 300)
  return new NeonPostgrestClient({
    dataApiUrl,
    options: { global: { fetch: globalThis.fetch.bind(globalThis), headers: { Authorization: `Bearer ${token}` } } },
  })
}

export function createNeonDataClient(role: 'authenticated' | 'service_role', subject: string) {
  return createClient(role, subject)
}
