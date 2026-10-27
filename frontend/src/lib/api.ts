import database from './neon-data-client'
import { buildBackendUrl } from './backend-url'

async function resolveCurrentOrgId(userId?: string): Promise<string> {
  if (!userId) throw new Error('No authenticated user to resolve org_id')

  // Prefer active membership org (source of truth for team-enabled flows)
  const membershipRes = await database
    .from('organization_members')
    .select('org_id')
    .eq('user_id', userId)
    .eq('status', 'active')
    .limit(1)
    .maybeSingle()

  if (membershipRes.data?.org_id) {
    return membershipRes.data.org_id
  }

  // Fallback to user profile org_id
  const profileRes = await database
    .from('user_profiles')
    .select('org_id')
    .eq('id', userId)
    .maybeSingle()

  if (profileRes.data?.org_id) {
    return profileRes.data.org_id
  }

  throw new Error('No active organization found for current user')
}

interface LeadData {
  [key: string]: unknown
}

export async function createLead(leadData: LeadData) {
  const { data: { session } } = await database.auth.getSession()
  const token = session?.access_token

  const res = await fetch(buildBackendUrl('/api/leads/intake'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token || ''}`
    },
    body: JSON.stringify(leadData)
  })

  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Error creating lead')
  }
  return res.json()
}

interface SkillData {
  [key: string]: unknown
}

export async function runSkill(skill: string, data: SkillData = {}) {
  const { data: { session } } = await database.auth.getSession()
  const token = session?.access_token

  const res = await fetch(buildBackendUrl('/api/skills/run'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token || ''}`
    },
    body: JSON.stringify({ skill, data })
  })

  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Error running skill')
  }
  return res.json()
}

export interface PropertyData {
  address: string
  price: string
  type?: string
  status?: string
  zone?: string
  useful_area_m2?: number
  built_area_m2?: number
  plot_area_m2?: number
  match_score?: number
  source_system?: string
  source_portal?: string
}

export async function createProperty(propertyData: PropertyData) {
  const { data: { session } } = await database.auth.getSession()
  const org_id = await resolveCurrentOrgId(session?.user?.id)

  // Map frontend to backend fields
  const dbData = {
    org_id,
    address: propertyData.address,
    price: parseFloat(propertyData.price) || 0,
    property_type: propertyData.type || 'Villa',
    status: propertyData.status || 'prospect',
    city: propertyData.zone || 'Mallorca',
    useful_area_m2: propertyData.useful_area_m2 ?? null,
    built_area_m2: propertyData.built_area_m2 ?? null,
    plot_area_m2: propertyData.plot_area_m2 ?? null,
    surface_m2: propertyData.built_area_m2 ?? propertyData.useful_area_m2 ?? null,
    prospection_score: (propertyData.match_score || 0) / 100,
    source_system: propertyData.source_system || 'manual',
    source_portal: propertyData.source_portal || null,
  }

  const { data, error } = await database.from('properties').insert(dbData).select().single()

  if (error) {
    throw new Error(error.message)
  }

  return data
}

export async function getWeeklyStats() {
  const { data: { session } } = await database.auth.getSession()
  const token = session?.access_token

  const res = await fetch(buildBackendUrl('/api/stats/weekly'), {
     headers: {
        'Authorization': `Bearer ${token || ''}`
     }
  })

  if (!res.ok) {
     const error = await res.json()
     throw new Error(error.detail || 'Error fetching stats')
  }
  return res.json()
}

export async function fetchIntelligenceQuery(message: string, mode: 'fast' | 'deep' = 'fast', domainHint?: string) {
  const { data: { session } } = await database.auth.getSession()
  const token = session?.access_token

  const res = await fetch(buildBackendUrl('/api/intelligence/query'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token || ''}`
    },
    body: JSON.stringify({ message, mode, domain_hint: domainHint })
  })

  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Error in intelligence query')
  }
  return res.json()
}

/**
 * Generic API utility for authenticated requests to the backend
 */
export const api = {
  get: async <T>(path: string): Promise<T> => {
    const { data: { session } } = await database.auth.getSession()
    const token = session?.access_token

    const res = await fetch(buildBackendUrl(path), {
      headers: {
        'Authorization': `Bearer ${token || ''}`
      }
    })

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(error.detail || 'Error in GET request')
    }
    return res.json()
  },

  post: async <T>(path: string, body: unknown): Promise<T> => {
    const { data: { session } } = await database.auth.getSession()
    const token = session?.access_token

    const res = await fetch(buildBackendUrl(path), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token || ''}`
      },
      body: JSON.stringify(body)
    })

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(error.detail || 'Error in POST request')
    }
    return res.json()
  }
}
