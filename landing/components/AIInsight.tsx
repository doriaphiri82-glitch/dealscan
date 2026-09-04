'use client'

import { useState } from 'react'

const actions = [
  'Verify legal access',
  'Confirm tax status',
  'Check flood zone',
  'Verify zoning',
]

export default function AIInsight() {
  const [expanded, setExpanded] = useState(false)

  return (
    <section id="ai-intelligence" className="px-6 py-24 md:px-8" data-reveal>
      <div className="mx-auto max-w-5xl">
        <div className="mb-10 max-w-2xl">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-emerald-200/80 bg-white/70 px-3 py-1.5 font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-emerald-700 shadow-sm backdrop-blur">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 shadow-[0_0_0_4px_rgba(34,197,94,0.10)]" />
            AI Deal Intelligence
          </div>
          <h2 className="text-3xl font-bold tracking-[-0.03em] md:text-4xl">Turn a score into a decision.</h2>
          <p className="mt-3 text-[15px] leading-7 text-[#536158]">
            DealScan can layer a conservative AI review on top of its deterministic screening score — surfacing what stands out, what is missing, and what to verify next.
          </p>
        </div>

        <div className="glass-panel overflow-hidden rounded-[24px]">
          <div className="grid gap-0 lg:grid-cols-[1.05fr_1.95fr]">
            <div className="border-b border-[#1b442b]/10 p-6 lg:border-b-0 lg:border-r md:p-8">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-[#87948b]">AI recommendation</p>
                  <h3 className="mt-2 text-2xl font-bold">BUY · with verification</h3>
                </div>
                <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-center">
                  <div className="text-2xl font-bold text-emerald-700">0.82</div>
                  <div className="font-mono text-[9px] uppercase tracking-wider text-emerald-700/70">confidence</div>
                </div>
              </div>

              <div className="mt-7 rounded-2xl border border-[#1b442b]/10 bg-white/65 p-4">
                <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-wider text-[#78867d]">
                  <span>Deterministic DealScore</span><strong className="text-[#17211b]">87 / 100</strong>
                </div>
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-[#1b442b]/8">
                  <div className="h-full w-[87%] rounded-full bg-emerald-500 transition-all duration-1000" />
                </div>
              </div>

              <div className="mt-6 flex flex-wrap gap-2">
                {['Value lead', 'Absentee owner', 'Long hold'].map((signal) => (
                  <span key={signal} className="rounded-full border border-[#1b442b]/10 bg-white/60 px-3 py-1.5 text-[11px] font-medium text-[#536158]">{signal}</span>
                ))}
              </div>
            </div>

            <div className="p-6 md:p-8">
              <div className="rounded-2xl border border-[#1b442b]/10 bg-white/55 p-5">
                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-100 text-sm text-emerald-700">✦</span>
                  <div>
                    <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.1em] text-[#87948b]">Summary</p>
                    <p className="mt-1 text-sm font-medium leading-6 text-[#2f3c34]">Strong initial price signal, but access and zoning evidence should be verified before treating this as an actionable opportunity.</p>
                  </div>
                </div>
              </div>

              <div className="mt-6 grid gap-5 md:grid-cols-2">
                <div>
                  <h4 className="font-mono text-[10px] font-semibold uppercase tracking-[0.1em] text-[#87948b]">Why it stands out</h4>
                  <ul className="mt-3 space-y-2.5 text-[13px] leading-5 text-[#536158]">
                    <li>✓ Screening score clears the review threshold.</li>
                    <li>✓ Pricing signal is stronger than nearby examples.</li>
                    <li>✓ Ownership history provides a useful seller signal.</li>
                  </ul>
                </div>
                <div>
                  <h4 className="font-mono text-[10px] font-semibold uppercase tracking-[0.1em] text-[#87948b]">Risks / unknowns</h4>
                  <ul className="mt-3 space-y-2.5 text-[13px] leading-5 text-[#536158]">
                    <li>△ Legal access is not independently verified.</li>
                    <li>△ Zoning compatibility is unverified.</li>
                    <li>△ AI does not replace title, tax, or appraisal work.</li>
                  </ul>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setExpanded((value) => !value)}
                className="mt-7 flex w-full items-center justify-between rounded-2xl border border-[#1b442b]/10 bg-white/60 px-4 py-3 text-left text-[12px] font-semibold text-[#2f3c34] transition duration-200 hover:-translate-y-0.5 hover:bg-white/90"
                aria-expanded={expanded}
              >
                <span>Recommended verification checklist</span>
                <span className="text-lg leading-none text-emerald-600">{expanded ? '−' : '+'}</span>
              </button>

              {expanded && (
                <div className="mt-3 grid gap-2 sm:grid-cols-2" role="region">
                  {actions.map((action, index) => (
                    <div key={action} className="rounded-xl border border-[#1b442b]/10 bg-white/55 px-3 py-2.5 text-[12px] text-[#536158]">
                      <span className="mr-2 font-mono text-[10px] text-emerald-600">0{index + 1}</span>{action}
                    </div>
                  ))}
                </div>
              )}

              <p className="mt-5 font-mono text-[9px] uppercase tracking-[0.08em] text-[#87948b]">Illustrative UI · AI output is advisory and must not invent missing evidence.</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
