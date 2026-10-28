import { generateKeyPairSync } from 'node:crypto'
import { describe, expect, it } from 'vitest'
import { buildNeonJwks } from '../src/lib/neon-jwks'

function createTestKeyPair() {
  const pair = generateKeyPairSync('ec', { namedCurve: 'prime256v1' })
  return {
    privateKey: pair.privateKey.export({ type: 'pkcs8', format: 'pem' }).toString(),
    privateJwk: pair.privateKey.export({ format: 'jwk' }),
    publicJwk: pair.publicKey.export({ format: 'jwk' }) as JsonWebKey,
  }
}

describe('Neon Data API JWKS', () => {
  it('preserves the existing single-key response', () => {
    const primary = createTestKeyPair()

    const result = buildNeonJwks(primary.privateKey, 'nexus-primary')

    expect(result.keys).toHaveLength(1)
    expect(result.keys[0]).toMatchObject({
      kid: 'nexus-primary',
      use: 'sig',
      alg: 'ES256',
      kty: 'EC',
      crv: 'P-256',
    })
    expect(result.keys[0]).not.toHaveProperty('d')
  })

  it('publishes an additional public signer without exposing private material', () => {
    const primary = createTestKeyPair()
    const renderSigner = createTestKeyPair()
    const additional = [{ ...renderSigner.publicJwk, kid: 'nexus-render-rotation' }]

    const result = buildNeonJwks(primary.privateKey, 'nexus-vercel', JSON.stringify(additional))

    expect(result.keys.map((key) => key.kid)).toEqual(['nexus-vercel', 'nexus-render-rotation'])
    expect(result.keys[1]).toMatchObject({ use: 'sig', alg: 'ES256', kty: 'EC', crv: 'P-256' })
    expect(result.keys.every((key) => !('d' in key))).toBe(true)
  })

  it('rejects duplicate key IDs', () => {
    const primary = createTestKeyPair()
    const extra = createTestKeyPair()

    expect(() => buildNeonJwks(
      primary.privateKey,
      'duplicate-id',
      JSON.stringify([{ ...extra.publicJwk, kid: 'duplicate-id' }]),
    )).toThrow('Neon JWKS contains duplicate key IDs')
  })

  it('rejects private material in the additional public-key configuration', () => {
    const primary = createTestKeyPair()
    const extra = createTestKeyPair()
    expect(() => buildNeonJwks(
      primary.privateKey,
      'nexus-primary',
      JSON.stringify([{ ...extra.publicJwk, ...extra.privateJwk, kid: 'must-not-be-private' }]),
    )).toThrow('Neon JWKS additional keys must contain public material only')
  })

  it('rejects malformed JSON and non-P-256 public keys', () => {
    const primary = createTestKeyPair()
    const rsa = generateKeyPairSync('rsa', { modulusLength: 2048 })
    const rsaJwk = rsa.publicKey.export({ format: 'jwk' }) as JsonWebKey

    expect(() => buildNeonJwks(primary.privateKey, 'nexus-primary', '{')).toThrow(
      'Neon JWKS additional keys must be a JSON array',
    )
    expect(() => buildNeonJwks(
      primary.privateKey,
      'nexus-primary',
      JSON.stringify([{ ...rsaJwk, kid: 'rsa-key' }]),
    )).toThrow('Neon JWKS additional keys must be EC P-256 public keys')
  })
})
