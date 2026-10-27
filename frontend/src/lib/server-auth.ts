import type { OrgMembership } from '@/lib/contexts/OrgContext'
import { getNexusIdentitySession } from '@/lib/anclora-identity/session'

export async function fetchUserAndOrg() {
  const session = await getNexusIdentitySession()
  if (!session) return { user: null, membership: null, orgId: null }
  const user = {
    id: session.userId,
    email: session.email,
    user_metadata: { full_name: session.name, avatar_url: session.avatarUrl },
    app_metadata: { provider: 'anclora-identity' },
  }
  const membership = { org_id: session.orgId, role: session.orgRole, user_id: session.userId, status: 'active' } as OrgMembership
  return { user, membership, orgId: session.orgId }
}
