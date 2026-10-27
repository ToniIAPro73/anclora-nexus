'use client'

import { useState, useCallback } from 'react'
import database from '@/lib/neon-data-client'
import { useOrgMembership } from './useOrgMembership'
import { OrgRole } from '../contexts/OrgContext'

export function useTeamManagement() {
  const { org_id, canManageTeam } = useOrgMembership()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const getResponseError = async (response: Response, fallback: string) => {
    const contentType = response.headers.get('content-type') || ''
    if (contentType.includes('application/json')) {
      const data = await response.json()
      return data.detail || data.message || fallback
    }

    const raw = await response.text()
    try {
      const parsed = JSON.parse(raw)
      return parsed.detail || parsed.message || fallback
    } catch {
      return raw || fallback
    }
  }

  const inviteMember = useCallback(async (email: string, role: OrgRole) => {
    if (!canManageTeam) throw new Error('Unauthorized')
    setLoading(true)
    setError(null)
    try {
      const { data: { session } } = await database.auth.getSession()
      const token = session?.access_token

      if (!token) throw new Error('No active session')

      const response = await fetch(`/api/organizations/${org_id}/members`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ email, role })
      })

      if (!response.ok) {
        throw new Error(await getResponseError(response, 'Failed to invite member'))
      }

      return await response.json()
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'An error occurred'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [org_id, canManageTeam])

  const changeMemberRole = useCallback(async (memberId: string, role: OrgRole) => {
    if (!canManageTeam) throw new Error('Unauthorized')
    setLoading(true)
    setError(null)
    try {
      const { data: { session } } = await database.auth.getSession()
      const token = session?.access_token

      if (!token) throw new Error('No active session')

      const response = await fetch(`/api/organizations/${org_id}/members/${memberId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ role })
      })

      if (!response.ok) {
        throw new Error(await getResponseError(response, 'Failed to update role'))
      }

      return await response.json()
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'An error occurred'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [org_id, canManageTeam])

  const removeMember = useCallback(async (memberId: string) => {
    if (!canManageTeam) throw new Error('Unauthorized')
    setLoading(true)
    setError(null)
    try {
      const { data: { session } } = await database.auth.getSession()
      const token = session?.access_token

      if (!token) throw new Error('No active session')

      const response = await fetch(`/api/organizations/${org_id}/members/${memberId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (!response.ok) {
        throw new Error(await getResponseError(response, 'Failed to remove member'))
      }

      return true
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'An error occurred'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [org_id, canManageTeam])

  const fetchMembers = useCallback(async () => {
    if (!org_id) return []
    setLoading(true)
    setError(null)
    try {
      const { data: { session } } = await database.auth.getSession()
      const token = session?.access_token

      if (!token) throw new Error('No active session')

      const response = await fetch(`/api/organizations/${org_id}/members`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      if (!response.ok) {
        throw new Error(await getResponseError(response, 'Failed to fetch members'))
      }
      const data = await response.json()
      return data.members
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'An error occurred'
      setError(message)
      return []
    } finally {
      setLoading(false)
    }
  }, [org_id])

  return {
    loading,
    error,
    inviteMember,
    changeMemberRole,
    removeMember,
    fetchMembers
  }
}
