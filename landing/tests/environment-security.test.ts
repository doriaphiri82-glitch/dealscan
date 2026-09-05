import { expect, it, vi } from 'vitest'
import { checkPublicEnvironment } from '../scripts/check-public-env.cjs'
import { isPublicSupabaseKey, publicSupabaseConfig } from '../lib/supabase-config'
import { privateSupabaseConfig } from '../lib/supabase-private'
const token=(role:string)=>`header.${Buffer.from(JSON.stringify({role})).toString('base64url')}.signature`

it.each(['sb_secret_ephemeral_marker',token('service_role'),token('authenticated'),`Bearer ${token('service_role')}`,JSON.stringify({key:'sb_secret_ephemeral_marker'})])('blocks private credentials even under an innocuous public variable name',value=>{
  expect(()=>checkPublicEnvironment({NEXT_PUBLIC_CONFIGURATION:value})).toThrow(/privileged credential/)
  try{checkPublicEnvironment({NEXT_PUBLIC_CONFIGURATION:value})}catch(error){expect(String(error)).not.toContain(value)}
})

it('allows ordinary public settings and anon keys without requiring production secrets',()=>{
  expect(()=>checkPublicEnvironment({NEXT_PUBLIC_THEME:'green',NEXT_PUBLIC_SUPABASE_ANON_KEY:token('anon')})).not.toThrow()
  expect(()=>checkPublicEnvironment({WAITLIST_CONTACT_EMAIL:'doriaphiri82@gmail.com'})).not.toThrow()
})

it.each(['sb_publishable_','header..signature',`header.${Buffer.from('{"role":"anon"}').toString('base64url')}`,`header.${Buffer.from('{"role":"anon"}').toString('base64url')}.`])('rejects malformed public key structure: %s',value=>{
  expect(isPublicSupabaseKey(value)).toBe(false)
  expect(()=>checkPublicEnvironment({NEXT_PUBLIC_SUPABASE_ANON_KEY:value})).toThrow()
})

it.each(['http://localhost:54321','https://localhost','http://127.1','https://127.0.0.2','https://[::1]','https://preview.localhost','https://0.0.0.0'])('production browser configuration never targets local services: %s',url=>{
  vi.stubEnv('NODE_ENV','production')
  vi.stubEnv('NEXT_PUBLIC_SUPABASE_URL',url)
  vi.stubEnv('NEXT_PUBLIC_SUPABASE_ANON_KEY','sb_publishable_ephemeral')
  expect(publicSupabaseConfig()).toBeNull()
})

it('permits an explicitly local development emulator without allowing remote plaintext HTTP',()=>{
  vi.stubEnv('NODE_ENV','development');vi.stubEnv('NEXT_PUBLIC_SUPABASE_ANON_KEY','sb_publishable_ephemeral')
  vi.stubEnv('NEXT_PUBLIC_SUPABASE_URL','http://localhost:54321')
  expect(publicSupabaseConfig()?.url).toBe('http://localhost:54321')
  vi.stubEnv('NEXT_PUBLIC_SUPABASE_URL','http://remote.example')
  expect(publicSupabaseConfig()).toBeNull()
})

it('private operations do not accept empty secret-key prefixes or malformed JWTs',()=>{
  vi.stubEnv('SUPABASE_URL','https://database.example')
  vi.stubEnv('NEXT_PUBLIC_SUPABASE_URL','https://database.example')
  for(const value of ['sb_secret_',`.${Buffer.from('{"role":"service_role"}').toString('base64url')}.`]){
    vi.stubEnv('SUPABASE_SERVICE_ROLE_KEY',value)
    expect(()=>privateSupabaseConfig()).toThrow(/not configured/)
  }
})
