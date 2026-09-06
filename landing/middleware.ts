import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'
import { publicSupabaseConfig } from './lib/supabase-config'

export async function middleware(request: NextRequest) {
  let response = NextResponse.next({ request })
  const config = publicSupabaseConfig()
  let signedIn = false
  if (config) {
    try {
      const supabase = createServerClient(config.url, config.key, {
        global: { fetch: (url, init) => fetch(url, { ...init, redirect: 'error', cache: 'no-store', signal: AbortSignal.timeout(8000) }) },
        cookies: {
          getAll: () => request.cookies.getAll(),
          setAll(cookiesToSet) {
            // Refreshed tokens must be visible to downstream Server Components.
            cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value))
            const previousCookies = response.cookies.getAll()
            response = NextResponse.next({ request })
            previousCookies.forEach(cookie => response.cookies.set(cookie))
            cookiesToSet.forEach(({ name, value, options }) => response.cookies.set(name, value, options))
          },
        },
      })
      const { data: { user }, error } = await supabase.auth.getUser()
      signedIn = !error && !!user
    } catch { /* Fail closed when session verification is unavailable. */ }
  }
  if (!signedIn) {
    if (request.nextUrl.pathname.startsWith('/api/')) {
      const denied=NextResponse.json({error:'Authentication required'},{status:401,headers:{'Cache-Control':'private, no-store'}})
      response.cookies.getAll().forEach(cookie=>denied.cookies.set(cookie))
      return denied
    }
    const url = request.nextUrl.clone()
    url.pathname = '/auth'
    url.search = ''
    url.searchParams.set('next', request.nextUrl.pathname + request.nextUrl.search)
    if (!config) url.searchParams.set('error', 'auth_unavailable')
    const redirect = NextResponse.redirect(url)
    response.cookies.getAll().forEach(cookie => redirect.cookies.set(cookie))
    redirect.headers.set('Cache-Control', 'private, no-store')
    return redirect
  }
  response.headers.set('Cache-Control', 'private, no-store')
  return response
}

// Public APIs/pages must still work when authentication is unconfigured or down.
export const config = {
  matcher: ['/dashboard/:path*', '/my-dealscan/:path*', '/admin/:path*', '/api/admin/:path*'],
}
