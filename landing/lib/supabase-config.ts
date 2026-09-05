export function isPublicSupabaseKey(key: string): boolean {
  if (/^sb_publishable_[A-Za-z0-9_-]+$/.test(key)) return true
  try {
    const parts=key.split('.')
    if(parts.length!==3||!parts.every(part=>/^[A-Za-z0-9_-]+$/.test(part)))return false
    const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')))
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
    const host=parsed.hostname.toLowerCase().replace(/\.$/,'')
    const local = host==='localhost'||host.endsWith('.localhost')||host.startsWith('127.')||['0.0.0.0','[::]','[::1]'].includes(host)||/^\[::ffff:7f[0-9a-f]{2}:/.test(host)
    if(local&&process.env.NODE_ENV==='production')return null
    if (parsed.protocol !== 'https:' && !(parsed.protocol === 'http:' && local && process.env.NODE_ENV==='development')) return null
    if (parsed.username || parsed.password || parsed.search || parsed.hash || parsed.pathname !== '/') return null
    return { url: parsed.origin, key }
  } catch {
    return null
  }
}
