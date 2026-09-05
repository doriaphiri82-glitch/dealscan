import { describe, expect, it } from 'vitest'
import { safeNext } from '../lib/safe-redirect'
import { isPublicSupabaseKey } from '../lib/supabase-config'

describe('internal auth redirects', () => {
  it.each([null, '', 'https://evil.example', '//evil.example', '/\\evil.example', '/%5cevil.example', '/%2f%2fevil.example', '/%252f%252fevil.example', '/\n/evil.example', '/%0d%0aevil', ' /dashboard', '/%', 'javascript:alert(1)'])('rejects %s', value => {
    expect(safeNext(value)).toBe('/my-dealscan')
  })
  it.each(['/dashboard', '/my-dealscan?tab=saved', '/deals/abc?county_id=county_az', '/deals#evidence'])('preserves %s', value => {
    expect(safeNext(value)).toBe(value)
  })
})

it('accepts only public Supabase key types', () => {
  const jwt = (role: string) => `header.${Buffer.from(JSON.stringify({ role })).toString('base64url')}.signature`
  expect(isPublicSupabaseKey(jwt('anon'))).toBe(true)
  expect(isPublicSupabaseKey('sb_publishable_test')).toBe(true)
  expect(isPublicSupabaseKey(jwt('service_role'))).toBe(false)
  expect(isPublicSupabaseKey('sb_secret_not_public')).toBe(false)
  expect(isPublicSupabaseKey('malformed')).toBe(false)
})
