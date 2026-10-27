'use client'

import { useEffect } from 'react'
import { normalizeNextPath } from '@/lib/private-area-access'

export default function LoginPage() {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const invite = params.get('invite')
    const next = normalizeNextPath(params.get('next') || (invite ? `/invite/${encodeURIComponent(invite)}` : '/dashboard'), '/dashboard')
    window.location.replace(`/api/auth/anclora-identity/login?next=${encodeURIComponent(next)}`)
  }, [])

  return <main className="grid min-h-screen place-items-center">Conectando con Anclora Identity…</main>
}
