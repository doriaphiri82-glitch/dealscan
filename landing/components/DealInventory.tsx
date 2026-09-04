'use client'

import { useEffect, useMemo, useState } from 'react'
import { Deal, fetchTopDeals } from '@/lib/deals'

const COUNTY_NAMES: Record<string, string> = {
  cochise_az: 'Cochise County, AZ',
  mohave_az: 'Mohave County, AZ',
  el_paso_tx: 'El Paso County, TX',
  yavapai_az: 'Yavapai County, AZ',
  washoe_nv: 'Washoe County, NV',
  pinal_az: 'Pinal County, AZ',
  hudson_co: 'Huerfano County, CO',
  socorro_nm: 'Socorro County, NM',
}

function money(value: number | null | undefined) {
  if (value == null) return '—'
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value)
}

function verdict(deal: Deal) {
  return deal.ai_analysis?.verdict?.replace('_', ' ') || (deal.deal_score >= 80 ? 'strong buy' : deal.deal_score >= 70 ? 'buy' : 'watch')
}

export default function DealInventory() {
  const [deals, setDeals] = useState<Deal[]>([])
  const [status, setStatus] = useState('loading')
  const [county, setCounty] = useState('all')
  const [minimumScore, setMinimumScore] = useState('0')

  useEffect(() => {
    let active = true
    fetchTopDeals(50).then((response) => {
      if (!active) return
      setDeals(response.deals || [])
      setStatus(response.deals?.length ? 'ready' : 'empty')
    })
    return () => { active = false }
  }, [])

  const counties = useMemo(() => Array.from(new Set(deals.map((deal) => deal.county_id))), [deals])
  const filtered = useMemo(() => deals
    .filter((deal) => county === 'all' || deal.county_id === county)
    .filter((deal) => deal.deal_score >= Number(minimumScore))
    .sort((a, b) => b.deal_score - a.deal_score), [deals, county, minimumScore])

  return (
    <section id="deal-inventory" className="px-6 py-24 md:px-8" data-reveal>
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div className="max-w-2xl">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-emerald-200/80 bg-white/70 px-3 py-1.5 font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-emerald-700 shadow-sm backdrop-blur">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 shadow-[0_0_0_4px_rgba(34,197,94,0.10)]" />
              Live screened inventory
            </div>
            <h2 className="text-3xl font-bold tracking-[-0.03em] md:text-4xl">See the deals DealScan actually found.</h2>
            <p className="mt-3 text-[15px] leading-7 text-[#536158]">Only published pipeline records appear here. No fabricated parcel, price, valuation, or AI result is substituted for live data.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <select value={county} onChange={(e) => setCounty(e.target.value)} className="rounded-xl border border-[#1b442b]/10 bg-white/75 px-3 py-2 text-xs font-medium text-[#2f3c34] outline-none focus:ring-2 focus:ring-emerald-400/30">
              <option value="all">All counties</option>
              {counties.map((id) => <option key={id} value={id}>{COUNTY_NAMES[id] || id}</option>)}
            </select>
            <select value={minimumScore} onChange={(e) => setMinimumScore(e.target.value)} className="rounded-xl border border-[#1b442b]/10 bg-white/75 px-3 py-2 text-xs font-medium text-[#2f3c34] outline-none focus:ring-2 focus:ring-emerald-400/30">
              <option value="0">Any score</option>
              <option value="70">70+ review</option>
              <option value="80">80+ strong</option>
              <option value="90">90+ elite</option>
            </select>
          </div>
        </div>

        {status === 'loading' && <div className="mt-10 glass-panel rounded-[24px] p-8 text-sm text-[#536158] animate-pulse">Loading current screened inventory…</div>}

        {status === 'empty' && <div className="mt-10 glass-panel rounded-[24px] border-dashed p-10 text-center"><div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-50 text-xl text-emerald-700">⌁</div><h3 className="mt-4 text-lg font-semibold">No live deals published yet</h3><p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-[#65736a]">The pipeline is running, but no parcel has cleared the current screening and publication gates. The demo below remains separate from live inventory.</p></div>}

        {status === 'ready' && filtered.length === 0 && <div className="mt-10 glass-panel rounded-[24px] p-8 text-sm text-[#536158]">No published deals match these filters.</div>}

        {filtered.length > 0 && <div className="mt-10 grid gap-4 lg:grid-cols-2">
          {filtered.map((deal) => <article key={`${deal.county_id}-${deal.apn}`} className="glass-panel group rounded-[24px] p-5 transition duration-300 hover:-translate-y-1 hover:shadow-[0_20px_60px_rgba(27,68,43,0.10)]">
            <div className="flex items-start justify-between gap-4">
              <div><p className="font-mono text-[10px] uppercase tracking-[0.12em] text-[#87948b]">{COUNTY_NAMES[deal.county_id] || deal.county_id}</p><h3 className="mt-1 text-lg font-semibold text-[#17211b]">{deal.address || 'Address not supplied'}</h3><p className="mt-1 font-mono text-[10px] text-[#87948b]">APN {deal.apn}</p></div>
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-center"><div className="text-2xl font-bold text-emerald-700">{deal.deal_score}</div><div className="font-mono text-[9px] uppercase tracking-wider text-emerald-700/70">score</div></div>
            </div>
            <div className="mt-5 grid grid-cols-3 gap-2 text-center">
              <div className="rounded-xl bg-white/60 p-3"><p className="font-mono text-[9px] uppercase text-[#87948b]">Acres</p><p className="mt-1 text-sm font-semibold">{deal.lot_size_acres ?? '—'}</p></div>
              <div className="rounded-xl bg-white/60 p-3"><p className="font-mono text-[9px] uppercase text-[#87948b]">Ask</p><p className="mt-1 text-sm font-semibold">{money(deal.asking_price)}</p></div>
              <div className="rounded-xl bg-white/60 p-3"><p className="font-mono text-[9px] uppercase text-[#87948b]">AI</p><p className="mt-1 text-sm font-semibold capitalize">{verdict(deal)}</p></div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2 text-[10px] text-[#65736a]">
              {deal.zoning && <span className="rounded-full border border-[#1b442b]/10 bg-white/60 px-2.5 py-1">Zoning: {deal.zoning}</span>}
              {deal.tax_delinquent_years != null && <span className="rounded-full border border-[#1b442b]/10 bg-white/60 px-2.5 py-1">Tax signal: {deal.tax_delinquent_years}y</span>}
              <span className="rounded-full border border-[#1b442b]/10 bg-white/60 px-2.5 py-1">Screening only</span>
            </div>
            {deal.ai_analysis?.summary && <p className="mt-4 rounded-xl bg-emerald-50/70 px-3 py-2.5 text-xs leading-5 text-[#405047]">{deal.ai_analysis.summary}</p>}
          </article>)}
        </div>}
      </div>
    </section>
  )
}
