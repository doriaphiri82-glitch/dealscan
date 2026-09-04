'use client'

import { useEffect, useState } from 'react'

interface Deal {
  apn?: string
  address?: string
  county_id?: string
  lot_size_acres?: number
  asking_price?: number
  deal_score?: number
  estimated_arv_low?: number
  estimated_arv_high?: number
  estimated_profit_low?: number
  estimated_profit_high?: number
  recommended_offer_low?: number
  recommended_offer_high?: number
  valuation_basis?: string
  valuation_confidence?: number
  source_url?: string
  source_quality?: string
  verification_status?: string
  data_freshness?: string
  motivation_signals?: string[]
}

const money = (value?: number) => typeof value === 'number'
  ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value)
  : '—'

const label = (value?: string) => value ? value.replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase()) : '—'

export default function DealDetailPage({ params }: { params: { apn: string } }) {
  const [deal, setDeal] = useState<Deal | null>(null)
  const [loading, setLoading] = useState(true)
  const [missing, setMissing] = useState(false)

  useEffect(() => {
    fetch(`/api/deals/${encodeURIComponent(params.apn)}`, { cache: 'no-store' })
      .then(async (res) => {
        if (res.status === 404) { setMissing(true); return }
        if (!res.ok) throw new Error('feed error')
        const json = await res.json() as { deal?: Deal }
        setDeal(json.deal ?? null)
      })
      .catch(() => setMissing(true))
      .finally(() => setLoading(false))
  }, [params.apn])

  if (loading) return <main className="min-h-screen bg-[#f6f8f7] p-6"><div className="mx-auto mt-20 h-96 max-w-4xl animate-pulse rounded-3xl bg-white" /></main>
  if (missing || !deal) return <main className="min-h-screen bg-[#f6f8f7] px-6 py-20 text-center text-[#13221c]"><h1 className="text-3xl font-black">Deal not found</h1><p className="mt-2 text-black/55">This parcel is not currently in the published DealScan feed.</p><a href="/deals" className="mt-6 inline-flex rounded-full bg-black px-5 py-3 font-semibold text-white">Back to deals</a></main>

  return (
    <main className="min-h-screen bg-[#f6f8f7] text-[#13221c]">
      <header className="border-b border-black/5 bg-white/90 backdrop-blur-xl"><div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4"><a href="/deals" className="font-black">← DealScan</a><a href="/" className="text-sm font-semibold text-black/55 hover:text-black">Home</a></div></header>
      <section className="mx-auto max-w-5xl px-6 py-10 sm:py-14">
        <div className="rounded-[2rem] border border-black/5 bg-white p-6 shadow-[0_20px_80px_rgba(0,0,0,0.07)] sm:p-10">
          <div className="flex flex-col justify-between gap-6 sm:flex-row">
            <div><p className="text-xs font-bold uppercase tracking-[0.2em] text-emerald-700">{label(deal.county_id)}</p><h1 className="mt-3 text-3xl font-black tracking-tight sm:text-5xl">{deal.address || 'Parcel opportunity'}</h1><p className="mt-3 text-sm text-black/45">APN {deal.apn || params.apn}</p></div>
            <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-3xl bg-emerald-50 text-3xl font-black text-emerald-700">{deal.deal_score ?? '—'}</div>
          </div>

          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-2xl bg-[#f7f9f8] p-4"><p className="text-xs text-black/40">Asking price</p><p className="mt-1 text-xl font-black">{money(deal.asking_price)}</p></div>
            <div className="rounded-2xl bg-[#f7f9f8] p-4"><p className="text-xs text-black/40">Estimated ARV</p><p className="mt-1 text-xl font-black">{money(deal.estimated_arv_low)}–{money(deal.estimated_arv_high)}</p></div>
            <div className="rounded-2xl bg-[#f7f9f8] p-4"><p className="text-xs text-black/40">Estimated profit</p><p className="mt-1 text-xl font-black text-emerald-700">{money(deal.estimated_profit_low)}–{money(deal.estimated_profit_high)}</p></div>
            <div className="rounded-2xl bg-[#f7f9f8] p-4"><p className="text-xs text-black/40">Recommended offer</p><p className="mt-1 text-xl font-black">{money(deal.recommended_offer_low)}–{money(deal.recommended_offer_high)}</p></div>
          </div>

          <div className="mt-8 grid gap-8 lg:grid-cols-[1.3fr_1fr]">
            <div><h2 className="text-xl font-black">Why this deal scored</h2><div className="mt-4 flex flex-wrap gap-2">{(deal.motivation_signals || []).map((signal) => <span key={signal} className="rounded-full bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-800">{label(signal)}</span>)}</div></div>
            <div className="rounded-3xl border border-black/5 bg-[#fafcfb] p-5"><h2 className="font-black">Evidence & provenance</h2><dl className="mt-4 space-y-3 text-sm"><div className="flex justify-between gap-4"><dt className="text-black/45">Valuation basis</dt><dd className="font-semibold">{label(deal.valuation_basis)}</dd></div><div className="flex justify-between gap-4"><dt className="text-black/45">Confidence</dt><dd className="font-semibold">{typeof deal.valuation_confidence === 'number' ? `${Math.round(deal.valuation_confidence * 100)}%` : '—'}</dd></div><div className="flex justify-between gap-4"><dt className="text-black/45">Verification</dt><dd className="font-semibold text-emerald-700">{label(deal.verification_status)}</dd></div><div className="flex justify-between gap-4"><dt className="text-black/45">Source quality</dt><dd className="font-semibold">{label(deal.source_quality)}</dd></div><div className="flex justify-between gap-4"><dt className="text-black/45">Freshness</dt><dd className="font-semibold">{deal.data_freshness || '—'}</dd></div></dl>{deal.source_url && <a href={deal.source_url} target="_blank" rel="noreferrer" className="mt-5 inline-flex rounded-full bg-black px-4 py-2.5 text-sm font-semibold text-white">Open source ↗</a>}</div>
          </div>

          <p className="mt-8 border-t border-black/5 pt-5 text-xs leading-5 text-black/40">DealScan scores are screening signals, not guarantees of value, title, buildability, or profit. Verify the parcel and source records before acting.</p>
        </div>
      </section>
    </main>
  )
}
