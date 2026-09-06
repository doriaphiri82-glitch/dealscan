'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { createSupabaseBrowserClient } from '@/lib/supabase-browser'

export default function SignOutButton() {
  const router = useRouter()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const signOut = async () => {
    setBusy(true)
    setError('')
    try {
      const supabase = createSupabaseBrowserClient()
      const { error } = await supabase.auth.signOut()
      if (error) throw error
      router.push('/deals')
      router.refresh()
    } catch { setError('Sign-out failed. Please try again.') }
    finally { setBusy(false) }
  }
  return <div><button onClick={signOut} disabled={busy} className="rounded-lg border border-[#d7e1db] px-3 py-2 text-xs font-bold text-[#34433b] hover:border-[#b9cfc1] disabled:opacity-50">{busy ? 'Signing out…' : 'Sign out'}</button>{error && <p role="alert" className="mt-2 text-xs text-red-700">{error}</p>}</div>
}
