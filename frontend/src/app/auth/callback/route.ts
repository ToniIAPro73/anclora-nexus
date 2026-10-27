import { createServerClient } from '@supabase/auth-helpers-nextjs'
import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { normalizeNextPath } from '@/lib/private-area-access'
import { isAncloraIdentityEnabled } from '@/lib/anclora-identity/env'

export async function GET(request: Request) {
  if (isAncloraIdentityEnabled()) return NextResponse.json({ error: 'Use the Anclora Identity callback.' }, { status: 404 })
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')
  const tokenHash = searchParams.get('token_hash')
  const type = searchParams.get('type')
  const next = normalizeNextPath(searchParams.get('next'), type === 'recovery' ? '/login?mode=reset' : '/dashboard')

  if (code) {
    const cookieStore = await cookies()
    
    // Create a response so we can set cookies on it
    const response = NextResponse.redirect(`${origin}${next}`)

    const supabase = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        cookies: {
          get(name: string) {
            return cookieStore.get(name)?.value
          },
          set(name: string, value: string, options: Record<string, unknown>) {
            response.cookies.set({ name, value, ...options })
          },
          remove(name: string, options: Record<string, unknown>) {
            response.cookies.set({ name, value: '', ...options })
          },
        },
      }
    )

    const { error } = await supabase.auth.exchangeCodeForSession(code)
    if (!error) {
      return response
    }
  }

  if (tokenHash && type) {
    const cookieStore = await cookies()
    const response = NextResponse.redirect(`${origin}${next}`)

    const supabase = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        cookies: {
          get(name: string) {
            return cookieStore.get(name)?.value
          },
          set(name: string, value: string, options: Record<string, unknown>) {
            response.cookies.set({ name, value, ...options })
          },
          remove(name: string, options: Record<string, unknown>) {
            response.cookies.set({ name, value: '', ...options })
          },
        },
      }
    )

    const { error } = await supabase.auth.verifyOtp({
      token_hash: tokenHash,
      type: type as 'recovery' | 'email' | 'signup' | 'invite' | 'magiclink' | 'email_change',
    })
    if (!error) {
      return response
    }
  }

  return NextResponse.redirect(`${origin}/login?error=auth-callback-failed`)
}

export async function POST(request: Request) {
  if (isAncloraIdentityEnabled()) return NextResponse.json({ error: 'Account management is handled by Anclora Identity.' }, { status: 404 })
  try {
    const body = await request.json()
    const password = String(body?.password || '')

    if (!password || password.length < 8) {
      return NextResponse.json(
        { message: 'La contraseña debe tener al menos 8 caracteres.' },
        { status: 400 }
      )
    }

    const cookieStore = await cookies()
    const response = NextResponse.json({ ok: true })

    const supabase = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        cookies: {
          get(name: string) {
            return cookieStore.get(name)?.value
          },
          set(name: string, value: string, options: Record<string, unknown>) {
            response.cookies.set({ name, value, ...options })
          },
          remove(name: string, options: Record<string, unknown>) {
            response.cookies.set({ name, value: '', ...options })
          },
        },
      }
    )

    const { data: userData, error: userError } = await supabase.auth.getUser()
    if (userError || !userData?.user) {
      return NextResponse.json({ message: 'Auth session missing' }, { status: 401 })
    }

    const { error } = await supabase.auth.updateUser({ password })
    if (error) {
      return NextResponse.json({ message: error.message }, { status: 400 })
    }

    return response
  } catch {
    return NextResponse.json({ message: 'No se pudo actualizar la contraseña.' }, { status: 500 })
  }
}
