import { createServerClient } from '@supabase/auth-helpers-nextjs'
import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { createNeonJwt } from '@/lib/neon-jwt'
import { isAncloraIdentityEnabled } from '@/lib/anclora-identity/env'
import { getNexusIdentitySession } from '@/lib/anclora-identity/session'

export const runtime = 'nodejs'

export async function POST() {
  try {
    if (isAncloraIdentityEnabled()) {
      const session = await getNexusIdentitySession()
      if (!session) return NextResponse.json({ error: 'Authentication required' }, { status: 401, headers: { 'Cache-Control': 'no-store' } })
      return NextResponse.json(createNeonJwt('authenticated', session.userId, 300), { headers: { 'Cache-Control': 'no-store, private' } })
    }
    const cookieStore = await cookies()
    const supabase = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        cookies: {
          getAll: () => cookieStore.getAll(),
          setAll: (cookiesToSet) => {
            try {
              cookiesToSet.forEach(({ name, value, options }) => cookieStore.set(name, value, options))
            } catch {
              // Route handlers may not permit cookie writes in every rendering context.
            }
          },
        },
      }
    )
    const { data: { user }, error } = await supabase.auth.getUser()
    if (error || !user) {
      return NextResponse.json({ error: 'Authentication required' }, { status: 401, headers: { 'Cache-Control': 'no-store' } })
    }

    const token = createNeonJwt('authenticated', user.id)
    return NextResponse.json(token, { headers: { 'Cache-Control': 'no-store, private' } })
  } catch (error) {
    console.error('Neon token exchange failed', error instanceof Error ? error.message : 'unknown error')
    return NextResponse.json({ error: 'Neon data access unavailable' }, { status: 503, headers: { 'Cache-Control': 'no-store' } })
  }
}
