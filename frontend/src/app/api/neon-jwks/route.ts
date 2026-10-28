import { NextResponse } from 'next/server'
import { buildNeonJwks } from '@/lib/neon-jwks'

export const runtime = 'nodejs'

export async function GET() {
  const privateKeyPem = process.env.NEON_JWT_PRIVATE_KEY?.replace(/\\n/g, '\n')
  const keyId = process.env.NEON_JWT_KEY_ID
  if (!privateKeyPem || !keyId) {
    return NextResponse.json({ error: 'Neon JWT signing is not configured' }, { status: 503 })
  }

  try {
    return NextResponse.json(
      buildNeonJwks(privateKeyPem, keyId, process.env.NEON_JWT_ADDITIONAL_PUBLIC_KEYS),
      { headers: { 'Cache-Control': 'public, max-age=300, stale-while-revalidate=300' } }
    )
  } catch {
    return NextResponse.json({ error: 'Neon JWT signing configuration is invalid' }, { status: 503 })
  }
}
