import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
/* eslint-disable @typescript-eslint/no-explicit-any */
import { render, screen, waitFor } from '@testing-library/react'
import { OrgProvider, useOrg } from '@/lib/contexts/OrgContext'
import { useOrgMembership } from '@/lib/hooks/useOrgMembership'
import database from '@/lib/neon-data-client'

vi.mock('@/lib/neon-data-client', () => ({
  default: {
    auth: {
      getUser: vi.fn(),
      onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } }))
    },
    from: vi.fn(() => ({
      select: vi.fn().mockReturnThis(),
      eq: vi.fn().mockReturnThis(),
      single: vi.fn()
    }))
  }
}))

const TestComponent = () => {
  const { membership, loading } = useOrg()
  if (loading) return <div>Loading...</div>
  return <div>{membership ? `Role: ${membership.role}` : 'No membership'}</div>
}

const PermissionTester = () => {
  const permissions = useOrgMembership()
  return (
    <div data-testid="permissions">
      {JSON.stringify({
        isOwner: permissions.isOwner,
        isAgent: permissions.isAgent,
        canManageTeam: permissions.canManageTeam,
        canAssignAgent: permissions.canAssignAgent,
        roleLabel: permissions.roleLabel
      })}
    </div>
  )
}

describe('OrgContext & useOrgMembership', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('provides membership data when user has an active membership', async () => {
    ;(database.auth.getUser as any).mockResolvedValue({ data: { user: { id: 'user-123' } } })
    ;(database.from as any)().single.mockResolvedValue({
      data: { id: 'm1', role: 'owner', status: 'active' },
      error: null
    })

    render(
      <OrgProvider>
        <TestComponent />
      </OrgProvider>
    )

    expect(screen.getByText('Loading...')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText('Role: owner')).toBeInTheDocument()
    })
  })

  it('sets membership to null if no organization found', async () => {
    ;(database.auth.getUser as any).mockResolvedValue({ data: { user: { id: 'user-123' } } })
    ;(database.from as any)().single.mockResolvedValue({
      data: null,
      error: { code: 'PGRST116', message: 'Not found' }
    })

    render(
      <OrgProvider>
        <TestComponent />
      </OrgProvider>
    )

    await waitFor(() => {
      expect(screen.getByText('No membership')).toBeInTheDocument()
    })
  })

  it('useOrgMembership returns correct permission flags', async () => {
    ;(database.auth.getUser as any).mockResolvedValue({ data: { user: { id: 'user-123' } } })
    ;(database.from as any)().single.mockResolvedValue({
      data: { id: 'm1', role: 'owner', status: 'active' },
      error: null
    })

    render(
      <OrgProvider>
        <PermissionTester />
      </OrgProvider>
    )

    await waitFor(() => {
      const raw = screen.getByTestId('permissions').textContent || '{}'
      const permissions = JSON.parse(raw)
      expect(permissions.isOwner).toBe(true)
      expect(permissions.canManageTeam).toBe(true)
      expect(permissions.roleLabel).toBe('Owner')
    })
  })

  it('useOrgMembership returns restricted flags for Agent', async () => {
    ;(database.auth.getUser as any).mockResolvedValue({ data: { user: { id: 'user-123' } } })
    ;(database.from as any)().single.mockResolvedValue({
      data: { id: 'm1', role: 'agent', status: 'active' },
      error: null
    })

    render(
      <OrgProvider>
        <PermissionTester />
      </OrgProvider>
    )

    await waitFor(() => {
      const raw = screen.getByTestId('permissions').textContent || '{}'
      const permissions = JSON.parse(raw)
      expect(permissions.isOwner).toBe(false)
      expect(permissions.isAgent).toBe(true)
      expect(permissions.canManageTeam).toBe(false)
      expect(permissions.canAssignAgent).toBe(false)
    })
  })
})
