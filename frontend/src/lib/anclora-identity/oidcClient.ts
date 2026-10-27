import * as client from 'openid-client'
import { getAncloraIdentityConfig } from './env'

let cachedConfig: client.Configuration | undefined

export async function getAncloraIdentityOidcConfig(): Promise<client.Configuration> {
  if (cachedConfig) return cachedConfig
  const { issuerUrl, clientId, clientSecret } = getAncloraIdentityConfig()
  cachedConfig = await client.discovery(new URL(issuerUrl), clientId, clientSecret, client.ClientSecretBasic(clientSecret))
  return cachedConfig
}

export function buildLoginRedirect(config: client.Configuration, input: { redirectUri: string; state: string; codeChallenge: string }) {
  return client.buildAuthorizationUrl(config, {
    redirect_uri: input.redirectUri,
    scope: 'openid profile email anclora_platform',
    code_challenge: input.codeChallenge,
    code_challenge_method: 'S256',
    state: input.state,
  })
}

export const randomPKCECodeVerifier = client.randomPKCECodeVerifier
export const calculatePKCECodeChallenge = client.calculatePKCECodeChallenge
export const randomState = client.randomState
export const authorizationCodeGrant = client.authorizationCodeGrant
export const fetchUserInfo = client.fetchUserInfo
