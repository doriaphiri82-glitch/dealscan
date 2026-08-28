const audiencePoints = [
  'Screen rural and vacant land opportunities.',
  'Research multiple properties before making contact.',
  'Need comparable-sales context for pricing.',
  'Want to identify obvious issues earlier.',
  'Are tired of jumping between listing sites, county records, maps, and spreadsheets.',
]

const traditionalChain = ['Listing', 'County website', 'Assessor', 'Tax records', 'Comparable sales', 'Maps', 'Spreadsheet', 'Decision']

export default function Audience() {
  return (
    <section className="py-24 px-6 md:px-8" id="who-its-for">
      <div className="max-w-6xl mx-auto">
        <div className="grid lg:grid-cols-2 gap-14 lg:gap-20 items-start" data-reveal>
          {/* Who it's for */}
          <div>
            <p className="font-mono text-[11px] font-semibold tracking-[0.12em] uppercase text-brand-500 mb-4">Who it&apos;s for</p>
            <h2 className="text-3xl md:text-4xl font-bold tracking-[-0.02em] mb-6 max-w-[420px]">
              Built for land investors who...
            </h2>
            <ul>
              {audiencePoints.map((point) => (
                <li key={point} className="flex items-start gap-3 py-2.5 border-b border-white/[0.04] last:border-0 text-[14px] text-[#A1A1AA] leading-[1.6]">
                  <span className="w-1 h-1 rounded-full bg-brand-500 flex-shrink-0 mt-2" aria-hidden="true" />
                  {point}
                </li>
              ))}
            </ul>
            <p className="text-[13px] text-[#52525B] mt-5 leading-[1.6]">
              DealScan is designed for vacant and rural land screening. It is not intended for every type of real-estate transaction, and it does not replace professional due diligence.
            </p>
          </div>

          {/* Manual research vs DealScan */}
          <div className="rounded-[10px] border border-white/[0.06] bg-[#161618] p-6">
            <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.08em] text-[#52525B] mb-5">The research problem</div>
            <div className="grid grid-cols-2 gap-6">
              <div>
                <div className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-[#71717A] mb-3">Traditional research</div>
                <ol className="space-y-0">
                  {traditionalChain.map((step, i) => (
                    <li key={step} className="relative pl-4 pb-3 last:pb-0 text-[12px] text-[#71717A]">
                      <span className="absolute left-0 top-[7px] w-1 h-1 rounded-full bg-[#52525B]" aria-hidden="true" />
                      {i < traditionalChain.length - 1 && (
                        <span className="absolute left-[1.5px] top-[13px] bottom-0 w-px bg-white/[0.06]" aria-hidden="true" />
                      )}
                      {step}
                    </li>
                  ))}
                </ol>
              </div>
              <div>
                <div className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-brand-500 mb-3">With DealScan</div>
                <ol>
                  {['Listing', 'Screened Deal Report'].map((step, i) => (
                    <li key={step} className="relative pl-4 pb-3 last:pb-0 text-[12px] text-[#E4E4E7]">
                      <span className="absolute left-0 top-[7px] w-1 h-1 rounded-full bg-brand-500" aria-hidden="true" />
                      {i < 1 && (
                        <span className="absolute left-[1.5px] top-[13px] bottom-0 w-px bg-brand-500/30" aria-hidden="true" />
                      )}
                      {step}
                    </li>
                  ))}
                </ol>
                <p className="text-[11px] text-[#52525B] mt-2 leading-[1.6]">Property, comps, seller, and risk signals in one structured report.</p>
              </div>
            </div>
            <p className="text-[12px] text-[#71717A] mt-5 pt-4 border-t border-white/[0.06] leading-[1.6]">
              DealScan reduces fragmented research into a single screening workflow. Verification with county and authoritative sources still happens before you buy.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}
