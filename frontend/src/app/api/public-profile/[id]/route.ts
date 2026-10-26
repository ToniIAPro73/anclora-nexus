import { NextResponse } from 'next/server'
import { createNeonDataClient } from '@/lib/neon-data-server'
import { createClient } from '@supabase/supabase-js'

export const runtime = 'nodejs'

const PUBLIC_PROFILE_FIELDS = 'id,full_name,bio,specialization,achievements,location,job_title,avatar_url'

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  if (!/^[0-9a-f-]{36}$/i.test(id)) {
    return NextResponse.json({ error: 'Profile not found' }, { status: 404 })
  }

  try {
    const client = process.env.DATABASE_PROVIDER === 'neon'
      ? createNeonDataClient('service_role', 'nexus-public-profile-route')
      : createClient(
          process.env.NEXT_PUBLIC_SUPABASE_URL!,
          process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
          { auth: { autoRefreshToken: false, persistSession: false, detectSessionInUrl: false } }
        )

    const { data, error } = await client
      .from('user_profiles')
      .select(PUBLIC_PROFILE_FIELDS)
      .eq('id', id)
      .maybeSingle()

    if (error || !data) return NextResponse.json({ error: 'Profile not found' }, { status: 404 })
    return NextResponse.json(data, { headers: { 'Cache-Control': 'public, max-age=60' } })
  } catch {
    return NextResponse.json({ error: 'Profile unavailable' }, { status: 503 })
  }
}
