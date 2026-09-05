import 'server-only'

export class PrivateStoreUnavailable extends Error {}

/** Private write credentials are never imported into browser code. */
export function privateSupabaseConfig(): { url: string; key: string } {
  const url = process.env.SUPABASE_URL
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY
  try {
    if (!url || !key) throw new Error()
    const parsed = new URL(url)
    if (parsed.protocol !== 'https:' || parsed.username || parsed.password || parsed.search || parsed.hash || parsed.pathname !== '/') throw new Error()
    const publicUrl=process.env.NEXT_PUBLIC_SUPABASE_URL
    if (publicUrl && new URL(publicUrl).origin !== parsed.origin) throw new Error()
    if (!key.startsWith('sb_secret_')) {
      const parts = key.split('.')
      if (parts.length !== 3 || JSON.parse(Buffer.from(parts[1], 'base64url').toString()).role !== 'service_role') throw new Error()
    }
    return { url: parsed.origin, key }
  } catch { throw new PrivateStoreUnavailable('Private database not configured') }
}

/** Fixed RPC allowlist, no arbitrary URLs, redirects or private error bodies. */
export async function privateRpc(name: 'join_waitlist' | 'county_operational_snapshot', body: Record<string, unknown>): Promise<unknown> {
  const config = privateSupabaseConfig()
  const headers: Record<string, string> = { apikey: config.key, 'Content-Type': 'application/json' }
  if (!config.key.startsWith('sb_secret_')) headers.Authorization = `Bearer ${config.key}`
  try {
    const response = await fetch(`${config.url}/rest/v1/rpc/${name}`, {
      method: 'POST', headers, body: JSON.stringify(body), cache: 'no-store',
      redirect: 'error', signal: AbortSignal.timeout(8000),
    })
    if (!response.ok) throw new Error()
    return await response.json() as unknown
  } catch { throw new PrivateStoreUnavailable('Private database unavailable') }
}
