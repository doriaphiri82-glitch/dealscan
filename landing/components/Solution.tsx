/* Miniature product UIs — one per capability. Demonstration data. */

function PropertyDataUI() {
  const rows = [
    { label: 'APN', value: '123-45-678A' },
    { label: 'Acres', value: '2.31' },
    { label: 'Asking', value: '$4,900' },
    { label: 'Ownership', value: '18 years' },
  ]
  return (
    <div>
      <div className="flex items-baseline justify-between mb-4">
        <span className="text-sm font-semibold text-white">Cochise County, AZ</span>
        <span className="font-mono text-[9px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-500">Example</span>
      </div>
      <dl>
        {rows.map((row) => (
          <div key={row.label} className="flex items-center justify-between py-2.5 border-b border-white/[0.06] last:border-0">
            <dt className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-[#52525B]">{row.label}</dt>
            <dd className="text-[13px] font-semibold text-[#E4E4E7] tabular-nums">{row.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

function ComparableSalesUI() {
  const rows = [
    { name: 'Lot 8', dist: '0.3 mi', acres: '2.1', price: '$8,500', ppa: '$4,048' },
    { name: 'Lot 14', dist: '0.5 mi', acres: '2.5', price: '$11,200', ppa: '$4,480' },
    { name: 'Lot 3', dist: '0.7 mi', acres: '1.8', price: '$7,800', ppa: '$4,333' },
  ]
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[12px] comps-table">
        <thead>
          <tr className="border-b border-white/10">
            <th className="text-left font-mono text-[9px] font-semibold uppercase tracking-[0.06em] text-[#52525B] py-2 pr-3">Property</th>
            <th className="num font-mono text-[9px] font-semibold uppercase tracking-[0.06em] text-[#52525B] py-2 px-3">Dist</th>
            <th className="num font-mono text-[9px] font-semibold uppercase tracking-[0.06em] text-[#52525B] py-2 px-3">Ac</th>
            <th className="num font-mono text-[9px] font-semibold uppercase tracking-[0.06em] text-[#52525B] py-2 px-3">Price</th>
            <th className="num font-mono text-[9px] font-semibold uppercase tracking-[0.06em] text-[#52525B] py-2 pl-3">$/Ac</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.name} className="border-b border-white/[0.06] last:border-0">
              <td className="py-2 pr-3 text-[#A1A1AA]">{row.name}</td>
              <td className="num py-2 px-3 text-[#A1A1AA]">{row.dist}</td>
              <td className="num py-2 px-3 text-[#A1A1AA]">{row.acres}</td>
              <td className="num py-2 px-3 text-[#A1A1AA]">{row.price}</td>
              <td className="num py-2 pl-3 font-semibold text-[#E4E4E7]">{row.ppa}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SellerSignalsUI() {
  const rows = [
    { label: 'Absentee owner', value: 'Detected', tone: 'ok' },
    { label: 'Ownership length', value: '18 years', tone: 'neutral' },
    { label: 'Listing history', value: 'No recent listing', tone: 'neutral' },
    { label: 'Tax signal', value: 'Review', tone: 'warn' },
  ]
  return (
    <ul>
      {rows.map((row) => (
        <li key={row.label} className="flex items-center justify-between py-2.5 border-b border-white/[0.06] last:border-0">
          <span className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-[#52525B]">{row.label}</span>
          <span className={`font-mono text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded ${
            row.tone === 'ok' ? 'bg-brand-500/10 text-brand-500' : row.tone === 'warn' ? 'bg-amber-500/10 text-amber-500' : 'bg-white/[0.04] text-[#A1A1AA]'
          }`}>{row.value}</span>
        </li>
      ))}
    </ul>
  )
}

function RiskFlagsUI() {
  const rows = [
    { label: 'Legal access', value: 'Review', warn: true },
    { label: 'Utilities', value: 'Review', warn: true },
    { label: 'Zoning', value: 'Appears compatible', warn: false },
    { label: 'Flood', value: 'Review', warn: true },
  ]
  return (
    <ul>
      {rows.map((row) => (
        <li key={row.label} className="flex items-center justify-between py-2.5 border-b border-white/[0.06] last:border-0">
          <span className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-[#52525B]">{row.label}</span>
          <span className={`text-[12px] font-medium ${row.warn ? 'text-amber-500' : 'text-brand-500'}`}>{row.value}</span>
        </li>
      ))}
    </ul>
  )
}

const features = [
  {
    num: '01',
    title: 'Property Data',
    description: 'Start with the parcel itself \u2014 acreage, asking price, ownership history, location, and available property records, consolidated into one view.',
    ui: <PropertyDataUI />,
  },
  {
    num: '02',
    title: 'Comparable Sales',
    description: 'Understand how nearby land has actually traded. Price-per-acre benchmarks so you can assess whether a listing is priced below market.',
    ui: <ComparableSalesUI />,
  },
  {
    num: '03',
    title: 'Seller Signals',
    description: 'Absentee ownership, long holding periods, and tax indicators are surfaced so you can prioritize which owners to contact first.',
    ui: <SellerSignalsUI />,
  },
  {
    num: '04',
    title: 'Risk Flags',
    description: 'Access concerns, utility gaps, flood zone status, and zoning questions are highlighted \u2014 so you know exactly what to verify before making an offer.',
    ui: <RiskFlagsUI />,
  },
]

export default function Solution() {
  return (
    <section className="py-24 px-6 md:px-8 bg-[#111113] border-y border-white/[0.06]" id="capabilities">
      <div className="max-w-6xl mx-auto">
        <div className="mb-6" data-reveal>
          <p className="font-mono text-[11px] font-semibold tracking-[0.12em] uppercase text-brand-500 mb-4">Capabilities</p>
          <h2 className="text-3xl md:text-4xl font-bold tracking-[-0.02em] max-w-[560px]">
            Built around the signals that matter.
          </h2>
        </div>

        <div className="space-y-0">
          {features.map((feature, i) => (
            <div
              key={feature.num}
              className={`grid md:grid-cols-2 gap-10 lg:gap-16 items-center py-12 lg:py-14 ${i > 0 ? 'border-t border-white/[0.06]' : ''}`}
              data-reveal
            >
              <div className={i % 2 === 1 ? 'md:order-2' : ''}>
                <span className="font-mono text-[11px] font-semibold text-brand-500 tracking-[0.08em] block mb-3">{feature.num}</span>
                <h3 className="text-[22px] font-semibold mb-3">{feature.title}</h3>
                <p className="text-[15px] text-[#A1A1AA] leading-[1.75] max-w-[420px]">{feature.description}</p>
              </div>
              <div className={`p-6 rounded-[10px] border border-white/[0.06] bg-[#161618] hover:border-white/10 transition-colors ${i % 2 === 1 ? 'md:order-1' : ''}`}>
                <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.08em] text-[#52525B] mb-4">{feature.title}</div>
                {feature.ui}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
