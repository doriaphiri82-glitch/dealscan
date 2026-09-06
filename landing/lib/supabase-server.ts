import 'server-only'
import { cookies } from 'next/headers'
import { createServerClient } from '@supabase/ssr'
import { publicSupabaseConfig } from './supabase-config'

/** Server-side authorization remains mandatory even if middleware is bypassed. */
export async function currentUser() {
  const config = publicSupabaseConfig()
  if (!config) return null
  try {
    const cookieStore = await cookies()
    const supabase = createServerClient(config.url, config.key, {
      global: { fetch: (url, init) => fetch(url, { ...init, redirect: 'error', cache: 'no-store', signal: AbortSignal.timeout(8000) }) },
      cookies: { getAll: () => cookieStore.getAll(), setAll: () => {} },
    })
    const { data: { user }, error } = await supabase.auth.getUser()
    return error ? null : user
  } catch { return null }
}
