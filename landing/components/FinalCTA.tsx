'use client'

import { useState, FormEvent } from 'react'

export default function FinalCTA() {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) { setStatus('error'); setMessage('Please enter a valid email address.'); return }
    setStatus('loading')
    try {
      const res = await fetch('/api/waitlist', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, source: 'final_cta' }) })
      const data = await res.json()
      if (res.ok) { setStatus('success'); setMessage("You're on the list. We'll be in touch when early access opens."); setEmail('') }
      else { setStatus('error'); setMessage(data.error || 'Something went wrong. Please try again.') }
    } catch { setStatus('error'); setMessage('Network error. Please try again.') }
  }

  return (
    <section className="py-28 px-6 md:px-8" id="early-access">
      <div className="max-w-[760px] mx-auto" data-reveal>
        <div className="relative overflow-hidden rounded-[28px] border border-[#cfded4] bg-[#eaf3ed] px-6 py-14 md:px-12 md:py-16 text-center shadow-[0_24px_60px_rgba(31,61,47,0.08)]">
          <div className="absolute inset-0 parcel-grid opacity-40" aria-hidden="true" />
          <div className="absolute -top-24 -right-20 h-56 w-56 rounded-full bg-white/70 blur-3xl" aria-hidden="true" />
          <div className="relative">
            <p className="font-mono text-[11px] font-semibold tracking-[0.12em] uppercase text-brand-500 mb-4">Early Access</p>
            <h2 className="text-3xl md:text-4xl font-bold tracking-[-0.02em] text-[#15211b] mb-4">Spend less time assembling the deal. More time evaluating it.</h2>
            <p className="text-[16px] text-[#64716a] leading-[1.75] mb-9 max-w-[590px] mx-auto">Join the waitlist for early access to DealScan. Free tier available at launch — no credit card required.</p>
            <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-2.5 max-w-[470px] mx-auto">
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@email.com" className="flex-1 px-4 py-3.5 rounded-xl bg-white border border-[#cfdad3] text-[#26352d] placeholder-[#9aa69f] text-sm shadow-sm focus:outline-none focus:border-[#176b45] focus:ring-[3px] focus:ring-[#176b45]/10 transition-colors" aria-label="Email address" />
              <button type="submit" disabled={status === 'loading'} className="px-6 py-3.5 rounded-xl bg-[#176b45] hover:bg-[#0f5637] text-white text-sm font-medium shadow-[0_8px_20px_rgba(23,107,69,0.18)] transition-all hover:-translate-y-px disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap">{status === 'loading' ? 'Joining...' : 'Get early access'}</button>
            </form>
            {message && <p role="status" aria-live="polite" className={`mt-4 text-[13px] font-medium ${status === 'success' ? 'text-[#176b45]' : 'text-red-600'}`}>{message}</p>}
          </div>
        </div>
      </div>
    </section>
  )
}
