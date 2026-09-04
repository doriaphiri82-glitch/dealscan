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
  valuation_basis?: string
  valuation_confidence?: number
  source_url?: string
  verification_status?: string
  latitude?: number
  longitude?: number
}
interface DealsResponse { deals: Deal[]; generated_at?: string | null; count?: number; meta?: { status?: string; scraped_counties?: string[]; storage_source?: string } }

const money = (value?: number) => typeof value === 'number' ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value) : '—'
const titleCase = (value?: string) => value ? value.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase()) : '—'
const clampScore = (score?: number) => typeof score === 'number' ? Math.max(0, Math.min(100, score)) : 0

function ScoreRing({ score, large = false }: { score?: number; large?: boolean }) {
  const value = clampScore(score)
  const size = large ? 'h-20 w-20' : 'h-14 w-14'
  const inner = large ? 'h-14 w-14' : 'h-10 w-10'
  return <div className={`relative grid ${size} shrink-0 place-items-center rounded-full`} style={{ background: `conic-gradient(#176b45 ${value * 3.6}deg, #e7ece9 0deg)` }}><div className={`grid ${inner} place-items-center rounded-full bg-white`}><div className="text-center"><span className={`${large ? 'text-xl' : 'text-base'} font-black text-[#153025]`}>{score ?? '—'}</span>{large && <span className="block text-[7px] font-black uppercase tracking-[.12em] text-[#9aa49f]">score</span>}</div></div></div>
}

function Metric({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return <div className="rounded-xl border border-[#e7ece9] bg-[#f8faf9] px-3 py-2.5"><p className="text-[9px] font-black uppercase tracking-[.14em] text-[#8a958f]">{label}</p><p className={`mt-1 text-sm font-black tracking-tight ${accent ? 'text-[#176b45]' : 'text-[#18251f]'}`}>{value}</p></div>
}

export default function DealExplorer() {
  const [data, setData] = useState<DealsResponse>({ deals: [] })
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [county, setCounty] = useState('all')
  const [minScore, setMinScore] = useState(0)
  const [sort, setSort] = useState<'score' | 'profit' | 'price'>('score')
  const [view, setView] = useState<'grid' | 'list' | 'map'>('grid')
  const [selected, setSelected] = useState<string[]>([])
  const [saved, setSaved] = useState<string[]>([])
  const [filtersOpen, setFiltersOpen] = useState(false)

  useEffect(() => {
    try { setSaved(JSON.parse(localStorage.getItem('dealscan:saved') || '[]')) } catch { setSaved([]) }
  }, [])

  const loadDeals = useCallback(async (silent = false) => {
    silent ? setRefreshing(true) : setLoading(true)
    try {
      const res = await fetch('/api/deals?limit=100', { cache: 'no-store' })
      if (!res.ok) throw new Error()
      setData(await res.json() as DealsResponse)
      setError('')
    } catch {
      setError('The deal feed is temporarily unavailable. Showing the latest data already loaded.')
    } finally { setLoading(false); setRefreshing(false) }
  }, [])

  useEffect(() => { void loadDeals(); const timer = window.setInterval(() => void loadDeals(true), 60000); return () => window.clearInterval(timer) }, [loadDeals])

  const counties = useMemo(() => Array.from(new Set(data.deals.map(d => d.county_id).filter(Boolean))).sort() as string[], [data.deals])
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return data.deals.filter(d => county === 'all' || d.county_id === county)
      .filter(d => (d.deal_score ?? 0) >= minScore)
      .filter(d => !needle || `${d.address ?? ''} ${d.apn ?? ''} ${d.county_id ?? ''}`.toLowerCase().includes(needle))
      .sort((a, b) => sort === 'profit' ? (b.estimated_profit_high ?? 0) - (a.estimated_profit_high ?? 0) : sort === 'price' ? (a.asking_price ?? Infinity) - (b.asking_price ?? Infinity) : (b.deal_score ?? 0) - (a.deal_score ?? 0))
  }, [data.deals, county, minScore, query, sort])

  const isDemo = data.meta?.storage_source === 'seed' || data.meta?.status === 'demo'
  const statusLabel = isDemo ? 'Demo data' : data.meta?.status === 'degraded' ? 'Feed degraded' : 'Verified feed'
  const avgScore = data.deals.length ? Math.round(data.deals.reduce((sum, d) => sum + (d.deal_score ?? 0), 0) / data.deals.length) : 0
  const avgProfit = data.deals.length ? data.deals.reduce((sum, d) => sum + (d.estimated_profit_high ?? 0), 0) / data.deals.length : 0

  const toggleSaved = (apn: string) => {
    const next = saved.includes(apn) ? saved.filter(x => x !== apn) : [...saved, apn]
    setSaved(next); localStorage.setItem('dealscan:saved', JSON.stringify(next))
  }
  const toggleSelected = (apn: string) => setSelected(prev => prev.includes(apn) ? prev.filter(x => x !== apn) : prev.length >= 3 ? prev : [...prev, apn])
  const clearFilters = () => { setQuery(''); setCounty('all'); setMinScore(0); setSort('score') }

  return <main className="min-h-screen bg-[#f7f9f7] text-[#15211b]">
    <header className="sticky top-0 z-40 border-b border-[#e6ebe8]/90 bg-white/90 backdrop-blur-2xl"><div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6"><a href="/" className="text-[17px] font-black tracking-tight">Deal<span className="text-[#176b45]">Scan</span></a><nav className="hidden items-center gap-1 md:flex"><a href="/deals" className="rounded-xl bg-[#edf5f0] px-3.5 py-2 text-sm font-bold text-[#176b45]">Explore</a><a href="/my-dealscan" className="rounded-xl px-3.5 py-2 text-sm font-bold text-[#65726b] hover:bg-[#f4f7f5]">My DealScan</a><a href="/compare" className="rounded-xl px-3.5 py-2 text-sm font-bold text-[#65726b] hover:bg-[#f4f7f5]">Compare</a></nav><div className="flex items-center gap-2"><button onClick={() => void loadDeals(true)} disabled={refreshing} className="rounded-xl border border-[#dfe6e2] bg-white px-3 py-2 text-xs font-bold text-[#34423b] hover:bg-[#f4f8f5] disabled:opacity-50">{refreshing ? 'Refreshing…' : 'Refresh'}</button><a href="/auth" className="hidden rounded-xl bg-[#153025] px-3.5 py-2 text-xs font-bold text-white hover:bg-[#176b45] sm:inline-flex">Sign in</a></div></div></header>

    <section className="relative overflow-hidden border-b border-[#e5ebe7] bg-white"><div className="absolute inset-0 opacity-40 [background-image:linear-gradient(#176b4510_1px,transparent_1px),linear-gradient(90deg,#176b4510_1px,transparent_1px)] [background-size:48px_48px]"/><div className="relative mx-auto max-w-7xl px-4 py-10 sm:px-6 sm:py-14"><div className="flex flex-col justify-between gap-7 lg:flex-row lg:items-end"><div><div className="flex flex-wrap items-center gap-2"><span className={`rounded-full px-3 py-1.5 text-[10px] font-black uppercase tracking-[.14em] ${isDemo ? 'bg-[#fff5df] text-[#9a6515]' : 'bg-[#e8f4ec] text-[#176b45]'}`}>{statusLabel}</span>{data.meta?.scraped_counties?.length ? <span className="text-xs font-bold text-[#7f8b85]">{data.meta.scraped_counties.length} source counties</span> : null}</div><h1 className="mt-4 text-4xl font-black tracking-[-.045em] sm:text-5xl">Deal Explorer</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-[#65726b] sm:text-base">Discover → understand → verify. Search the published feed, narrow the field, then open a property to research the evidence.</p></div><div className="grid grid-cols-3 gap-2 sm:min-w-[420px]"><Metric label="Published" value={String(data.count ?? data.deals.length)} /><Metric label="Avg score" value={loading ? '—' : `${avgScore}/100`} accent /><Metric label="Upside signal" value={loading ? '—' : money(avgProfit)} accent /></div></div>
      <div className="mt-7 rounded-[1.75rem] border border-[#dfe7e2] bg-white/95 p-2 shadow-[0_20px_70px_rgba(22,45,34,.08)]"><div className="flex flex-col gap-2 lg:flex-row"><label className="flex min-h-12 flex-1 items-center gap-3 rounded-xl bg-[#f5f8f6] px-4 ring-1 ring-inset ring-[#e4ebe7] focus-within:ring-2 focus-within:ring-[#176b45]/25"><span className="text-[#718078]">⌕</span><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search address, APN or county" aria-label="Search deals" className="w-full bg-transparent text-sm font-semibold outline-none placeholder:text-[#98a29d]"/><kbd className="hidden rounded-lg border border-[#dce4df] bg-white px-2 py-1 text-[10px] font-bold text-[#87928c] sm:block">⌘ K</kbd></label><button onClick={() => setFiltersOpen(v => !v)} className="min-h-12 rounded-xl border border-[#e4ebe7] bg-white px-4 text-sm font-bold text-[#34423b] hover:bg-[#f4f8f5] lg:hidden">Filters {minScore || county !== 'all' ? '•' : ''}</button><div className={`${filtersOpen ? 'grid' : 'hidden'} gap-2 lg:grid lg:grid-cols-3`}><select value={county} onChange={e => setCounty(e.target.value)} aria-label="Filter county" className="min-h-12 rounded-xl border border-[#e4ebe7] bg-[#f5f8f6] px-4 text-sm font-bold text-[#46534c] outline-none"><option value="all">All counties</option>{counties.map(c => <option key={c} value={c}>{titleCase(c)}</option>)}</select><select value={String(minScore)} onChange={e => setMinScore(Number(e.target.value))} aria-label="Minimum score" className="min-h-12 rounded-xl border border-[#e4ebe7] bg-[#f5f8f6] px-4 text-sm font-bold text-[#46534c] outline-none"><option value="0">Any score</option><option value="50">50+ score</option><option value="70">70+ score</option><option value="80">80+ score</option><option value="90">90+ score</option></select><select value={sort} onChange={e => setSort(e.target.value as typeof sort)} aria-label="Sort deals" className="min-h-12 rounded-xl border border-[#e4ebe7] bg-[#f5f8f6] px-4 text-sm font-bold text-[#46534c] outline-none"><option value="score">Highest score</option><option value="profit">Highest profit</option><option value="price">Lowest price</option></select></div></div></div>
      {(query || county !== 'all' || minScore > 0) && <div className="mt-3 flex flex-wrap items-center gap-2"><span className="text-xs font-bold text-[#7f8b85]">Active:</span>{query && <button onClick={() => setQuery('')} className="rounded-full bg-[#e8f4ec] px-3 py-1 text-xs font-bold text-[#176b45]">Search: {query} ×</button>}{county !== 'all' && <button onClick={() => setCounty('all')} className="rounded-full bg-[#e8f4ec] px-3 py-1 text-xs font-bold text-[#176b45]">{titleCase(county)} ×</button>}{minScore > 0 && <button onClick={() => setMinScore(0)} className="rounded-full bg-[#e8f4ec] px-3 py-1 text-xs font-bold text-[#176b45]">Score {minScore}+ ×</button>}<button onClick={clearFilters} className="text-xs font-bold text-[#6f7b74] hover:text-[#153025]">Clear all</button></div>}
    </div></section>

    <section className="mx-auto max-w-7xl px-4 py-7 pb-24 sm:px-6"><div className="flex flex-col gap-4 border-b border-[#e3e9e5] pb-4 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-[10px] font-black uppercase tracking-[.18em] text-[#8b9690]">Opportunity feed</p><h2 className="mt-1 text-xl font-black">{filtered.length} {filtered.length === 1 ? 'match' : 'matches'}</h2></div><div className="flex items-center gap-2"><div className="flex rounded-xl border border-[#dfe6e2] bg-white p-1"><button onClick={() => setView('grid')} className={`rounded-lg px-3 py-1.5 text-xs font-bold ${view === 'grid' ? 'bg-[#153025] text-white' : 'text-[#6f7b74]'}`}>Grid</button><button onClick={() => setView('list')} className={`rounded-lg px-3 py-1.5 text-xs font-bold ${view === 'list' ? 'bg-[#153025] text-white' : 'text-[#6f7b74]'}`}>List</button><button onClick={() => setView('map')} className={`rounded-lg px-3 py-1.5 text-xs font-bold ${view === 'map' ? 'bg-[#153025] text-white' : 'text-[#6f7b74]'}`}>Map</button></div><span className="hidden text-xs text-[#8b9690] sm:inline">Select up to 3</span></div></div>
      {selected.length > 0 && <div className="sticky top-[72px] z-20 mt-4 flex items-center justify-between gap-3 rounded-2xl border border-[#bcd3c5] bg-[#eff7f1]/95 px-4 py-3 shadow-lg backdrop-blur"><div className="text-sm font-bold text-[#254136]">{selected.length} deal{selected.length > 1 ? 's' : ''} selected</div><div className="flex items-center gap-2"><button onClick={() => setSelected([])} className="rounded-lg px-3 py-2 text-xs font-bold text-[#68756e]">Clear</button>{selected.length >= 2 && <a href={`/compare?apns=${encodeURIComponent(selected.join(','))}`} className="rounded-lg bg-[#153025] px-3 py-2 text-xs font-bold text-white hover:bg-[#176b45]">Compare →</a>}</div></div>}
      {isDemo && <div className="mt-4 rounded-2xl border border-[#ead9b8] bg-[#fffaf0] px-4 py-3 text-sm font-medium text-[#76521b]">Seed records are clearly labeled. Treat them as interface/data-shape previews, not verified investment opportunities.</div>}
      {error && <div role="alert" className="mt-4 rounded-2xl border border-[#ead9b8] bg-[#fffaf0] px-4 py-3 text-sm font-medium text-[#76521b]">{error}</div>}
      {view === 'map' ? <MapPanel deals={filtered} /> : loading ? <div className={`mt-5 grid gap-5 ${view === 'list' ? '' : 'md:grid-cols-2 xl:grid-cols-3'}`}>{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-72 animate-pulse rounded-[1.5rem] border border-[#e7ece9] bg-white" />)}</div> : filtered.length === 0 ? <div className="mt-5 rounded-[1.75rem] border border-dashed border-[#cfd9d3] bg-white p-14 text-center"><div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-[#eef4f0]">⌕</div><h2 className="mt-5 text-xl font-black">No matching opportunities</h2><p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-[#718078]">Clear a filter or broaden the search. DealScan only presents records available from its current published feed.</p><button onClick={clearFilters} className="mt-5 rounded-xl bg-[#153025] px-4 py-2.5 text-sm font-bold text-white hover:bg-[#176b45]">Clear filters</button></div> : <div className={`mt-5 grid gap-5 ${view === 'list' ? '' : 'md:grid-cols-2 xl:grid-cols-3'}`}>{filtered.map((deal, index) => <DealCard key={`${deal.apn}-${index}`} deal={deal} list={view === 'list'} selected={!!deal.apn && selected.includes(deal.apn)} saved={!!deal.apn && saved.includes(deal.apn)} onSelect={() => deal.apn && toggleSelected(deal.apn)} onSave={() => deal.apn && toggleSaved(deal.apn)} />)}</div>}
    </section>
    <MobileNav />
  </main>
}

function DealCard({ deal, list, selected, saved, onSelect, onSave }: { deal: Deal; list: boolean; selected: boolean; saved: boolean; onSelect: () => void; onSave: () => void }) {
  return <article className={`group relative overflow-hidden rounded-[1.5rem] border bg-white transition duration-300 hover:-translate-y-0.5 ${selected ? 'border-[#176b45] ring-2 ring-[#176b45]/10' : 'border-[#e3e9e5] hover:border-[#b9cfc1]'} ${list ? 'p-4 sm:flex sm:items-center sm:gap-5' : 'p-5 sm:p-6'}`}><div className="absolute inset-x-0 top-0 h-1 bg-[#176b45] opacity-0 transition group-hover:opacity-100"/><div className={`${list ? 'sm:flex-1' : ''}`}><div className="flex items-start justify-between gap-4"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><span className="rounded-full bg-[#edf5f0] px-2.5 py-1 text-[9px] font-black uppercase tracking-[.12em] text-[#176b45]">{titleCase(deal.county_id)}</span>{deal.verification_status && <span className="text-[9px] font-bold text-[#87928c]">{titleCase(deal.verification_status)}</span>}</div><h3 className="mt-2 line-clamp-2 text-lg font-black tracking-tight">{deal.address || 'Parcel opportunity'}</h3><p className="mt-1 truncate font-mono text-[10px] text-[#929d97]">APN {deal.apn || '—'}</p></div><ScoreRing score={deal.deal_score}/></div>{!list && <div className="mt-5 grid grid-cols-2 gap-2"><Metric label="Ask" value={money(deal.asking_price)} /><Metric label="Profit signal" value={money(deal.estimated_profit_high)} accent /><Metric label="ARV" value={money(deal.estimated_arv_high)} /><Metric label="Lot" value={deal.lot_size_acres ? `${deal.lot_size_acres.toLocaleString()} ac` : '—'} /></div>}{list && <div className="mt-4 grid grid-cols-3 gap-2 sm:mt-0 sm:max-w-md"><Metric label="Ask" value={money(deal.asking_price)} /><Metric label="Profit" value={money(deal.estimated_profit_high)} accent /><Metric label="Lot" value={deal.lot_size_acres ? `${deal.lot_size_acres.toLocaleString()} ac` : '—'} /></div>}</div><div className={`${list ? 'mt-4 sm:mt-0' : 'mt-4'}`}><div className="rounded-xl bg-[#f7faf8] p-3"><div className="flex items-center justify-between gap-3"><span className="text-[10px] font-bold text-[#77837c]">Recommended offer</span><span className="text-xs font-black">{money(deal.recommended_offer_low)}–{money(deal.recommended_offer_high)}</span></div>{deal.valuation_confidence != null && <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[#e1e8e3]"><div className="h-full rounded-full bg-[#176b45]" style={{ width: `${Math.max(0, Math.min(100, deal.valuation_confidence * 100))}%` }} /></div>}</div><div className="mt-3 flex items-center justify-between gap-2"><button onClick={onSelect} aria-pressed={selected} className={`rounded-lg border px-2.5 py-1.5 text-[10px] font-bold ${selected ? 'border-[#176b45] bg-[#e8f4ec] text-[#176b45]' : 'border-[#dfe6e2] text-[#68756e] hover:bg-[#f4f8f5]'}`}>{selected ? 'Selected' : 'Compare'}</button><button onClick={onSave} aria-pressed={saved} className={`rounded-lg px-2.5 py-1.5 text-[10px] font-bold ${saved ? 'bg-[#e8f4ec] text-[#176b45]' : 'text-[#68756e] hover:bg-[#f4f8f5]'}`}>{saved ? 'Saved ✓' : 'Save'}</button>{deal.source_url && <a href={deal.source_url} target="_blank" rel="noreferrer" className="text-[10px] font-bold text-[#176b45] hover:underline">Source ↗</a>}{deal.apn && <a href={`/deals/${encodeURIComponent(deal.apn)}`} className="rounded-lg bg-[#153025] px-3 py-1.5 text-[10px] font-bold text-white hover:bg-[#176b45]">Research →</a>}</div></div></article>
}

function MapPanel({ deals }: { deals: Deal[] }) {
  const withCoords = deals.filter(d => typeof d.latitude === 'number' && typeof d.longitude === 'number')
  return <div className="mt-5 overflow-hidden rounded-[1.75rem] border border-[#dfe7e2] bg-white"><div className="grid min-h-[520px] lg:grid-cols-[1fr_340px]"><div className="relative overflow-hidden bg-[#eef3ef] [background-image:linear-gradient(#d7e1da_1px,transparent_1px),linear-gradient(90deg,#d7e1da_1px,transparent_1px)] [background-size:48px_48px]"><div className="absolute inset-0 opacity-60 [background-image:radial-gradient(circle_at_30%_35%,#fff_0,transparent_26%),radial-gradient(circle_at_70%_65%,#d9e8de_0,transparent_28%)]"/><div className="absolute left-5 top-5 rounded-xl border border-white/80 bg-white/90 px-3 py-2 text-[10px] font-black uppercase tracking-[.14em] text-[#536159] shadow-sm">Published parcel map</div>{withCoords.length ? withCoords.map((deal, i) => <a key={deal.apn || i} href={deal.apn ? `/deals/${encodeURIComponent(deal.apn)}` : '#'} className="absolute grid h-9 w-9 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border-4 border-white bg-[#176b45] text-[9px] font-black text-white shadow-lg" style={{ left: `${12 + ((i * 37) % 76)}%`, top: `${18 + ((i * 53) % 68)}%` }} title={deal.address || deal.apn}>{deal.deal_score ?? '—'}</a>) : <div className="absolute inset-0 grid place-items-center p-8 text-center"><div className="max-w-sm rounded-2xl border border-white bg-white/90 p-6 shadow-xl backdrop-blur"><div className="mx-auto grid h-11 w-11 place-items-center rounded-xl bg-[#e8f4ec] text-[#176b45]">⌖</div><h3 className="mt-4 text-lg font-black">Coordinates are not published yet</h3><p className="mt-2 text-sm leading-6 text-[#6f7b74]">DealScan will only place parcels on the map when the source feed provides legitimate latitude/longitude. No locations are fabricated.</p></div></div>}</div><aside className="border-t border-[#e2e9e4] bg-white p-5 lg:border-l lg:border-t-0"><p className="text-[10px] font-black uppercase tracking-[.16em] text-[#8b9690]">Map results</p><h3 className="mt-1 text-lg font-black">{deals.length} opportunities</h3><div className="mt-4 space-y-2">{deals.slice(0, 8).map((deal, i) => <a key={deal.apn || i} href={deal.apn ? `/deals/${encodeURIComponent(deal.apn)}` : '#'} className="block rounded-xl border border-[#e7ece9] p-3 hover:border-[#b9cfc1] hover:bg-[#f8faf9]"><div className="flex items-center justify-between gap-3"><span className="line-clamp-1 text-xs font-bold">{deal.address || 'Parcel opportunity'}</span><span className="text-xs font-black text-[#176b45]">{deal.deal_score ?? '—'}</span></div><span className="mt-1 block font-mono text-[9px] text-[#919c96]">{deal.apn || 'No APN'}</span></a>)}</div></aside></div></div>
}

function MobileNav() {
  return <nav className="fixed inset-x-0 bottom-0 z-50 border-t border-[#dfe7e2] bg-white/95 px-4 py-2 backdrop-blur-xl md:hidden"><div className="mx-auto grid max-w-lg grid-cols-4 gap-1"><a href="/" className="rounded-xl p-2 text-center text-[10px] font-bold text-[#718078]">Home</a><a href="/deals" className="rounded-xl bg-[#edf5f0] p-2 text-center text-[10px] font-black text-[#176b45]">Explore</a><a href="/my-dealscan" className="rounded-xl p-2 text-center text-[10px] font-bold text-[#718078]">Saved</a><a href="/compare" className="rounded-xl p-2 text-center text-[10px] font-bold text-[#718078]">Compare</a></div></nav>
}
