export function isAncloraIdentityEnabled(): boolean {
  const serverEnabled = process.env.ANCLORA_IDENTITY_ENABLED === 'true'
  const browserEnabled = process.env.NEXT_PUBLIC_ANCLORA_IDENTITY_ENABLED === 'true'
  if (serverEnabled !== browserEnabled) {
    throw new Error('ANCLORA_IDENTITY_ENABLED and NEXT_PUBLIC_ANCLORA_IDENTITY_ENABLED must match')
  }
  return serverEnabled
}

export interface AncloraIdentityConfig {
  issuerUrl: string
  clientId: string
  clientSecret: string
  redirectUri: string
  sessionSecret: string
}

export function getAncloraIdentityConfig(): AncloraIdentityConfig {
  const values = {
    issuerUrl: process.env.ANCLORA_IDENTITY_ISSUER_URL?.trim(),
    clientId: process.env.ANCLORA_IDENTITY_CLIENT_ID?.trim(),
    clientSecret: process.env.ANCLORA_IDENTITY_CLIENT_SECRET?.trim(),
    redirectUri: process.env.ANCLORA_IDENTITY_REDIRECT_URI?.trim(),
    sessionSecret: process.env.ANCLORA_IDENTITY_SESSION_SECRET?.trim(),
  }
  const missing = Object.entries(values).filter(([, value]) => !value).map(([key]) => key)
  if (missing.length) {
    throw new Error(`ANCLORA_IDENTITY_ENABLED=true but missing configuration: ${missing.join(', ')}`)
  }
  return values as AncloraIdentityConfig
}
