import { createServerClient } from '@supabase/auth-helpers-nextjs'
import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { isAncloraIdentityEnabled } from '@/lib/anclora-identity/env'

function createSupabaseResponse() {
  return NextResponse.json({ ok: true })
}

export async function POST(request: Request) {
  if (isAncloraIdentityEnabled()) return NextResponse.json({ message: 'Sign in through Anclora Identity.' }, { status: 404 })
  try {
    const body = await request.json().catch(() => null)
    const email = String(body?.email || '').trim()
    const password = String(body?.password || '')

    if (!email || !password) {
      return NextResponse.json(
        { message: 'Introduce tu email y tu contraseña.' },
        { status: 400 }
      )
    }

    const cookieStore = await cookies()
    const response = createSupabaseResponse()

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

    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) {
      return NextResponse.json({ message: error.message }, { status: 401 })
    }

    return response
  } catch {
    return NextResponse.json(
      { message: 'No se pudo iniciar sesión. Inténtalo de nuevo en unos segundos.' },
      { status: 500 }
    )
  }
}
