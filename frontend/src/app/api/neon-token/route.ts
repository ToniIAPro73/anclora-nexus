import { NextResponse } from 'next/server'
import { createNeonJwt } from '@/lib/neon-jwt'
import { getNexusIdentitySession } from '@/lib/anclora-identity/session'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function POST() {
  try {
    const session = await getNexusIdentitySession()
    if (!session) return NextResponse.json({ error: 'Authentication required' }, { status: 401, headers: { 'Cache-Control': 'no-store' } })
    return NextResponse.json(createNeonJwt('authenticated', session.userId, 300), { headers: { 'Cache-Control': 'no-store, private' } })
  } catch (error) {
    console.error('Neon token exchange failed', error instanceof Error ? error.message : 'unknown error')
    return NextResponse.json({ error: 'Neon data access unavailable' }, { status: 503, headers: { 'Cache-Control': 'no-store' } })
  }
}
