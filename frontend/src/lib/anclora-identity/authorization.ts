export const NEXUS_APPLICATION_ID = 'anclora-nexus'

export interface AncloraIdentityClaims {
  sub: string
  name?: string
  email?: string
  email_verified?: boolean
  platform_roles?: string[]
  application_memberships?: string[]
}

export function hasNexusApplicationAccess(claims: AncloraIdentityClaims): boolean {
  return (claims.platform_roles ?? []).includes('GROUP_OWNER') ||
    (claims.application_memberships ?? []).includes(NEXUS_APPLICATION_ID)
}
