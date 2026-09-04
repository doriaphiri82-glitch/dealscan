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
          <div>
            <p className="font-mono text-[11px] font-semibold tracking-[0.12em] uppercase text-brand-500 mb-4">Who it&apos;s for</p>
            <h2 className="text-3xl md:text-4xl font-bold tracking-[-0.02em] mb-6 max-w-[420px] text-[#15211b]">
              Built for land investors who want clarity before they act.
            </h2>
            <ul className="dealscan-card divide-y divide-[#e5ebe7]">
              {audiencePoints.map((point) => (
                <li key={point} className="flex items-start gap-3 px-5 py-3.5 text-[14px] text-[#64716a] leading-[1.6]">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#176b45] flex-shrink-0 mt-2" aria-hidden="true" />
                  {point}
                </li>
              ))}
            </ul>
            <p className="text-[13px] text-[#8a958f] mt-5 leading-[1.6] max-w-[520px]">
              DealScan is designed for vacant and rural land screening. It is not intended for every type of real-estate transaction, and it does not replace professional due diligence.
            </p>
          </div>

          <div className="dealscan-card p-6 md:p-7 relative overflow-hidden">
            <div className="absolute -right-10 -top-10 w-36 h-36 rounded-full bg-[#e5f2ea] blur-2xl opacity-70" aria-hidden="true" />
            <div className="relative">
              <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.08em] text-[#8a958f] mb-5">The research problem</div>
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <div className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-[#8a958f] mb-3">Traditional research</div>
                  <ol>
                    {traditionalChain.map((step, i) => (
                      <li key={step} className="relative pl-4 pb-3 last:pb-0 text-[12px] text-[#7a867f]">
                        <span className="absolute left-0 top-[7px] w-1 h-1 rounded-full bg-[#aeb8b2]" aria-hidden="true" />
                        {i < traditionalChain.length - 1 && <span className="absolute left-[1.5px] top-[13px] bottom-0 w-px bg-[#dfe6e1]" aria-hidden="true" />}
                        {step}
                      </li>
                    ))}
                  </ol>
                </div>
                <div>
                  <div className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-[#176b45] mb-3">With DealScan</div>
                  <ol>
                    {['Listing', 'Screened Deal Report'].map((step, i) => (
                      <li key={step} className="relative pl-4 pb-3 last:pb-0 text-[12px] font-medium text-[#26352d]">
                        <span className="absolute left-0 top-[7px] w-1 h-1 rounded-full bg-[#176b45]" aria-hidden="true" />
                        {i < 1 && <span className="absolute left-[1.5px] top-[13px] bottom-0 w-px bg-[#b9d9c6]" aria-hidden="true" />}
                        {step}
                      </li>
                    ))}
                  </ol>
                  <p className="text-[11px] text-[#8a958f] mt-2 leading-[1.6]">Property, comps, seller, and risk signals in one structured report.</p>
                </div>
              </div>
              <p className="text-[12px] text-[#7a867f] mt-5 pt-4 border-t border-[#e5ebe7] leading-[1.6]">
                DealScan reduces fragmented research into a single screening workflow. Verification with county and authoritative sources still happens before you buy.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
