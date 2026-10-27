'use client'

import React, { createContext, useContext, useState, useEffect } from 'react'
import type { IdentityAuthEvent } from '@/lib/neon-data-client'
import database from '@/lib/neon-data-client'

export type OrgRole = 'owner' | 'manager' | 'agent'
export type MembershipStatus = 'active' | 'pending' | 'suspended' | 'removed'

export interface OrgMembership {
  id: string
  org_id: string
  user_id?: string | null
  role: OrgRole
  status: MembershipStatus
  joined_at: string
}

interface OrgContextType {
  membership: OrgMembership | null
  loading: boolean
  error: string | null
  refreshMembership: () => Promise<void>
}

export const OrgContext = createContext<OrgContextType | undefined>(undefined)

interface OrgProviderProps {
  children: React.ReactNode
  initialMembership?: OrgMembership | null
}

export function OrgProvider({ children, initialMembership = null }: OrgProviderProps) {
  const [membership, setMembership] = useState<OrgMembership | null>(initialMembership ?? null)
  const [loading, setLoading] = useState(!initialMembership)
  const [error, setError] = useState<string | null>(null)

  const fetchMembership = async () => {
    try {
      setLoading(true)
      const { data: { user } } = await database.auth.getUser()
      
      if (!user) {
        setMembership(null)
        setLoading(false)
        return
      }

      const { data: profileData } = await database
        .from('user_profiles')
        .select('org_id')
        .eq('id', user.id)
        .maybeSingle()

      const preferredOrgId = profileData?.org_id || null

      const { data, error: fetchError } = await database
        .from('organization_members')
        .select('*')
        .eq('user_id', user.id)
        .eq('status', 'active')
        .order('updated_at', { ascending: false })

      if (fetchError) {
        setError(fetchError.message)
        setMembership(null)
      } else {
        const rows = Array.isArray(data) ? (data as OrgMembership[]) : []
        if (!rows.length) {
          setMembership(null)
        } else if (preferredOrgId) {
          const preferred = rows.find((row) => row.org_id === preferredOrgId)
          setMembership(preferred || rows[0])
        } else {
          setMembership(rows[0])
        }
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // Only fetch if we don't have initial data
    if (!initialMembership) {
      fetchMembership()
    }

    // Listen for auth changes (login/logout), but not every route change
    const { data: { subscription } } = database.auth.onAuthStateChange((event: IdentityAuthEvent) => {
      // Only refetch on actual auth events (sign out, sign in), not route changes
      if (event === 'SIGNED_OUT' || event === 'SIGNED_IN' || event === 'USER_UPDATED') {
        fetchMembership()
      }
    })

    return () => {
      subscription.unsubscribe()
    }
  }, [initialMembership])

  return (
    <OrgContext.Provider 
      value={{ 
        membership, 
        loading, 
        error, 
        refreshMembership: fetchMembership 
      }}
    >
      {children}
    </OrgContext.Provider>
  )
}

export function useOrg() {
  const context = useContext(OrgContext)
  if (context === undefined) {
    throw new Error('useOrg must be used within an OrgProvider')
  }
  return context
}
