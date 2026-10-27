import { NextResponse } from 'next/server'
import { isAncloraIdentityEnabled } from '@/lib/anclora-identity/env'
import { clearNexusIdentitySession } from '@/lib/anclora-identity/session'

export async function POST() {
  if (!isAncloraIdentityEnabled()) return NextResponse.json({ error: 'ANCLORA_IDENTITY_DISABLED' }, { status: 404 })
  await clearNexusIdentitySession()
  return NextResponse.json({ ok: true }, { headers: { 'Cache-Control': 'no-store' } })
}
