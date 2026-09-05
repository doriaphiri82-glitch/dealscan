import { createBrowserClient } from '@supabase/ssr'
import { publicSupabaseConfig } from './supabase-config'

export function createSupabaseBrowserClient() {
  const config = publicSupabaseConfig()
  if (!config) throw new Error('Sign-in is temporarily unavailable. Please try again later.')
  return createBrowserClient(config.url, config.key)
}
