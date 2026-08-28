'use client'

import { useState, FormEvent } from 'react'

export default function FinalCTA() {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setStatus('error')
      setMessage('Please enter a valid email address.')
      return
    }
    setStatus('loading')
    try {
      const res = await fetch('/api/waitlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, source: 'final_cta' }),
      })
      const data = await res.json()
      if (res.ok) {
        setStatus('success')
        setMessage("You're on the list. We'll be in touch when early access opens.")
        setEmail('')
      } else {
        setStatus('error')
        setMessage(data.error || 'Something went wrong. Please try again.')
      }
    } catch {
      setStatus('error')
      setMessage('Network error. Please try again.')
    }
  }

  return (
    <section className="py-32 px-6 md:px-8 text-center bg-[#111113] border-y border-white/[0.06]" id="early-access">
      <div className="max-w-[680px] mx-auto" data-reveal>
        <p className="font-mono text-[11px] font-semibold tracking-[0.12em] uppercase text-brand-500 mb-4">Early Access</p>
        <h2 className="text-3xl md:text-4xl font-bold tracking-[-0.02em] mb-4">
          Get early access.
        </h2>
        <p className="text-[17px] text-[#A1A1AA] leading-[1.75] mb-9">
          Join the waitlist for early access to DealScan. Free tier available at launch — no credit card required.
        </p>

        <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-2.5 max-w-[420px] mx-auto">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@email.com"
            className="flex-1 px-4 py-3 rounded-md bg-[#161618] border border-white/10 text-white placeholder-[#52525B] text-sm focus:outline-none focus:border-brand-600 focus:ring-[3px] focus:ring-brand-500/[0.08] transition-colors"
            aria-label="Email address"
          />
          <button
            type="submit"
            disabled={status === 'loading'}
            className="px-6 py-3 rounded-md bg-brand-600 hover:bg-brand-500 text-white text-sm font-medium transition-all hover:-translate-y-px disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
          >
            {status === 'loading' ? 'Joining...' : 'Get early access'}
          </button>
        </form>

        {message && (
          <p role="status" aria-live="polite" className={`mt-4 text-[13px] font-medium ${status === 'success' ? 'text-brand-500' : 'text-red-500'}`}>
            {message}
          </p>
        )}
      </div>
    </section>
  )
}
