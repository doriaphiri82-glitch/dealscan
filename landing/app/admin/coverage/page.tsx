'use client'

import { useEffect, useMemo, useState } from 'react'

type County = {
  county_id: string
  county_name: string
  state: string
  tier: string | null
  tier_name: string | null
  status: string
  source_stage: string
  records: number
  published: number
  last_run: string | null
  data_freshness?: string | null
  validation_status?: string | null
  verification_status?: string | null
  registry_coverage_status?: string | null
  rejection_reasons: Record<string, number>
}

type Summary = {
  total: number
  total_counties?: number
  active: number
  live_validated: number
  ingestion_ready: number
  verified_opportunities: number
  degraded: number
  failed: number
  not_implemented: number
  skipped: number
}

type DashboardData = { coverage_summary: Summary; counties: County[]; generated_at: string }

function statusMeta(status: string) {
  const normalized = status === 'ok' ? 'active' : status
  if (normalized === 'active') return { label: 'Active', className: 'bg-emerald-50 text-emerald-700' }
  if (normalized === 'degraded') return { label: 'Degraded', className: 'bg-amber-50 text-amber-700' }
  if (normalized === 'failed' || normalized === 'error') return { label: 'Failed', className: 'bg-red-50 text-red-700' }
  if (normalized === 'skipped') return { label: 'Skipped', className: 'bg-black/5 text-black/55' }
  return { label: 'Not implemented', className: 'bg-black/5 text-black/55' }
}

export default function CoveragePage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [stateFilter, setStateFilter] = useState('all')

  useEffect(() => {
    fetch('/api/admin/coverage',{cache:'no-store',signal:AbortSignal.timeout(12000)})
      .then((res) => { if (!res.ok) throw new Error(`HTTP ${res.status}`); return res.json() })
      .then(setData)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false))
  }, [])

  const states = useMemo(() => Array.from(new Set(data?.counties.map((c) => c.state).filter(Boolean) ?? [])).sort(), [data])
  const filteredCounties = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (data?.counties ?? []).filter((c) => {
      const matchesQuery = !q || `${c.county_name} ${c.state}`.toLowerCase().includes(q)
      return matchesQuery && (stateFilter === 'all' || c.state === stateFilter)
    })
  }, [data, query, stateFilter])

  if (loading) return <div className="min-h-screen bg-[#f6f8f7] p-8 text-[#13221c]">Loading coverage…</div>
  if (error) return <div className="min-h-screen bg-[#f6f8f7] p-8 text-red-600">Error: {error}</div>
  if (!data) return <div className="min-h-screen bg-[#f6f8f7] p-8">No coverage data.</div>

  const stats = data.coverage_summary
  const totalCounties = stats.total_counties ?? stats.total
  return (
    <main className="min-h-screen bg-[#f6f8f7] p-6 text-[#13221c] md:p-10">
      <div className="mx-auto max-w-7xl">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-emerald-700">Operations</p>
            <h1 className="mt-2 text-3xl font-black tracking-tight md:text-4xl">Coverage dashboard</h1>
            <p className="mt-2 text-black/50">Persisted source readiness and current inventory. County geography is not national live parcel coverage.</p>
          </div>
          <a href="/deals" className="rounded-full bg-[#13221c] px-5 py-2.5 text-sm font-semibold text-white transition hover:-translate-y-px">Open deal explorer →</a>
        </div>

        <div className="mb-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ['Registered counties', totalCounties, 'text-[#13221c]'],
            ['Live validated', stats.live_validated, 'text-emerald-700'],
            ['Ingestion ready', stats.ingestion_ready, 'text-emerald-700'],
            ['Verified opportunities', stats.verified_opportunities, 'text-[#13221c]'],
          ].map(([label, value, tone]) => (
            <div key={String(label)} className="rounded-3xl border border-black/5 bg-white p-5 shadow-[0_15px_50px_rgba(0,0,0,0.04)]">
              <p className="text-sm text-black/45">{label}</p>
              <p className={`mt-2 text-3xl font-black ${tone}`}>{value}</p>
            </div>
          ))}
        </div>

        <div className="mb-5 flex flex-col gap-3 rounded-3xl border border-black/5 bg-white p-4 shadow-[0_15px_50px_rgba(0,0,0,0.04)] md:flex-row">
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search county or state…" className="min-w-0 flex-1 rounded-2xl border border-black/10 bg-[#fafbfa] px-4 py-3 text-sm outline-none transition focus:border-emerald-600" aria-label="Search counties" />
          <select value={stateFilter} onChange={(e) => setStateFilter(e.target.value)} className="rounded-2xl border border-black/10 bg-[#fafbfa] px-4 py-3 text-sm outline-none" aria-label="Filter by state">
            <option value="all">All states</option>
            {states.map((state) => <option key={state} value={state}>{state}</option>)}
          </select>
          <div className="flex items-center px-2 text-xs font-semibold text-black/40">{filteredCounties.length.toLocaleString()} shown</div>
        </div>

        <div className="overflow-hidden rounded-3xl border border-black/5 bg-white shadow-[0_15px_50px_rgba(0,0,0,0.04)]">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-black/[0.025] text-left text-xs uppercase tracking-wider text-black/45">
                <tr>{['Status', 'County', 'State', 'Coverage', 'Stored parcels', 'Published now', 'Source stage', 'Last run', 'Source freshness'].map((h) => <th key={h} className="whitespace-nowrap px-5 py-4 font-bold">{h}</th>)}</tr>
              </thead>
              <tbody>
                {filteredCounties.map((c) => {
                  const status = statusMeta(c.status)
                  const validation = c.source_stage.replaceAll('_', ' ')
                  return (
                    <tr key={c.county_id} className="border-t border-black/5 transition hover:bg-black/[0.015]">
                      <td className="px-5 py-4"><span className={`rounded-full px-2.5 py-1 text-xs font-bold ${status.className}`}>{status.label}</span></td>
                      <td className="whitespace-nowrap px-5 py-4 font-semibold">{c.county_name}</td>
                      <td className="px-5 py-4">{c.state}</td>
                      <td className="px-5 py-4"><span className="font-medium">{c.tier_name ?? c.tier ?? '—'}</span></td>
                      <td className="px-5 py-4 tabular-nums">{c.records.toLocaleString()}</td>
                      <td className="px-5 py-4 tabular-nums">{c.published.toLocaleString()}</td>
                      <td className="px-5 py-4"><span className="rounded-full bg-black/[0.035] px-2.5 py-1 text-xs font-semibold text-black/55">{validation}</span></td>
                      <td className="whitespace-nowrap px-5 py-4 text-black/50">{c.last_run ? new Date(c.last_run).toLocaleString() : '—'}</td>
                      <td className="whitespace-nowrap px-5 py-4 text-black/50">{c.data_freshness || 'Unknown'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {filteredCounties.length === 0 && <div className="p-10 text-center text-sm text-black/45">No counties match the current filters.</div>}
        </div>

        <p className="mt-4 text-xs text-black/35">Dashboard generated {new Date(data.generated_at).toLocaleString()}. Coverage labels reflect persisted registry evidence; source discovery or validation alone is not treated as published ETL data.</p>
      </div>
    </main>
  )
}
