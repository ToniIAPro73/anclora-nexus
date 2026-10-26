import { createServerClient } from '@supabase/auth-helpers-nextjs'
import { cookies } from 'next/headers'
import type { OrgMembership } from '@/lib/contexts/OrgContext'
import { createNeonDataClient } from '@/lib/neon-data-server'

/**
 * Server-side function to fetch user and org data
 * Called once per request, cached via Next.js request deduplication
 */
export async function fetchUserAndOrg() {
  try {
    const cookieStore = await cookies()
    type CookieSetOptions = Parameters<typeof cookieStore.set>[2]
    const supabase = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        cookies: {
          get(name: string) {
            return cookieStore.get(name)?.value
          },
          set(name: string, value: string, options: CookieSetOptions) {
            cookieStore.set(name, value, options)
          },
          remove(name: string, options: CookieSetOptions) {
            cookieStore.set(name, '', { ...options, maxAge: 0 })
          },
        },
      }
    )

    const { data: { user } } = await supabase.auth.getUser()

    if (!user) {
      return { user: null, membership: null, orgId: null }
    }

    const dataClient = process.env.DATABASE_PROVIDER === 'neon'
      ? createNeonDataClient('authenticated', user.id)
      : supabase

    // Fetch user profile and org memberships in parallel
    const [profileData, membershipsData] = await Promise.all([
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

    const preferredOrgId = profileData.data?.org_id || null
    const memberships = membershipsData.data as OrgMembership[] || []

    // Select the preferred membership or first one
    let selectedMembership: OrgMembership | null = null
    if (memberships.length > 0) {
      if (preferredOrgId) {
        selectedMembership = memberships.find(m => m.org_id === preferredOrgId) || memberships[0]
      } else {
        selectedMembership = memberships[0]
      }
    }

    return {
      user,
      membership: selectedMembership,
      orgId: selectedMembership?.org_id || null,
    }
  } catch (error) {
    const isDynamicServerUsage =
      error instanceof Error &&
      ('digest' in error || 'description' in error) &&
      (
        String((error as { digest?: unknown }).digest ?? '').includes('DYNAMIC_SERVER_USAGE') ||
        String((error as { description?: unknown }).description ?? '').includes('Dynamic server usage')
      )

    if (!isDynamicServerUsage) {
      console.error('Error fetching user and org:', error)
    }

    return { user: null, membership: null, orgId: null }
  }
}
