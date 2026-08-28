'use client'

import { useState, useEffect, useRef, FormEvent } from 'react'

const SCORE_FINAL = 87
/* Order per design spec: VALUE, MARKET, SELLER, ACCESS, RISK */
const scoreBars = [
  { label: 'Value', val: 91 },
  { label: 'Market', val: 79 },
  { label: 'Seller', val: 84 },
  { label: 'Access', val: 72 },
  { label: 'Risk', val: 88 },
]

const signals = [
  { text: 'Below comparable pricing', warn: false },
  { text: 'Absentee ownership', warn: false },
  { text: 'Long ownership history', warn: false },
  { text: 'Tax history requires review', warn: true },
]

const riskChecks = [
  { text: 'Verify legal access', warn: true },
  { text: 'Confirm utilities availability', warn: true },
  { text: 'Zoning appears compatible', warn: false },
]

export default function Hero() {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')
  /* Staged analysis sequence: 0 hidden → 8 settled */
  const [stage, setStage] = useState(0)
  const [score, setScore] = useState(0)
  const barsRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (prefersReduced) {
      setStage(8)
      setScore(SCORE_FINAL)
      return
    }

    const timers: ReturnType<typeof setTimeout>[] = []
    const at = (ms: number, fn: () => void) => timers.push(setTimeout(fn, ms))

    // 1. panel fades in
    at(150, () => setStage(1))
    // 2. property identity appears
    at(500, () => setStage(2))
    // 3. metrics appear
    at(900, () => setStage(3))
    // 4. score counts 0 → 87
    at(1150, () => {
      const duration = 1400
      const start = performance.now()
      const tick = (now: number) => {
        const t = Math.min((now - start) / duration, 1)
        const eased = 1 - Math.pow(1 - t, 3)
        setScore(Math.round(eased * SCORE_FINAL))
        if (t < 1) requestAnimationFrame(tick)
      }
      requestAnimationFrame(tick)
    })
    // 5. score breakdown animates
    at(1300, () => {
      setStage(4)
      barsRef.current?.querySelectorAll<HTMLElement>('.mini-bar-fill').forEach((bar, i) => {
        setTimeout(() => { bar.style.width = (bar.dataset.w ?? '0') + '%' }, i * 90)
      })
    })
    // 6. signals reveal
    at(2000, () => setStage(5))
    // 7. risk indicators reveal
    at(2300, () => setStage(6))
    // 8. timestamp appears, interface settles
    at(2600, () => setStage(8))

    return () => timers.forEach(clearTimeout)
  }, [])

  const stageIn = (s: number) =>
    `hero-stage ${stage >= s ? 'stage-in' : ''}`

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!email || !email.includes('@')) {
      setStatus('error')
      setMessage('Please enter a valid email address.')
      return
    }
    setStatus('loading')
    try {
      const res = await fetch('/api/waitlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, source: 'landing_page' }),
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
    <section className="relative min-h-screen flex items-center overflow-hidden">
      <div className="absolute inset-0">
        <div className="absolute top-[-20%] right-[-10%] w-[60%] h-[80%] bg-[radial-gradient(ellipse,rgba(34,197,94,0.03)_0%,transparent_70%)]" />
        <div className="absolute inset-0 opacity-[0.025]" style={{
          backgroundImage: 'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)',
          backgroundSize: '80px 80px'
        }} />
      </div>

      <div className="relative z-10 max-w-6xl mx-auto px-6 md:px-8 pt-28 pb-20 lg:py-32 grid lg:grid-cols-2 gap-14 lg:gap-16 items-center">
        <div className="animate-fade-in-up">
          <p className="font-mono text-[11px] font-semibold tracking-[0.12em] uppercase text-brand-500 mb-4">
            Land Deal Intelligence
          </p>
          <h1 className="text-4xl md:text-5xl font-bold leading-[1.1] tracking-[-0.03em] mb-5">
            Find land worth looking at.
          </h1>
          <p className="text-[17px] text-[#A1A1AA] leading-[1.75] max-w-[440px] mb-9">
            DealScan helps land investors screen rural and vacant land opportunities in one workflow — property data, comparable sales, seller signals, and risk flags side by side — instead of jumping between listing sites, county records, and spreadsheets.
          </p>
          <div className="flex flex-col sm:flex-row gap-3">
            <a href="#early-access" className="group inline-flex items-center justify-center gap-2 px-6 py-3 rounded-md bg-brand-600 hover:bg-brand-500 text-white text-sm font-medium transition-all hover:-translate-y-px">
              Start exploring <span aria-hidden="true" className="transition-transform duration-200 group-hover:translate-x-1">&rarr;</span>
            </a>
            <a href="#deal-example" className="inline-flex items-center justify-center px-6 py-3 rounded-md border border-white/10 text-white text-sm font-medium hover:bg-white/5 hover:border-white/20 transition-all hover:-translate-y-px">
              See an example
            </a>
          </div>
        </div>

        {/* Product card with depth layer */}
        <div className="animate-fade-in-up delay-200 relative">
          <div className="absolute inset-[12px_-8px_-8px_12px] border border-white/[0.06] rounded-[10px] -z-10" />
          <div className={`hero-card ${stage >= 1 ? 'settled' : ''} rounded-[10px] border border-white/10 bg-[#161618] overflow-hidden shadow-[0_24px_48px_rgba(0,0,0,0.4)]`}>
            {/* Property identity */}
            <div className={stageIn(2)}>
              <div className="px-5 py-4 border-b border-white/[0.06] bg-[#111113] flex items-center justify-between">
                <div>
                  <div className="font-semibold text-sm">Cochise County, Arizona</div>
                  <div className="font-mono text-[11px] text-[#52525B] mt-0.5">APN 123-45-678A</div>
                </div>
                <span className="font-mono text-[10px] font-semibold uppercase tracking-wide px-2 py-1 rounded bg-amber-500/10 text-amber-500">Demo — fictional</span>
              </div>
            </div>

            <div className="p-5">
              {/* DealScore with mini-bars */}
              <div className={stageIn(4)}>
                <div className="p-3.5 rounded-md bg-[#111113] border border-white/[0.06] mb-5">
                  <div className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-[#52525B]">Deal Score</div>
                  <div className="flex items-baseline gap-1 mb-3" aria-label={`Deal score ${SCORE_FINAL} out of 100`}>
                    <span className="text-[32px] font-bold text-brand-500 leading-none tabular-nums" aria-hidden="true">{score}</span>
                    <span className="text-[13px] text-[#52525B]">/ 100</span>
                  </div>
                  <div ref={barsRef}>
                    {scoreBars.map((bar) => (
                      <div key={bar.label} className="mini-bar-row">
                        <span className="mini-bar-label">{bar.label}</span>
                        <div className="mini-bar-track"><div className="mini-bar-fill" data-w={bar.val} /></div>
                        <span className="mini-bar-val">{bar.val}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              {/* Metrics */}
              <div className={stageIn(3)}>
                <div className="grid grid-cols-2 gap-4 mb-5">
                  <div>
                    <div className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-[#52525B] mb-1">Asking Price</div>
                    <div className="text-[22px] font-bold tracking-[-0.01em] tabular-nums">$4,900</div>
                  </div>
                  <div>
                    <div className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-[#52525B] mb-1">Est. Market Value</div>
                    <div className="text-[22px] font-bold tracking-[-0.01em] tabular-nums">$9,700</div>
                  </div>
                  <div>
                    <div className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-[#52525B] mb-1">Potential Spread</div>
                    <div className="text-[22px] font-bold tracking-[-0.01em] text-brand-500 tabular-nums">$4,800</div>
                  </div>
                  <div>
                    <div className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-[#52525B] mb-1">Acreage</div>
                    <div className="text-[22px] font-bold tracking-[-0.01em] tabular-nums">2.31 <span className="text-xs font-normal text-[#52525B]">ac</span></div>
                  </div>
                </div>
              </div>
              {/* Signals */}
              <div className={stageIn(5)}>
                <div className="mb-4">
                  <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.08em] text-[#52525B] mb-3">Signals</div>
                  <ul>
                    {signals.map((s) => (
                      <li key={s.text} className="flex items-start gap-2.5 py-[7px] border-b border-white/[0.06] last:border-0 text-[13px] text-[#A1A1AA]">
                        <span className={`text-xs w-4 text-center flex-shrink-0 ${s.warn ? 'text-amber-500' : 'text-brand-500'}`} aria-hidden="true">{s.warn ? '\u26A0' : '\u2713'}</span>
                        <span className="sr-only">{s.warn ? 'Review: ' : ''}</span>{s.text}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
              {/* Risk checks */}
              <div className={stageIn(6)}>
                <div>
                  <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.08em] text-[#52525B] mb-3">Risk check</div>
                  <ul>
                    {riskChecks.map((s) => (
                      <li key={s.text} className="flex items-start gap-2.5 py-[7px] border-b border-white/[0.06] last:border-0 text-[13px] text-[#A1A1AA]">
                        <span className={`text-xs w-4 text-center flex-shrink-0 ${s.warn ? 'text-amber-500' : 'text-brand-500'}`} aria-hidden="true">{s.warn ? '\u26A0' : '\u2713'}</span>
                        <span className="sr-only">{s.warn ? 'Review: ' : ''}</span>{s.text}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
            {/* Timestamp footer */}
            <div className={stageIn(8)}>
              <div className="px-5 py-3 border-t border-white/[0.06] bg-[#111113] flex items-center justify-between font-mono text-[11px] text-[#52525B]">
                <span className="flex items-center gap-1.5">
                  <span className="w-[5px] h-[5px] rounded-full bg-brand-500/70" aria-hidden="true" />
                  Demo dataset &middot; illustrative
                </span>
                <span>EXAMPLE DATA</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
