'use client'

import { useEffect, useState } from 'react'

type County = {
  county_id: string
  county_name: string
  state: string
  tier: number | null
  tier_name: string | null
  status: string
  records: number
  published: number
  last_run: string | null
  rejection_reasons: Record<string, number>
}

type Summary = {
  total_counties: number
  active: number
  degraded: number
  failed: number
  not_implemented: number
  skipped: number
}

type DashboardData = { coverage_summary: Summary; counties: County[]; generated_at: string }

export default function CoveragePage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/admin/coverage')
      .then((res) => { if (!res.ok) throw new Error(`HTTP ${res.status}`); return res.json() })
      .then(setData)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="min-h-screen bg-[#f6f8f7] p-8 text-[#13221c]">Loading coverage…</div>
  if (error) return <div className="min-h-screen bg-[#f6f8f7] p-8 text-red-600">Error: {error}</div>
  if (!data) return <div className="min-h-screen bg-[#f6f8f7] p-8">No coverage data.</div>

  const stats = data.coverage_summary
  return (
    <main className="min-h-screen bg-[#f6f8f7] p-6 text-[#13221c] md:p-10">
      <div className="mx-auto max-w-7xl">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div><p className="text-xs font-bold uppercase tracking-[0.2em] text-emerald-700">Operations</p><h1 className="mt-2 text-3xl font-black tracking-tight md:text-4xl">Coverage dashboard</h1><p className="mt-2 text-black/50">Source health and verified ETL coverage.</p></div>
          <a href="/deals" className="rounded-full bg-[#13221c] px-5 py-2.5 text-sm font-semibold text-white transition hover:-translate-y-px">Open deal explorer →</a>
        </div>
        <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[['Total Counties', stats.total_counties, 'text-[#13221c]'], ['Active', stats.active, 'text-emerald-700'], ['Degraded', stats.degraded, 'text-amber-700'], ['Failed', stats.failed, 'text-red-700']].map(([label, value, tone]) => <div key={String(label)} className="rounded-3xl border border-black/5 bg-white p-5 shadow-[0_15px_50px_rgba(0,0,0,0.04)]"><p className="text-sm text-black/45">{label}</p><p className={`mt-2 text-3xl font-black ${tone}`}>{value}</p></div>)}
        </div>
        <div className="overflow-hidden rounded-3xl border border-black/5 bg-white shadow-[0_15px_50px_rgba(0,0,0,0.04)]"><div className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-black/[0.025] text-left text-xs uppercase tracking-wider text-black/45"><tr>{['Status','County','State','Tier','Records','Published','Last Run'].map((h) => <th key={h} className="whitespace-nowrap px-5 py-4 font-bold">{h}</th>)}</tr></thead><tbody>{data.counties.map((c) => <tr key={c.county_id} className="border-t border-black/5"><td className="px-5 py-4"><span className={`rounded-full px-2.5 py-1 text-xs font-bold ${c.status === 'active' ? 'bg-emerald-50 text-emerald-700' : c.status === 'failed' ? 'bg-red-50 text-red-700' : c.status === 'degraded' ? 'bg-amber-50 text-amber-700' : 'bg-black/5 text-black/55'}`}>{c.status}</span></td><td className="whitespace-nowrap px-5 py-4 font-semibold">{c.county_name}</td><td className="px-5 py-4">{c.state}</td><td className="px-5 py-4">{c.tier_name ?? c.tier ?? '—'}</td><td className="px-5 py-4">{c.records.toLocaleString()}</td><td className="px-5 py-4">{c.published.toLocaleString()}</td><td className="whitespace-nowrap px-5 py-4 text-black/50">{c.last_run ? new Date(c.last_run).toLocaleString() : '—'}</td></tr>)}</tbody></table></div></div>
      </div>
    </main>
  )
}
