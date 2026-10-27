import { NextResponse } from 'next/server'
import { clearNexusIdentitySession } from '@/lib/anclora-identity/session'

export async function POST() {
  await clearNexusIdentitySession()
  return NextResponse.json({ ok: true }, { headers: { 'Cache-Control': 'no-store' } })
}
