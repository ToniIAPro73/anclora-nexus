import { createPublicKey } from 'node:crypto'

type PublishedJwk = JsonWebKey & {
  kid: string
  use: 'sig'
  alg: 'ES256'
}

type NeonJwks = { keys: PublishedJwk[] }

const MAX_ADDITIONAL_PUBLIC_KEYS = 10

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function publishedPublicKey(key: JsonWebKey, kid: string): PublishedJwk {
  return { ...key, kid, use: 'sig', alg: 'ES256' }
}

function parseAdditionalPublicKeys(raw: string | undefined, primaryKid: string): PublishedJwk[] {
  if (!raw?.trim()) return []

  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    throw new Error('Neon JWKS additional keys must be a JSON array')
  }

  if (!Array.isArray(parsed) || parsed.length > MAX_ADDITIONAL_PUBLIC_KEYS) {
    throw new Error('Neon JWKS additional keys must be a JSON array of at most 10 keys')
  }

  const keyIds = new Set([primaryKid])
  return parsed.map((candidate): PublishedJwk => {
    if (!isRecord(candidate)) {
      throw new Error('Neon JWKS additional keys must be EC P-256 public keys')
    }
    if ('d' in candidate || 'p' in candidate || 'q' in candidate || 'dp' in candidate || 'dq' in candidate || 'qi' in candidate) {
      throw new Error('Neon JWKS additional keys must contain public material only')
    }

    const kid = typeof candidate.kid === 'string' ? candidate.kid.trim() : ''
    if (!kid || kid.length > 128) {
      throw new Error('Neon JWKS additional keys require a valid kid')
    }
    if (keyIds.has(kid)) {
      throw new Error('Neon JWKS contains duplicate key IDs')
    }

    if (candidate.kty !== 'EC' || candidate.crv !== 'P-256' || typeof candidate.x !== 'string' || typeof candidate.y !== 'string') {
      throw new Error('Neon JWKS additional keys must be EC P-256 public keys')
    }

    try {
      const publicKey = createPublicKey({
        key: {
          kty: 'EC',
          crv: 'P-256',
          x: candidate.x,
          y: candidate.y,
        },
        format: 'jwk',
      })
      if (publicKey.asymmetricKeyType !== 'ec' || publicKey.asymmetricKeyDetails?.namedCurve !== 'prime256v1') {
        throw new Error('invalid curve')
      }

      const exported = publicKey.export({ format: 'jwk' }) as JsonWebKey
      keyIds.add(kid)
      return publishedPublicKey(exported, kid)
    } catch {
      throw new Error('Neon JWKS additional keys must be valid EC P-256 public keys')
    }
  })
}

export function buildNeonJwks(
  privateKeyPem: string,
  keyId: string,
  additionalPublicKeysJson?: string,
): NeonJwks {
  if (!privateKeyPem || !keyId.trim()) {
    throw new Error('Neon JWT signing is not configured')
  }

  const privateKey = privateKeyPem.replace(/\\n/g, '\n')
  const primaryPublicKey = createPublicKey(privateKey)
  if (primaryPublicKey.asymmetricKeyType !== 'ec' || primaryPublicKey.asymmetricKeyDetails?.namedCurve !== 'prime256v1') {
    throw new Error('Neon JWT signing key must be an EC P-256 key')
  }

  const primaryJwk = primaryPublicKey.export({ format: 'jwk' }) as JsonWebKey
  const primary = publishedPublicKey(primaryJwk, keyId)
  const additional = parseAdditionalPublicKeys(additionalPublicKeysJson, keyId)
  return { keys: [primary, ...additional] }
}
