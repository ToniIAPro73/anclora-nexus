import { NextResponse, type NextRequest } from 'next/server'
import { normalizeNextPath } from '@/lib/private-area-access'
import { NEXUS_IDENTITY_SESSION_COOKIE, readNexusIdentitySession } from '@/lib/anclora-identity/session-token'

export function proxy(request: NextRequest) {
  const response = NextResponse.next()
  const pathname = request.nextUrl.pathname
  const isLoginPage = pathname.startsWith('/login')
  const isAuthRoute = pathname.startsWith('/auth/')
  const isInvitePage = pathname.startsWith('/invite/')
  const isPrivateAreaPublic = pathname === '/private-area' || pathname.startsWith('/private-area/')
  if (isAuthRoute || isInvitePage || isPrivateAreaPublic) return response

  const session = readNexusIdentitySession(request.cookies.get(NEXUS_IDENTITY_SESSION_COOKIE)?.value)
  if (!session && !isLoginPage) {
    response.cookies.delete(NEXUS_IDENTITY_SESSION_COOKIE)
    response.cookies.delete('nexus-org-id')
    response.cookies.delete('nexus-org-role')
    return NextResponse.redirect(new URL('/login', request.url))
  }
  if (session && isLoginPage) {
    const next = normalizeNextPath(request.nextUrl.searchParams.get('next'), '/dashboard')
    return NextResponse.redirect(new URL(next, request.url))
  }
  if (session) {
    response.cookies.set('nexus-org-id', session.orgId, { httpOnly: false, secure: process.env.NODE_ENV === 'production', sameSite: 'lax', maxAge: 60 * 60 * 24 * 7 })
    response.cookies.set('nexus-org-role', session.orgRole, { httpOnly: false, secure: process.env.NODE_ENV === 'production', sameSite: 'lax', maxAge: 60 * 60 * 24 * 7 })
  } else {
    response.cookies.delete('nexus-org-id')
    response.cookies.delete('nexus-org-role')
  }
  return response
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico|brand).*)'],
}
