'use client'

import { useEffect, useRef } from 'react'

const SCORE_FINAL = 87
const scoreBreakdown = [
  { label: 'Value', val: 91, evidence: 'Nearby sales suggest substantial price support.' },
  { label: 'Market', val: 79, evidence: 'Consistent recent sales activity in the immediate area.' },
  { label: 'Seller', val: 84, evidence: 'Long ownership + absentee ownership signal.' },
  { label: 'Access', val: 72, evidence: 'Legal access should be independently verified.' },
  { label: 'Risk', val: 88, evidence: 'No title or tax delinquency signals detected.' },
]

export default function SampleDeal() {
  const mapRef = useRef<HTMLDivElement>(null)
  const tableRef = useRef<HTMLTableElement>(null)
  const scoreRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const observers: IntersectionObserver[] = []

    // Parcel map sequence
    if (mapRef.current) {
      const mapObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const outline = document.getElementById('subjectOutline')
            const comps = ['comp1', 'comp2', 'comp3', 'comp4']
            if (prefersReduced) {
              outline?.classList.add('drawn')
              comps.forEach((id) => document.getElementById(id)?.classList.add('visible'))
            } else {
              setTimeout(() => outline?.classList.add('drawn'), 300)
              comps.forEach((id, i) => {
                setTimeout(() => document.getElementById(id)?.classList.add('visible'), 800 + i * 180)
              })
            }
            mapObserver.unobserve(entry.target)
          }
        })
      }, { threshold: 0.3 })
      mapObserver.observe(mapRef.current)
      observers.push(mapObserver)
    }

    // Comparable sales row reveal
    if (tableRef.current) {
      const tableObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const rows = entry.target.querySelectorAll('tbody tr')
            rows.forEach((row, i) => {
              if (prefersReduced) {
                row.classList.add('row-visible')
              } else {
                setTimeout(() => row.classList.add('row-visible'), i * 100)
              }
            })
            tableObserver.unobserve(entry.target)
          }
        })
      }, { threshold: 0.2 })
      tableObserver.observe(tableRef.current)
      observers.push(tableObserver)
    }

    // DealScore breakdown bars
    if (scoreRef.current) {
      const scoreObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const bars = entry.target.querySelectorAll<HTMLElement>('.score-bar-fill')
            bars.forEach((bar, i) => {
              if (prefersReduced) {
                bar.style.width = (bar.dataset.w ?? '0') + '%'
              } else {
                setTimeout(() => { bar.style.width = (bar.dataset.w ?? '0') + '%' }, i * 110)
              }
            })
            scoreObserver.unobserve(entry.target)
          }
        })
      }, { threshold: 0.3 })
      scoreObserver.observe(scoreRef.current)
      observers.push(scoreObserver)
    }

    return () => observers.forEach((o) => o.disconnect())
  }, [])

  return (
    <section className="py-24 px-6 md:px-8" id="deal-example">
      <div className="max-w-4xl mx-auto">
        <div className="mb-12" data-reveal>
          <p className="font-mono text-[11px] font-semibold tracking-[0.12em] uppercase text-brand-500 mb-4">Example Data</p>
          <h2 className="text-3xl md:text-4xl font-bold tracking-[-0.02em] mb-3 max-w-[560px]">
            See what a DealScan analysis looks like.
          </h2>
          <p className="text-[15px] text-[#A1A1AA]">This is demonstration data showing the type of analysis DealScan provides.</p>
        </div>

        <div className="rounded-[10px] border border-white/10 bg-[#161618] overflow-hidden shadow-[0_16px_40px_rgba(0,0,0,0.3)]" data-reveal>
          <div className="px-6 py-5 border-b border-white/[0.06] bg-[#111113] flex items-center justify-between">
            <div>
              <div className="font-semibold text-base">Cochise County, AZ</div>
              <div className="font-mono text-[11px] text-[#52525B] mt-0.5">APN 123-45-678A &middot; 2.31 acres</div>
            </div>
            <span className="font-mono text-[10px] font-semibold uppercase tracking-wide px-2 py-1 rounded bg-amber-500/10 text-amber-500">Demo — fictional data</span>
          </div>
          <div className="px-6 py-2.5 border-b border-white/[0.06] bg-[#111113]">
            <p className="text-[11px] text-[#71717A] leading-[1.6]">Illustrative example only. Property, pricing, comparable and risk data shown here are fictional and do not represent a real property.</p>
          </div>

          <div className="p-6 md:p-7">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mb-4">
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
                <div className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-[#52525B] mb-1">Deal Score</div>
                <div className="text-[22px] font-bold tracking-[-0.01em] tabular-nums">87 <span className="text-xs font-normal text-[#52525B]">/ 100</span></div>
              </div>
            </div>
            <p className="text-[12px] text-[#71717A] mb-9">Estimated value and spread are preliminary screening estimates, not appraisals.</p>

            {/* DealScore breakdown with evidence */}
            <div ref={scoreRef} className="p-5 rounded-[10px] bg-[#111113] border border-white/[0.06] mb-9">
              <div className="flex items-baseline justify-between mb-5">
                <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.08em] text-[#52525B]">Deal Score</div>
                <div className="flex items-baseline gap-1" aria-label="Deal score 87 out of 100">
                  <span className="text-[28px] font-bold text-brand-500 leading-none tabular-nums" aria-hidden="true">87</span>
                  <span className="text-[12px] text-[#52525B]">/ 100</span>
                </div>
              </div>
              <div className="md:grid md:grid-cols-2 md:gap-x-10">
                {scoreBreakdown.map((item) => (
                  <div key={item.label} className="py-3 border-b border-white/[0.04] last:border-b-0">
                    <div className="score-bar-row" style={{ padding: 0 }}>
                      <span className="score-bar-label">{item.label}</span>
                      <div className="score-bar-track"><div className="score-bar-fill" data-w={item.val} /></div>
                      <span className="score-bar-val">{item.val}</span>
                    </div>
                    <p className="text-[12px] text-[#71717A] leading-[1.6] mt-1.5">{item.evidence}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* How DealScore works */}
            <div className="mb-9 p-4 rounded-md border border-white/[0.06] bg-[#111113]">
              <h4 className="font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-[#52525B] mb-2">How DealScore works</h4>
              <p className="text-[13px] text-[#A1A1AA] leading-[1.7]">DealScore combines five screening dimensions — Value, Market, Seller, Access, and Risk — into a single 0–100 score that helps prioritize which parcels deserve a closer look. It is a screening aid for initial triage: not investment advice, not an appraisal, and not a guarantee of profitability. Verify findings independently before acting on them.</p>
            </div>

            {/* Signals + risk check */}
            <div className="grid md:grid-cols-2 gap-8 mb-9">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-[#52525B]">Screening signals</h4>
                  <span className="font-mono text-[9px] font-semibold uppercase tracking-wide text-[#52525B]">Preliminary</span>
                </div>
                <ul>
                  {[
                    { text: 'Below comparable pricing', warn: false },
                    { text: 'Absentee ownership', warn: false },
                    { text: 'Long ownership history (18 years)', warn: false },
                    { text: 'Tax history requires review', warn: true },
                  ].map((s) => (
                    <li key={s.text} className="flex items-start gap-2.5 py-[7px] border-b border-white/[0.06] last:border-0 text-[13px] text-[#A1A1AA]">
                      <span className={`text-xs w-4 text-center flex-shrink-0 ${s.warn ? 'text-amber-500' : 'text-brand-500'}`} aria-hidden="true">{s.warn ? '\u26A0' : '\u2713'}</span>
                      <span className="sr-only">{s.warn ? 'Review: ' : ''}</span>{s.text}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h4 className="font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-[#52525B] mb-3">Risk check</h4>
                <ul>
                  {[
                    { text: 'Legal and physical access', status: 'Preliminary' },
                    { text: 'Tax history', status: 'Needs review' },
                    { text: 'Zoning compatibility', status: 'Unverified' },
                    { text: 'Flood zone', status: 'Unverified' },
                    { text: 'Utilities availability', status: 'Unverified' },
                  ].map((s) => (
                    <li key={s.text} className="flex items-center justify-between gap-3 py-[7px] border-b border-white/[0.06] last:border-0 text-[13px] text-[#A1A1AA]">
                      <span className="flex items-center gap-2.5">
                        <span className="text-xs w-4 text-center flex-shrink-0 text-amber-500" aria-hidden="true">{'\u26A0'}</span>
                        {s.text}
                      </span>
                      <span className="font-mono text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-500 whitespace-nowrap">{s.status}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Suggested next steps */}
            <div className="mb-9">
              <h4 className="font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-[#52525B] mb-3">Suggested next steps</h4>
              <div className="flex flex-wrap gap-2">
                {['Verify legal access', 'Confirm tax status', 'Check flood zone maps', 'Verify zoning with county', 'Order title search'].map((step) => (
                  <span key={step} className="text-[12px] text-[#A1A1AA] border border-white/10 rounded-md px-3 py-1.5">{step}</span>
                ))}
              </div>
              <p className="text-[12px] text-[#71717A] mt-3">No data in this report has been independently verified. Screening is not a substitute for due diligence.</p>
            </div>

            {/* Comparable sales */}
            <div className="mb-9">
              <div className="flex items-center justify-between mb-3">
                <h4 className="font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-[#52525B]">Comparable Sales</h4>
                <span className="font-mono text-[9px] font-semibold uppercase tracking-wide text-[#52525B]">Example records</span>
              </div>
              <div className="overflow-x-auto -mx-1 px-1">
                <table ref={tableRef} className="comps-table w-full text-[13px] min-w-[540px]">
                  <thead>
                    <tr className="border-b border-white/10">
                      <th className="text-left font-mono text-[10px] font-semibold uppercase tracking-[0.06em] text-[#52525B] py-2.5 px-3">Property</th>
                      <th className="num font-mono text-[10px] font-semibold uppercase tracking-[0.06em] text-[#52525B] py-2.5 px-3">Distance</th>
                      <th className="num font-mono text-[10px] font-semibold uppercase tracking-[0.06em] text-[#52525B] py-2.5 px-3">Acres</th>
                      <th className="num font-mono text-[10px] font-semibold uppercase tracking-[0.06em] text-[#52525B] py-2.5 px-3">Sale Price</th>
                      <th className="num font-mono text-[10px] font-semibold uppercase tracking-[0.06em] text-[#52525B] py-2.5 px-3">$/Acre</th>
                      <th className="num font-mono text-[10px] font-semibold uppercase tracking-[0.06em] text-[#52525B] py-2.5 px-3">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ['Lot 8, Sierra Vista Estates', '0.3 mi', '2.1', '$8,500', '$4,048', 'Jun 2026'],
                      ['Lot 14, Sierra Vista Estates', '0.5 mi', '2.5', '$11,200', '$4,480', 'May 2026'],
                      ['Lot 3, Sierra Vista Estates', '0.7 mi', '1.8', '$7,800', '$4,333', 'Apr 2026'],
                      ['Lot 22, Sierra Vista Estates', '0.9 mi', '2.4', '$9,400', '$3,917', 'Mar 2026'],
                    ].map((row) => (
                      <tr key={row[0]} className="table-row-reveal border-b border-white/[0.06] last:border-0 hover:bg-white/[0.02] transition-colors">
                        <td className="py-2.5 px-3 text-white">{row[0]}</td>
                        <td className="num py-2.5 px-3 text-[#A1A1AA]">{row[1]}</td>
                        <td className="num py-2.5 px-3 text-[#A1A1AA]">{row[2]}</td>
                        <td className="num py-2.5 px-3 text-[#A1A1AA]">{row[3]}</td>
                        <td className="num py-2.5 px-3 font-semibold text-[#E4E4E7]">{row[4]}</td>
                        <td className="num py-2.5 px-3 text-[#A1A1AA]">{row[5]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Parcel map */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h4 className="font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-[#52525B]">Parcel Map</h4>
                <span className="font-mono text-[9px] font-semibold uppercase tracking-wide text-[#52525B]">Stylized &mdash; Example</span>
              </div>
              <div ref={mapRef} className="rounded-md border border-white/[0.06] bg-[#111113] p-4">
                <svg viewBox="0 0 400 220" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-auto" role="img" aria-label="Stylized vicinity map showing the subject parcel, neighboring parcels, a road, and four comparable sales markers">
                  <defs>
                    <pattern id="mapGrid" width="20" height="20" patternUnits="userSpaceOnUse">
                      <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="0.5"/>
                    </pattern>
                  </defs>
                  <rect width="400" height="220" fill="url(#mapGrid)"/>
                  <path d="M 0 140 L 400 140" stroke="rgba(255,255,255,0.12)" strokeWidth="8" strokeLinecap="round"/>
                  <path d="M 0 140 L 400 140" stroke="rgba(255,255,255,0.06)" strokeWidth="1" strokeDasharray="8 6"/>
                  <text x="360" y="135" fill="rgba(255,255,255,0.25)" fontSize="8" fontFamily="monospace">ROAD</text>
                  <rect x="40" y="30" width="80" height="90" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="1" rx="1"/>
                  <rect x="130" y="30" width="80" height="90" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="1" rx="1"/>
                  <rect x="310" y="30" width="70" height="90" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="1" rx="1"/>
                  <rect x="40" y="155" width="80" height="50" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="1" rx="1"/>
                  <rect x="310" y="155" width="70" height="50" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="1" rx="1"/>
                  <rect x="220" y="30" width="80" height="90" fill="rgba(34,197,94,0.12)" rx="1"/>
                  <rect id="subjectOutline" x="220" y="30" width="80" height="90" fill="none" stroke="#22C55E" strokeWidth="1.5" rx="1" className="parcel-outline"/>
                  <text x="240" y="80" fill="#22C55E" fontSize="9" fontWeight="600" fontFamily="monospace">SUBJECT</text>
                  <text x="240" y="93" fill="rgba(255,255,255,0.4)" fontSize="7" fontFamily="monospace">2.31 ac</text>
                  <g id="comp1" className="comp-marker">
                    <circle cx="80" cy="75" r="4" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="1"/>
                    <circle cx="80" cy="75" r="1.5" fill="rgba(255,255,255,0.5)"/>
                    <text x="88" y="78" fill="rgba(255,255,255,0.35)" fontSize="7" fontFamily="monospace">$4,048/ac</text>
                  </g>
                  <g id="comp2" className="comp-marker">
                    <circle cx="170" cy="60" r="4" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="1"/>
                    <circle cx="170" cy="60" r="1.5" fill="rgba(255,255,255,0.5)"/>
                    <text x="178" y="63" fill="rgba(255,255,255,0.35)" fontSize="7" fontFamily="monospace">$4,480/ac</text>
                  </g>
                  <g id="comp3" className="comp-marker">
                    <circle cx="345" cy="70" r="4" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="1"/>
                    <circle cx="345" cy="70" r="1.5" fill="rgba(255,255,255,0.5)"/>
                    <text x="318" y="88" fill="rgba(255,255,255,0.35)" fontSize="7" fontFamily="monospace">$4,333/ac</text>
                  </g>
                  <g id="comp4" className="comp-marker">
                    <circle cx="80" cy="180" r="4" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="1"/>
                    <circle cx="80" cy="180" r="1.5" fill="rgba(255,255,255,0.5)"/>
                    <text x="88" y="183" fill="rgba(255,255,255,0.35)" fontSize="7" fontFamily="monospace">$3,917/ac</text>
                  </g>
                </svg>
                {/* Map metadata — makes the map read as software, not artwork */}
                <dl className="grid grid-cols-3 gap-3 mt-4 pt-4 border-t border-white/[0.06]">
                  <div>
                    <dt className="font-mono text-[9px] font-medium uppercase tracking-[0.08em] text-[#52525B] mb-0.5">Parcel</dt>
                    <dd className="font-mono text-[12px] font-semibold text-[#E4E4E7] tabular-nums">2.31 ac</dd>
                  </div>
                  <div>
                    <dt className="font-mono text-[9px] font-medium uppercase tracking-[0.08em] text-[#52525B] mb-0.5">Comps</dt>
                    <dd className="font-mono text-[12px] font-semibold text-[#E4E4E7] tabular-nums">4 found</dd>
                  </div>
                  <div>
                    <dt className="font-mono text-[9px] font-medium uppercase tracking-[0.08em] text-[#52525B] mb-0.5">Radius</dt>
                    <dd className="font-mono text-[12px] font-semibold text-[#E4E4E7] tabular-nums">1.0 mi</dd>
                  </div>
                </dl>
              </div>
            </div>
          </div>
          {/* Report footer */}
          <div className="px-6 py-3 border-t border-white/[0.06] bg-[#111113] flex items-center justify-between font-mono text-[11px] text-[#52525B]">
            <span>Demo dataset &middot; illustrative</span>
            <span>DEMO DATA</span>
          </div>
        </div>
      </div>
    </section>
  )
}