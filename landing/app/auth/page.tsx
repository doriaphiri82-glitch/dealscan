'use client'

import { FormEvent, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { createSupabaseBrowserClient } from '@/lib/supabase-browser'

function safeNext(value: string | null): string {
  if (!value || !value.startsWith('/') || value.startsWith('//')) return '/my-dealscan'
  return value
}

export default function AuthPage() {
  const router = useRouter()
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [nextPath, setNextPath] = useState('/my-dealscan')

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    setNextPath(safeNext(params.get('next')))
    if (params.get('error')) setError('We could not complete that sign-in. Please try again.')
  }, [])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const supabase = createSupabaseBrowserClient()
      const result = mode === 'signin'
        ? await supabase.auth.signInWithPassword({ email, password })
        : await supabase.auth.signUp({ email, password, options: { emailRedirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(nextPath)}` } })
      if (result.error) throw result.error
      if (mode === 'signup' && !result.data.session) {
        setMessage('Check your email to confirm your account, then come back to DealScan.')
      } else {
        router.push(nextPath)
        router.refresh()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  const google = async () => {
    setBusy(true)
    setError('')
    try {
      const supabase = createSupabaseBrowserClient()
      const { error: authError } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: { redirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(nextPath)}` },
      })
      if (authError) throw authError
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Google sign-in failed. Please try again.')
      setBusy(false)
    }
  }

  return (
    <main className="min-h-screen bg-[#f7f9f7] px-4 py-10 sm:px-6 lg:px-8">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-6xl items-center justify-center">
        <div className="grid w-full overflow-hidden rounded-[30px] border border-[#dbe5df] bg-white shadow-[0_28px_80px_rgba(25,49,38,.12)] lg:grid-cols-[1.05fr_.95fr]">
          <section className="hidden bg-[#eef5f0] p-10 lg:flex lg:flex-col lg:justify-between xl:p-14">
            <div>
              <a href="/" className="text-xl font-black tracking-[-.04em] text-[#153025]">Deal<span className="text-[#176b45]">Scan</span></a>
              <div className="mt-20 max-w-md">
                <p className="font-mono text-[10px] font-bold uppercase tracking-[.14em] text-[#176b45]">Land deal intelligence</p>
                <h1 className="mt-4 text-4xl font-black leading-tight tracking-[-.04em] text-[#15211b]">Your research desk for land deals.</h1>
                <p className="mt-5 text-base leading-7 text-[#64716a]">Save the properties worth a closer look, return to your research, and keep your screening workflow in one place.</p>
              </div>
            </div>
            <p className="font-mono text-[9px] uppercase tracking-[.1em] text-[#8a958f]">Discover · Understand · Verify · Act</p>
          </section>

          <section className="p-6 sm:p-10 xl:p-14">
            <div className="mb-8 lg:hidden"><a href="/" className="text-xl font-black tracking-[-.04em] text-[#153025]">Deal<span className="text-[#176b45]">Scan</span></a></div>
            <div className="mb-7">
              <p className="font-mono text-[10px] font-bold uppercase tracking-[.14em] text-[#176b45]">{mode === 'signin' ? 'Welcome back' : 'Create your account'}</p>
              <h2 className="mt-2 text-3xl font-black tracking-[-.04em] text-[#15211b]">{mode === 'signin' ? 'Sign in to DealScan' : 'Start your DealScan workspace'}</h2>
              <p className="mt-2 text-sm leading-6 text-[#69766f]">No early-access gate. Create an account or sign in to continue.</p>
            </div>

            <button type="button" onClick={google} disabled={busy} className="flex w-full items-center justify-center gap-3 rounded-xl border border-[#d7e1db] bg-white px-4 py-3 text-sm font-bold text-[#26362e] transition hover:-translate-y-0.5 hover:border-[#b9cfc1] hover:shadow-sm disabled:cursor-not-allowed disabled:opacity-60">
              <span className="grid h-6 w-6 place-items-center rounded-full border border-[#dfe6e1] text-xs font-black">G</span>
              Continue with Google
            </button>

            <div className="my-6 flex items-center gap-3"><div className="h-px flex-1 bg-[#e8edea]"/><span className="font-mono text-[9px] uppercase tracking-[.1em] text-[#9aa49e]">or email</span><div className="h-px flex-1 bg-[#e8edea]"/></div>

            <form onSubmit={submit} className="space-y-4">
              <label className="block"><span className="mb-1.5 block text-xs font-bold text-[#34433b]">Email</span><input type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} className="w-full rounded-xl border border-[#d7e1db] bg-[#fbfcfb] px-4 py-3 text-sm text-[#15211b] outline-none transition focus:border-[#176b45] focus:ring-4 focus:ring-[#176b45]/10" placeholder="you@example.com" /></label>
              <label className="block"><span className="mb-1.5 block text-xs font-bold text-[#34433b]">Password</span><input type="password" autoComplete={mode === 'signin' ? 'current-password' : 'new-password'} required minLength={6} value={password} onChange={e => setPassword(e.target.value)} className="w-full rounded-xl border border-[#d7e1db] bg-[#fbfcfb] px-4 py-3 text-sm text-[#15211b] outline-none transition focus:border-[#176b45] focus:ring-4 focus:ring-[#176b45]/10" placeholder="At least 6 characters" /></label>
              {error && <p role="alert" className="rounded-xl border border-[#ecd5d0] bg-[#fff7f5] px-3 py-2.5 text-xs font-semibold text-[#9a4c3d]">{error}</p>}
              {message && <p role="status" className="rounded-xl border border-[#cfe1d6] bg-[#eef7f1] px-3 py-2.5 text-xs font-semibold text-[#176b45]">{message}</p>}
              <button disabled={busy} className="w-full rounded-xl bg-[#153025] px-4 py-3.5 text-sm font-bold text-white shadow-[0_10px_24px_rgba(21,48,37,.14)] transition hover:-translate-y-0.5 hover:bg-[#176b45] disabled:cursor-not-allowed disabled:opacity-60">{busy ? 'Please wait…' : mode === 'signin' ? 'Sign in →' : 'Create account →'}</button>
            </form>

            <button type="button" onClick={() => { setMode(mode === 'signin' ? 'signup' : 'signin'); setError(''); setMessage('') }} className="mt-6 w-full text-center text-xs font-bold text-[#176b45] hover:underline">{mode === 'signin' ? 'New to DealScan? Create an account' : 'Already have an account? Sign in'}</button>
          </section>
        </div>
      </div>
    </main>
  )
}
