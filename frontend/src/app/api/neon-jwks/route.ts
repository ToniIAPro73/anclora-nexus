import { createPublicKey } from 'node:crypto'
import { NextResponse } from 'next/server'

export const runtime = 'nodejs'

export async function GET() {
  const privateKeyPem = process.env.NEON_JWT_PRIVATE_KEY?.replace(/\\n/g, '\n')
  const keyId = process.env.NEON_JWT_KEY_ID
  if (!privateKeyPem || !keyId) {
    return NextResponse.json({ error: 'Neon JWT signing is not configured' }, { status: 503 })
  }

  try {
    const publicJwk = createPublicKey(privateKeyPem).export({ format: 'jwk' })
    if (publicJwk.kty !== 'EC' || publicJwk.crv !== 'P-256') {
      return NextResponse.json({ error: 'Neon JWT signing key must be an EC P-256 key' }, { status: 503 })
    }
    return NextResponse.json(
      { keys: [{ ...publicJwk, kid: keyId, use: 'sig', alg: 'ES256' }] },
      { headers: { 'Cache-Control': 'public, max-age=300, stale-while-revalidate=300' } }
    )
  } catch {
    return NextResponse.json({ error: 'Neon JWT signing key is invalid' }, { status: 503 })
  }
}
