const sources = [
  'County assessor records',
  'GIS parcel maps',
  'Tax records',
  'Listing sites',
  'Comparable sales',
  'Zoning documents',
]

export default function Problem() {
  return (
    <section className="py-24 px-6 md:px-8">
      <div className="max-w-6xl mx-auto">
        <div className="grid lg:grid-cols-2 gap-14 lg:gap-20 items-center" data-reveal>
          <div>
            <p className="font-mono text-[11px] font-semibold tracking-[0.12em] uppercase text-brand-500 mb-4">The Problem</p>
            <h2 className="text-3xl md:text-4xl font-bold tracking-[-0.02em] mb-5">
              Finding the parcel is often harder than evaluating it.
            </h2>
            <p className="text-[15px] text-[#A1A1AA] leading-[1.75] max-w-[520px]">
              Land investors spend hours jumping between county assessor websites, GIS maps, tax records, listings, and zoning documents. The problem isn&apos;t a lack of data. The problem is that the useful signals are scattered.
            </p>
          </div>

          {/* Scattered sources → DealScan */}
          <div className="rounded-[10px] border border-white/[0.06] bg-[#161618] p-6">
            <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.08em] text-[#52525B] mb-4">Where the signals live today</div>
            <ul className="space-y-2 mb-5">
              {sources.map((source) => (
                <li key={source} className="flex items-center gap-3 text-[13px] text-[#A1A1AA] py-1.5 border-b border-white/[0.04] last:border-0">
                  <span className="w-1 h-1 rounded-full bg-[#52525B] flex-shrink-0" aria-hidden="true" />
                  {source}
                </li>
              ))}
            </ul>
            <div className="flex items-center gap-3 rounded-md border border-white/[0.06] bg-[#111113] px-4 py-3">
              <span className="text-[13px] font-bold tracking-[0.02em] text-white">DEAL<span className="text-brand-500">SCAN</span></span>
              <span className="text-xs text-[#52525B]">One screened report per parcel.</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
