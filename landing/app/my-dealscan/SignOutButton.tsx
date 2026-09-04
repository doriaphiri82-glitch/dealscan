'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { createSupabaseBrowserClient } from '@/lib/supabase-browser'

export default function SignOutButton() {
  const router = useRouter()
  const [busy, setBusy] = useState(false)
  const signOut = async () => {
    setBusy(true)
    const supabase = createSupabaseBrowserClient()
    await supabase.auth.signOut()
    router.push('/deals')
    router.refresh()
  }
  return <button onClick={signOut} disabled={busy} className="rounded-lg border border-[#d7e1db] px-3 py-2 text-xs font-bold text-[#34433b] hover:border-[#b9cfc1] disabled:opacity-50">{busy ? 'Signing out…' : 'Sign out'}</button>
}
