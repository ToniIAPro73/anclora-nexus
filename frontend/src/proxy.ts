import { createServerClient } from '@supabase/auth-helpers-nextjs'
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { normalizeNextPath } from '@/lib/private-area-access'
import { createNeonDataClient } from '@/lib/neon-data-server'

export async function proxy(req: NextRequest) {
  let res = NextResponse.next({
    request: {
      headers: req.headers,
    },
  })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        get(name: string) {
          return req.cookies.get(name)?.value
        },
        set(name: string, value: string, options: Record<string, unknown>) {
          req.cookies.set({
            name,
            value,
            ...options,
          })
          res = NextResponse.next({
            request: {
              headers: req.headers,
            },
          })
          res.cookies.set({
            name,
            value,
            ...options,
          })
        },
        remove(name: string, options: Record<string, unknown>) {
          req.cookies.set({
            name,
            value: '',
            ...options,
          })
          res = NextResponse.next({
            request: {
              headers: req.headers,
            },
          })
          res.cookies.set({
            name,
            value: '',
            ...options,
          })
        },
      },
    }
  )

  const {
    data: { session },
  } = await supabase.auth.getSession()

  const isLoginPage = req.nextUrl.pathname.startsWith('/login')
  const isAuthRoute = req.nextUrl.pathname.startsWith('/auth/')
  const isInvitePage = req.nextUrl.pathname.startsWith('/invite/')
  const isPrivateAreaPublic = req.nextUrl.pathname === '/private-area' || req.nextUrl.pathname.startsWith('/private-area/')
  const isRecoveryFlow =
    req.nextUrl.searchParams.has('code') ||
    req.nextUrl.searchParams.get('mode') === 'reset' ||
    req.nextUrl.searchParams.get('type') === 'recovery'

  if (isAuthRoute || isInvitePage || isPrivateAreaPublic) {
    return res
  }

  if (!session && !isLoginPage) {
    return NextResponse.redirect(new URL('/login', req.url))
  }

  if (session && isLoginPage && !isRecoveryFlow) {
    const next = normalizeNextPath(req.nextUrl.searchParams.get('next'), '/dashboard')
    return NextResponse.redirect(new URL(next, req.url))
  }

  if (session && !isLoginPage) {
    const {
      data: { user },
      error: userError,
    } = await supabase.auth.getUser()

    if (userError || !user) {
      await supabase.auth.signOut()
      res.cookies.delete('nexus-org-id')
      res.cookies.delete('nexus-org-role')
      return NextResponse.redirect(new URL('/login?error=session-invalid', req.url))
    }

    const dataClient = process.env.DATABASE_PROVIDER === 'neon'
      ? createNeonDataClient('authenticated', user.id)
      : supabase

    // Fetch full membership data and cache it
    const [profileData, membershipData] = await Promise.all([
      dataClient
        .from('user_profiles')
        .select('org_id')
        .eq('id', user.id)
        .maybeSingle(),
      dataClient
        .from('organization_members')
        .select('*')
        .eq('user_id', user.id)
        .eq('status', 'active')
        .order('updated_at', { ascending: false }),
    ])

    const membershipRows = membershipData.data || []
    if (!membershipRows.length) {
      await supabase.auth.signOut()
      res.cookies.delete('nexus-org-id')
      res.cookies.delete('nexus-org-role')
      return NextResponse.redirect(new URL('/login?error=invitation-required', req.url))
    }

    // Select preferred membership
    const preferredOrgId = profileData.data?.org_id
    const selectedMembership = preferredOrgId
      ? membershipRows.find(m => m.org_id === preferredOrgId) || membershipRows[0]
      : membershipRows[0]

    // Cache org data in cookies (7 days) to prevent repeated queries on navigation
    res.cookies.set('nexus-org-id', selectedMembership.org_id, {
      httpOnly: false,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 60 * 60 * 24 * 7,
    })
    res.cookies.set('nexus-org-role', selectedMembership.role, {
      httpOnly: false,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 60 * 60 * 24 * 7,
    })
  } else if (!session) {
    // Clear org cookies if session is gone
    res.cookies.delete('nexus-org-id')
    res.cookies.delete('nexus-org-role')
  }

  return res
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico|brand).*)'],
}
