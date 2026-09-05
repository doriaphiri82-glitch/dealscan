import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

function safeNext(value: string | null): string {
  if (!value || !value.startsWith('/') || value.startsWith('//')) return '/my-dealscan'
  return value
}

export async function GET(request: Request) {
  const requestUrl = new URL(request.url)
  const code = requestUrl.searchParams.get('code')
  const next = safeNext(requestUrl.searchParams.get('next'))

  if (!code) return NextResponse.redirect(new URL('/auth?error=missing_code', requestUrl.origin))

  const cookieStore = await cookies()
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() { return cookieStore.getAll() },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) => cookieStore.set(name, value, options))
        },
      },
    }
  )

  const { error } = await supabase.auth.exchangeCodeForSession(code)
  if (error) return NextResponse.redirect(new URL(`/auth?error=callback_failed&next=${encodeURIComponent(next)}`, requestUrl.origin))

  return NextResponse.redirect(new URL(next, requestUrl.origin))
}
