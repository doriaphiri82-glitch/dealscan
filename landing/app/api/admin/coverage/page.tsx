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

type DashboardData = {
  coverage_summary: Summary
  counties: County[]
  generated_at: string
}

export default function CoveragePage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/admin/coverage')
      .then((res) => res.json())
      .then(setData)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8">Loading...</div>
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>
  if (!data) return <div className="p-8">No data</div>

  const stats = data.coverage_summary

  return (
    <div className="min-h-screen bg-[#0A0A0B] text-[#F4F4F5] p-8">
      <h1 className="text-2xl font-bold mb-4">DealScan Admin — Coverage Dashboard</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white border rounded-lg p-4">
          <div className="text-gray-500 text-sm">Total Counties</div>
          <div className="text-2xl font-bold">{stats.total_counties}</div>
        </div>
        <div className="bg-white border rounded-lg p-4">
          <div className="text-gray-500 text-sm">Active</div>
          <div className="text-2xl font-bold text-green-600">{stats.active}</div>
        </div>
        <div className="bg-white border rounded-lg p-4">
          <div className="text-gray-500 text-sm">Degraded</div>
          <div className="text-2xl font-bold text-yellow-600">{stats.degraded}</div>
        </div>
        <div className="bg-white border rounded-lg p-4">
          <div className="text-gray-500 text-sm">Failed</div>
          <div className="text-2xl font-bold text-red-600">{stats.failed}</div>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse bg-white border rounded-lg overflow-hidden">
          <thead>
            <tr className="bg-gray-100">
              <th className="text-left p-3 border-b">Status</th>
              <th className="text-left p-3 border-b">County</th>
              <th className="text-left p-3 border-b">State</th>
              <th className="text-left p-3 border-b">Tier</th>
              <th className="text-left p-3 border-b">Records</th>
              <th className="text-left p-3 border-b">Published</th>
              <th className="text-left p-3 border-b">Last Run</th>
            </tr>
          </thead>
          <tbody>
            {data.counties.map((c) => (
              <tr key={c.county_id} className="border-b last:border-0">
                <td className="p-3">
                  <span
                    className={`inline-block px-2 py-1 rounded text-xs font-medium ${
                      c.status === 'active'
                        ? 'bg-green-100 text-green-800'
                        : c.status === 'failed'
                        ? 'bg-red-100 text-red-800'
                        : c.status === 'degraded'
                        ? 'bg-yellow-100 text-yellow-800'
                        : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {c.status}
                  </span>
                </td>
                <td className="p-3">{c.county_name}</td>
                <td className="p-3">{c.state}</td>
                <td className="p-3">{c.tier_name ?? c.tier ?? '-'}</td>
                <td className="p-3">{c.records}</td>
                <td className="p-3">{c.published}</td>
                <td className="p-3">
                  {c.last_run ? new Date(c.last_run).toLocaleString() : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
