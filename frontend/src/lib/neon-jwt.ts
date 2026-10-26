import 'server-only'
import { createPrivateKey, createSign, randomUUID } from 'node:crypto'

type NeonRole = 'anonymous' | 'authenticated' | 'service_role'

function base64Url(value: Buffer | string) {
  return Buffer.from(value).toString('base64url')
}

export function createNeonJwt(role: NeonRole, subject: string, ttlSeconds = 300) {
  const privateKeyPem = process.env.NEON_JWT_PRIVATE_KEY?.replace(/\\n/g, '\n')
  const keyId = process.env.NEON_JWT_KEY_ID
  if (!privateKeyPem || !keyId) {
    throw new Error('Neon JWT signing is not configured')
  }
  const parsedKey = createPrivateKey(privateKeyPem)
  if (
    parsedKey.asymmetricKeyType !== 'ec' ||
    parsedKey.asymmetricKeyDetails?.namedCurve !== 'prime256v1'
  ) {
    throw new Error('Neon JWT signing key must be an EC P-256 private key')
  }
  if (ttlSeconds < 30 || ttlSeconds > 3600) {
    throw new Error('Neon JWT lifetime must be between 30 and 3600 seconds')
  }

  const now = Math.floor(Date.now() / 1000)
  const audience = process.env.NEON_JWT_AUDIENCE || 'authenticated'
  const issuer = process.env.NEON_JWT_ISSUER || 'anclora-nexus'
  const header = { alg: 'ES256', typ: 'JWT', kid: keyId }
  const claims = {
    iss: issuer,
    aud: audience,
    sub: subject || randomUUID(),
    role,
    iat: now,
    exp: now + ttlSeconds,
  }
  const input = `${base64Url(JSON.stringify(header))}.${base64Url(JSON.stringify(claims))}`
  const signer = createSign('SHA256')
  signer.update(input)
  signer.end()
  const signature = signer.sign({ key: privateKeyPem, dsaEncoding: 'ieee-p1363' })
  return { token: `${input}.${base64Url(signature)}`, expiresAt: claims.exp }
}
