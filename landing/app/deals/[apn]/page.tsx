'use client'

import { useEffect, useMemo, useState } from 'react'

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

const money = (value?: number) => typeof value === 'number' ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value) : '—'
const label = (value?: string) => value ? value.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase()) : '—'

function ScoreRing({ score }: { score?: number }) {
  const value = typeof score === 'number' ? Math.max(0, Math.min(100, score)) : 0
  return (
    <div className="relative grid h-28 w-28 shrink-0 place-items-center rounded-full shadow-[0_12px_35px_rgba(23,107,69,.12)]" style={{ background: `conic-gradient(#176b45 ${value * 3.6}deg, #e3ebe6 0deg)` }}>
      <div className="grid h-[88px] w-[88px] place-items-center rounded-full bg-white">
        <div className="text-center"><div className="text-3xl font-black tracking-tight text-[#153025]">{score ?? '—'}</div><div className="mt-0.5 text-[9px] font-black uppercase tracking-[0.15em] text-[#8a958f]">DealScore</div></div>
      </div>
    </div>
  )
}

function Stat({ label: caption, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return <div className="rounded-2xl border border-[#e4ebe7] bg-white p-4 transition hover:-translate-y-0.5 hover:border-[#cbd9d0] hover:shadow-[0_10px_30px_rgba(23,42,32,.05)]"><p className="text-[10px] font-black uppercase tracking-[0.14em] text-[#8b9690]">{caption}</p><p className={`mt-2 text-lg font-black tracking-tight ${accent ? 'text-[#176b45]' : 'text-[#18251f]'}`}>{value}</p></div>
}

function EvidenceRow({ label: caption, value, available = true }: { label: string; value: string; available?: boolean }) {
  return <div className="flex items-start justify-between gap-4 border-b border-white/10 py-3 last:border-0"><span className="text-sm text-white/55">{caption}</span><span className={`max-w-[58%] text-right text-sm font-bold ${available ? 'text-white' : 'text-white/35'}`}>{value}</span></div>
}

export default function DealDetailPage({ params }: { params: { apn: string } }) {
  const [deal, setDeal] = useState<Deal | null>(null)
  const [loading, setLoading] = useState(true)
  const [missing, setMissing] = useState(false)

  useEffect(() => {
    fetch(`/api/deals/${encodeURIComponent(params.apn)}`, { cache: 'no-store' })
      .then(async res => { if (res.status === 404) { setMissing(true); return }; if (!res.ok) throw new Error(); setDeal((await res.json() as { deal?: Deal }).deal ?? null) })
      .catch(() => setMissing(true))
      .finally(() => setLoading(false))
  }, [params.apn])

  const confidence = typeof deal?.valuation_confidence === 'number' ? Math.round(deal.valuation_confidence * 100) : null
  const signalCount = deal?.motivation_signals?.length ?? 0
  const evidenceLabel = useMemo(() => {
    if (!deal) return 'Awaiting record'
    if (deal.verification_status && confidence != null) return confidence >= 75 ? 'Strong screening evidence' : 'Review evidence carefully'
    return 'Evidence needs verification'
  }, [deal, confidence])

  if (loading) return <main className="min-h-screen bg-[#f7f9f7] px-4 py-8 sm:px-6"><div className="mx-auto max-w-6xl space-y-5"><div className="h-14 animate-pulse rounded-2xl bg-white"/><div className="h-72 animate-pulse rounded-[2rem] bg-white"/><div className="grid gap-5 lg:grid-cols-3"><div className="h-56 animate-pulse rounded-[1.75rem] bg-white lg:col-span-2"/><div className="h-56 animate-pulse rounded-[1.75rem] bg-white"/></div></div></main>

  if (missing || !deal) return <main className="grid min-h-screen place-items-center bg-[#f7f9f7] px-6 text-center text-[#15211b]"><div><div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-[#eef4f0] text-xl">⌕</div><h1 className="mt-5 text-3xl font-black">Deal not found</h1><p className="mt-2 text-[#718078]">This parcel is not currently in the published DealScan feed.</p><a href="/deals" className="mt-6 inline-flex rounded-xl bg-[#153025] px-5 py-3 text-sm font-bold text-white transition hover:bg-[#176b45]">Return to explorer</a></div></main>

  return <main className="min-h-screen bg-[#f7f9f7] text-[#15211b]">
    <header className="sticky top-0 z-30 border-b border-[#e5ebe7]/90 bg-white/85 backdrop-blur-2xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3"><a href="/deals" className="text-[15px] font-black tracking-tight">Deal<span className="text-[#176b45]">Scan</span></a><span className="hidden h-4 w-px bg-[#dce4df] sm:block"/><span className="hidden truncate text-xs font-semibold text-[#87928c] sm:block">Property research</span></div>
        <div className="flex items-center gap-2"><a href="/deals" className="rounded-xl border border-[#dfe6e2] bg-white px-3.5 py-2 text-sm font-bold text-[#536159] transition hover:border-[#b9cfc1] hover:text-[#176b45]">← Explorer</a><a href="/" className="hidden rounded-xl bg-[#153025] px-3.5 py-2 text-sm font-bold text-white transition hover:bg-[#176b45] sm:inline-flex">Home</a></div>
      </div>
    </header>

    <section className="relative overflow-hidden border-b border-[#e4ebe7] bg-white">
      <div className="dealscan-grid absolute inset-0 opacity-80"/>
      <div className="absolute -right-20 top-0 h-72 w-72 rounded-full bg-[#e5f2ea] blur-3xl opacity-70"/>
      <div className="relative mx-auto max-w-6xl px-4 py-9 sm:px-6 sm:py-12">
        <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0 max-w-3xl">
            <div className="flex flex-wrap items-center gap-2"><span className="rounded-full bg-[#e8f4ec] px-3 py-1.5 text-[10px] font-black uppercase tracking-[0.14em] text-[#176b45]">{label(deal.county_id)}</span>{deal.verification_status && <span className="rounded-full border border-[#dfe7e2] bg-white/80 px-3 py-1.5 text-[10px] font-bold text-[#69766f]">{label(deal.verification_status)}</span>}<span className="rounded-full border border-[#e6ebe8] bg-white/75 px-3 py-1.5 text-[10px] font-bold text-[#87928c]">{evidenceLabel}</span></div>
            <h1 className="mt-4 text-3xl font-black tracking-[-0.04em] sm:text-5xl">{deal.address || 'Parcel opportunity'}</h1>
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-[#87928c]"><span className="font-mono">APN {deal.apn || params.apn}</span>{deal.lot_size_acres ? <><span className="hidden h-3 w-px bg-[#dce4df] sm:block"/><span>{deal.lot_size_acres.toLocaleString()} acres</span></> : null}</div>
          </div>
          <div className="flex items-center gap-4 self-start rounded-[1.5rem] border border-[#e1e9e4] bg-white/85 p-3 shadow-[0_18px_55px_rgba(23,42,32,.07)] lg:self-auto"><div className="hidden text-right sm:block"><p className="text-[10px] font-black uppercase tracking-[.14em] text-[#8b9690]">Screening signal</p><p className="mt-1 text-sm font-bold text-[#536159]">{deal.deal_score != null ? 'Worth a closer look' : 'Not scored'}</p></div><ScoreRing score={deal.deal_score}/></div>
        </div>
        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><Stat label="Asking price" value={money(deal.asking_price)}/><Stat label="Estimated ARV" value={`${money(deal.estimated_arv_low)}–${money(deal.estimated_arv_high)}`}/><Stat label="Estimated profit" value={`${money(deal.estimated_profit_low)}–${money(deal.estimated_profit_high)}`} accent/><Stat label="Recommended offer" value={`${money(deal.recommended_offer_low)}–${money(deal.recommended_offer_high)}`}/></div>
      </div>
    </section>

    <section className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">
      <div className="grid gap-5 lg:grid-cols-[1.35fr_.65fr]">
        <div className="space-y-5">
          <article className="rounded-[1.75rem] border border-[#e2e9e4] bg-white p-6 shadow-[0_14px_55px_rgba(23,42,32,.045)] sm:p-7">
            <div className="flex items-start justify-between gap-4"><div><p className="text-xs font-black uppercase tracking-[.16em] text-[#8b9690]">Decision brief</p><h2 className="mt-2 text-2xl font-black tracking-tight">What the record tells you</h2></div><span className="rounded-xl bg-[#edf5f0] px-3 py-2 text-xs font-black text-[#176b45]">{deal.deal_score != null ? `${deal.deal_score}/100` : 'Unscored'}</span></div>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-[#65726b]">DealScan combines the published record with available valuation and motivation signals to prioritize human review. It does not replace parcel research, title work, site checks, or your own underwriting.</p>
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              <div className="rounded-2xl border border-[#e6ece8] bg-[#f8faf9] p-4"><p className="text-[10px] font-black uppercase tracking-[.13em] text-[#8b9690]">Valuation basis</p><p className="mt-2 text-sm font-black text-[#27372f]">{label(deal.valuation_basis)}</p><p className="mt-1 text-xs leading-5 text-[#7a8780]">The published basis behind the available valuation signal.</p></div>
              <div className="rounded-2xl border border-[#e6ece8] bg-[#f8faf9] p-4"><p className="text-[10px] font-black uppercase tracking-[.13em] text-[#8b9690]">Motivation signals</p><p className="mt-2 text-sm font-black text-[#27372f]">{signalCount ? `${signalCount} published signal${signalCount === 1 ? '' : 's'}` : 'None published'}</p><p className="mt-1 text-xs leading-5 text-[#7a8780]">Signals are evidence to investigate, not proof of seller intent.</p></div>
            </div>
            {signalCount > 0 && <div className="mt-5 flex flex-wrap gap-2">{deal.motivation_signals?.map(signal => <span key={signal} className="rounded-full border border-[#dfe9e3] bg-[#eef6f1] px-3 py-1.5 text-xs font-bold text-[#35634d]">✓ {label(signal)}</span>)}</div>}
          </article>

          <article className="rounded-[1.75rem] border border-[#e2e9e4] bg-white p-6 sm:p-7">
            <div><p className="text-xs font-black uppercase tracking-[.16em] text-[#8b9690]">Before you act</p><h2 className="mt-2 text-2xl font-black tracking-tight">Verification path</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-[#718078]">Use the score to prioritize the parcel; use the checks below to decide whether it is actually actionable.</p></div>
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              {[['01','Records','Confirm parcel identity, ownership, title status and the current source record.'],['02','Site & planning','Confirm access, zoning, utilities, flood/buildability constraints and local requirements.'],['03','Valuation','Review the valuation basis and comparable evidence before relying on ARV or profit estimates.'],['04','Economics','Recalculate closing, holding, improvement, transaction and resale costs for your situation.']].map(([number,title,body]) => <div key={number} className="group rounded-2xl border border-[#e6ece8] bg-[#fafcfb] p-4 transition hover:-translate-y-0.5 hover:border-[#cbd9d0]"><div className="flex gap-3"><span className="font-mono text-[10px] font-bold text-[#176b45]">{number}</span><div><p className="text-sm font-black text-[#27372f]">{title}</p><p className="mt-1 text-xs leading-5 text-[#78847e]">{body}</p></div></div></div>)}
            </div>
          </article>
        </div>

        <aside className="space-y-5">
          <article className="overflow-hidden rounded-[1.75rem] bg-[#153025] p-6 text-white shadow-[0_20px_60px_rgba(21,48,37,.16)] sm:p-7">
            <div className="flex items-start justify-between gap-4"><div><p className="text-[10px] font-black uppercase tracking-[.16em] text-[#a9c7b7]">Evidence ledger</p><h2 className="mt-2 text-xl font-black">How strong is the signal?</h2></div><span className="rounded-full bg-white/10 px-2.5 py-1 text-[10px] font-bold text-white/65">Source-aware</span></div>
            <div className="mt-5"><EvidenceRow label="Valuation basis" value={label(deal.valuation_basis)} available={!!deal.valuation_basis}/><EvidenceRow label="Confidence" value={confidence != null ? `${confidence}%` : 'Not published'} available={confidence != null}/><EvidenceRow label="Verification" value={label(deal.verification_status)} available={!!deal.verification_status}/><EvidenceRow label="Source quality" value={label(deal.source_quality)} available={!!deal.source_quality}/><EvidenceRow label="Freshness" value={deal.data_freshness || 'Not published'} available={!!deal.data_freshness}/></div>
            {confidence != null && <div className="mt-5"><div className="mb-2 flex justify-between text-[10px] font-bold uppercase tracking-[.12em] text-white/45"><span>Valuation confidence</span><span>{confidence}%</span></div><div className="h-2 overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full bg-[#8fc3a6] transition-[width] duration-700" style={{ width: `${Math.max(0, Math.min(100, confidence))}%` }}/></div></div>}
            {deal.source_url && <a href={deal.source_url} target="_blank" rel="noreferrer" className="mt-6 flex items-center justify-center rounded-xl bg-white px-4 py-3 text-sm font-black text-[#153025] transition hover:-translate-y-0.5 hover:bg-[#e8f4ec]">Open source record ↗</a>}
          </article>

          <article className="rounded-[1.75rem] border border-[#e2e9e4] bg-white p-6">
            <div className="flex items-center justify-between gap-3"><div><p className="text-xs font-black uppercase tracking-[.16em] text-[#8b9690]">Parcel snapshot</p><h2 className="mt-1 text-lg font-black">Core record</h2></div><span className="grid h-9 w-9 place-items-center rounded-xl bg-[#edf5f0] text-[#176b45]">⌖</span></div>
            <div className="mt-5 space-y-3">{[['Lot size',deal.lot_size_acres ? `${deal.lot_size_acres.toLocaleString()} acres` : '—'],['County',label(deal.county_id)],['APN',deal.apn || params.apn],['Asking price',money(deal.asking_price)]].map(([caption,value]) => <div key={caption} className="flex justify-between gap-4 border-b border-[#edf0ee] pb-3 text-sm last:border-0 last:pb-0"><span className="text-[#7b8780]">{caption}</span><strong className={caption === 'APN' ? 'font-mono text-xs text-[#33423a]' : 'text-[#27372f]'}>{value}</strong></div>)}</div>
          </article>
        </aside>
      </div>
      <div className="mt-8 rounded-2xl border border-[#e4ebe7] bg-white px-5 py-4 text-xs leading-5 text-[#87928c]">DealScan scores are screening signals, not guarantees of value, title, buildability, or profit. Verify parcel and source records before making an offer or other investment decision.</div>
    </section>
  </main>
}
