'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'

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
  market_velocity?: number
  competition_level?: string
  valuation_basis?: string
  valuation_confidence?: number
  source_url?: string
  verification_status?: string
}

interface DealsResponse {
  deals: Deal[]
  generated_at?: string | null
  count?: number
  meta?: { status?: string; scraped_counties?: string[]; storage_source?: string }
}

const money = (value?: number) =>
  typeof value === 'number'
    ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value)
    : '—'

const titleCase = (value?: string) =>
  value ? value.replaceAll('_', ' ').replace(/\b\w/g, (char) => char.toUpperCase()) : '—'

export default function DealsPage() {
  const [data, setData] = useState<DealsResponse>({ deals: [] })
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [county, setCounty] = useState('all')
  const [minScore, setMinScore] = useState(0)
  const [sort, setSort] = useState<'score' | 'profit' | 'price'>('score')

  const loadDeals = useCallback(async (silent = false) => {
    silent ? setRefreshing(true) : setLoading(true)
    try {
      const res = await fetch('/api/deals?limit=50', { cache: 'no-store' })
      if (!res.ok) throw new Error(`Deal feed returned ${res.status}`)
      const json = (await res.json()) as DealsResponse
      setData(json)
      setError('')
    } catch {
      setError('The deal feed is temporarily unavailable. Showing the latest data already loaded.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void loadDeals()
    const timer = window.setInterval(() => void loadDeals(true), 60_000)
    return () => window.clearInterval(timer)
  }, [loadDeals])

  const counties = useMemo(
    () => Array.from(new Set(data.deals.map((deal) => deal.county_id).filter(Boolean))).sort() as string[],
    [data.deals]
  )

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return data.deals
      .filter((deal) => county === 'all' || deal.county_id === county)
      .filter((deal) => (deal.deal_score ?? 0) >= minScore)
      .filter((deal) => !needle || `${deal.address ?? ''} ${deal.apn ?? ''} ${deal.county_id ?? ''}`.toLowerCase().includes(needle))
      .sort((a, b) => {
        if (sort === 'profit') return (b.estimated_profit_high ?? 0) - (a.estimated_profit_high ?? 0)
        if (sort === 'price') return (a.asking_price ?? Infinity) - (b.asking_price ?? Infinity)
        return (b.deal_score ?? 0) - (a.deal_score ?? 0)
      })
  }, [data.deals, county, minScore, query, sort])

  const isDemo = data.meta?.storage_source === 'seed' || data.meta?.status === 'demo'
  const statusLabel = isDemo ? 'Demo data' : data.meta?.status === 'degraded' ? 'Feed degraded' : 'Verified feed'

  return (
    <main className="min-h-screen bg-[#f6f8f7] text-[#13221c]">
      <header className="sticky top-0 z-20 border-b border-black/5 bg-white/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <a href="/" className="text-xl font-black tracking-tight">DealScan</a>
          <div className="flex items-center gap-2">
            {refreshing && <span className="hidden text-xs font-semibold text-black/40 sm:inline">Refreshing…</span>}
            <button onClick={() => void loadDeals(true)} disabled={refreshing} className="rounded-full border border-black/10 px-4 py-2 text-sm font-semibold transition hover:bg-black hover:text-white disabled:opacity-50">Refresh</button>
            <a href="/" className="hidden rounded-full border border-black/10 px-4 py-2 text-sm font-semibold transition hover:bg-black hover:text-white sm:inline-flex">Back home</a>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-7xl px-4 pb-16 pt-10 sm:px-6 sm:pt-12">
        <div className="mb-8 max-w-3xl">
          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs font-bold uppercase tracking-[0.2em]">
            <span className={isDemo ? 'rounded-full bg-amber-50 px-3 py-1.5 text-amber-700' : 'rounded-full bg-emerald-50 px-3 py-1.5 text-emerald-700'}>{statusLabel}</span>
            {data.meta?.scraped_counties?.length ? <span className="text-black/35">{data.meta.scraped_counties.length} source counties in latest bundle</span> : null}
          </div>
          <h1 className="text-4xl font-black tracking-tight sm:text-6xl">Find the deals worth investigating.</h1>
          <p className="mt-4 text-lg leading-8 text-black/60">Search published property opportunities, compare estimated upside, and inspect the evidence behind each score.</p>
          {isDemo && <p className="mt-3 text-sm font-medium text-amber-800">You are seeing clearly labeled seed data until the verified pipeline publishes a live bundle.</p>}
        </div>

        {error && <div role="alert" className="mb-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-900">{error}</div>}

        <div className="mb-8 grid gap-3 rounded-3xl border border-black/5 bg-white p-4 shadow-[0_20px_70px_rgba(0,0,0,0.06)] md:grid-cols-[1.5fr_1fr_1fr_1fr]">
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search address, APN, county…" aria-label="Search deals" className="rounded-2xl border border-black/10 bg-[#f8faf9] px-4 py-3 outline-none transition focus:border-emerald-600 focus:ring-4 focus:ring-emerald-600/10" />
          <select value={county} onChange={(e) => setCounty(e.target.value)} aria-label="Filter by county" className="rounded-2xl border border-black/10 bg-[#f8faf9] px-4 py-3 outline-none">
            <option value="all">All counties</option>
            {counties.map((item) => <option key={item} value={item}>{titleCase(item)}</option>)}
          </select>
          <select value={String(minScore)} onChange={(e) => setMinScore(Number(e.target.value))} aria-label="Minimum deal score" className="rounded-2xl border border-black/10 bg-[#f8faf9] px-4 py-3 outline-none">
            <option value="0">Any score</option>
            <option value="50">50+ score</option>
            <option value="70">70+ score</option>
            <option value="80">80+ score</option>
            <option value="90">90+ score</option>
          </select>
          <select value={sort} onChange={(e) => setSort(e.target.value as typeof sort)} aria-label="Sort deals" className="rounded-2xl border border-black/10 bg-[#f8faf9] px-4 py-3 outline-none">
            <option value="score">Sort: highest score</option>
            <option value="profit">Sort: highest profit</option>
            <option value="price">Sort: lowest price</option>
          </select>
        </div>

        {loading ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-72 animate-pulse rounded-3xl bg-white" />)}</div>
        ) : filtered.length === 0 ? (
          <div className="rounded-3xl border border-dashed border-black/15 bg-white p-12 text-center">
            <h2 className="text-2xl font-bold">No matching deals yet</h2>
            <p className="mx-auto mt-2 max-w-xl text-black/55">Try clearing the filters. The discovery pipeline continuously expands its source registry and publishes only qualified opportunities.</p>
          </div>
        ) : (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {filtered.map((deal, index) => (
              <article key={`${deal.apn}-${index}`} className="group rounded-3xl border border-black/5 bg-white p-6 shadow-[0_15px_50px_rgba(0,0,0,0.05)] transition duration-300 hover:-translate-y-1 hover:shadow-[0_24px_70px_rgba(0,0,0,0.1)]">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-bold uppercase tracking-wider text-black/40">{titleCase(deal.county_id) || 'Unknown county'}</p>
                    <h2 className="mt-2 line-clamp-2 text-lg font-bold">{deal.address || 'Parcel opportunity'}</h2>
                  </div>
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-emerald-50 text-lg font-black text-emerald-700">{deal.deal_score ?? '—'}</div>
                </div>

                <div className="mt-6 grid grid-cols-2 gap-3">
                  <div className="rounded-2xl bg-[#f7f9f8] p-3"><p className="text-xs text-black/40">Ask</p><p className="mt-1 font-bold">{money(deal.asking_price)}</p></div>
                  <div className="rounded-2xl bg-[#f7f9f8] p-3"><p className="text-xs text-black/40">Profit</p><p className="mt-1 font-bold text-emerald-700">{money(deal.estimated_profit_high)}</p></div>
                  <div className="rounded-2xl bg-[#f7f9f8] p-3"><p className="text-xs text-black/40">ARV</p><p className="mt-1 font-bold">{money(deal.estimated_arv_high)}</p></div>
                  <div className="rounded-2xl bg-[#f7f9f8] p-3"><p className="text-xs text-black/40">Lot</p><p className="mt-1 font-bold">{deal.lot_size_acres ? `${deal.lot_size_acres.toLocaleString()} ac` : '—'}</p></div>
                </div>

                <div className="mt-5 flex flex-wrap gap-2 text-xs font-semibold">
                  <span className="rounded-full bg-black/[0.04] px-3 py-1.5">Offer {money(deal.recommended_offer_low)}–{money(deal.recommended_offer_high)}</span>
                  {deal.valuation_basis && <span className="rounded-full bg-black/[0.04] px-3 py-1.5">{titleCase(deal.valuation_basis)}</span>}
                  {deal.verification_status && <span className="rounded-full bg-emerald-50 px-3 py-1.5 text-emerald-700">{titleCase(deal.verification_status)}</span>}
                </div>

                <div className="mt-5 flex items-center justify-between border-t border-black/5 pt-4 text-xs text-black/40">
                  <span className="truncate pr-3">APN {deal.apn ?? '—'}</span>
                  <div className="flex shrink-0 items-center gap-3">
                    {deal.apn ? <a href={`/deals/${encodeURIComponent(deal.apn)}`} className="font-bold text-black transition group-hover:text-emerald-700 hover:underline">View evidence →</a> : null}
                    {deal.source_url ? <a href={deal.source_url} target="_blank" rel="noreferrer" className="font-semibold text-emerald-700 hover:underline">Source ↗</a> : null}
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}

        <div className="mt-8 flex flex-wrap items-center justify-between gap-3 text-sm text-black/45">
          <span>{filtered.length} visible {filtered.length === 1 ? 'deal' : 'deals'}</span>
          {data.generated_at && <span>Last pipeline update: {new Date(data.generated_at).toLocaleString()}</span>}
        </div>
      </section>
    </main>
  )
}
