import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { safeNext } from '@/lib/safe-redirect'
import { publicSupabaseConfig } from '@/lib/supabase-config'

export async function GET(request: Request) {
  const requestUrl = new URL(request.url)
  const code = requestUrl.searchParams.get('code')
  const next = safeNext(requestUrl.searchParams.get('next'))
  const redirect = (path: string) => {
    const response = NextResponse.redirect(new URL(path, requestUrl.origin))
    response.headers.set('Cache-Control', 'private, no-store')
    return response
  }
  if (!code) return redirect('/auth?error=missing_code')
  const config = publicSupabaseConfig()
  if (!config) return redirect('/auth?error=auth_unavailable')
  try {
    const cookieStore = await cookies()
    const supabase = createServerClient(config.url, config.key, {
      global: { fetch: (url, init) => fetch(url, { ...init, signal: AbortSignal.timeout(8000) }) },
      cookies: {
        getAll: () => cookieStore.getAll(),
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) => cookieStore.set(name, value, options))
        },
      },
    })
    const { error } = await supabase.auth.exchangeCodeForSession(code)
    if (error) return redirect(`/auth?error=callback_failed&next=${encodeURIComponent(next)}`)
    return redirect(next)
  } catch {
    return redirect(`/auth?error=callback_failed&next=${encodeURIComponent(next)}`)
  }
}
