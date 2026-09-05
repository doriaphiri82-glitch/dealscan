export function isPublicSupabaseKey(key: string): boolean {
  if (key.startsWith('sb_publishable_')) return true
  try {
    const payload = JSON.parse(atob(key.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    return payload.role === 'anon'
  } catch {
    return false
  }
}

/** Uses only browser-safe credentials; never falls back to a service-role key. */
export function publicSupabaseConfig(): { url: string; key: string } | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  if (!url || !key || !isPublicSupabaseKey(key)) return null
  try {
    const parsed = new URL(url)
    const local = ['localhost', '127.0.0.1', '[::1]'].includes(parsed.hostname)
    if (parsed.protocol !== 'https:' && !(parsed.protocol === 'http:' && local)) return null
    if (parsed.username || parsed.password || parsed.search || parsed.hash || parsed.pathname !== '/') return null
    return { url: parsed.origin, key }
  } catch {
    return null
  }
}
