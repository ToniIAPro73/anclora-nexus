import { NextResponse } from 'next/server'
import { getNexusIdentitySession } from '@/lib/anclora-identity/session'
import { createNeonJwt } from '@/lib/neon-jwt'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function GET() {
  const session = await getNexusIdentitySession()
  if (!session) return NextResponse.json({ user: null, session: null }, { headers: { 'Cache-Control': 'no-store' } })

  try {
    const access = createNeonJwt('authenticated', session.userId, 300)
    const user = {
      id: session.userId,
      email: session.email,
      user_metadata: { full_name: session.name, avatar_url: session.avatarUrl },
      app_metadata: { provider: 'anclora-identity' },
    }
    return NextResponse.json({
      user,
      session: { access_token: access.token, token_type: 'bearer', expires_in: 300, expires_at: access.expiresAt, refresh_token: '', user },
    }, { headers: { 'Cache-Control': 'no-store, private' } })
  } catch {
    return NextResponse.json({ error: 'NEXUS_SESSION_TOKEN_UNAVAILABLE' }, { status: 503, headers: { 'Cache-Control': 'no-store' } })
  }
}
