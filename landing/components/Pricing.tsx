'use client'

const tiers = [
  {
    name: 'Free',
    price: '$0',
    period: '/month',
    description: 'Try screening with limited reports',
    features: [
      'Limited deal previews',
      'Example deal reports',
      'Basic DealScore',
      'Educational resources',
    ],
    cta: 'Explore free',
    featured: false,
  },
  {
    name: 'Pro',
    price: '$79',
    period: '/month',
    description: 'More screening capacity, deeper analysis',
    features: [
      'Full deal reports',
      'Daily screened opportunities',
      'Comparable sales data',
      'DealScore breakdown',
      'Seller signals',
      'Risk flags',
    ],
    cta: 'Start with Pro',
    featured: true,
  },
  {
    name: 'Pro+',
    price: '$149',
    period: '/month',
    description: 'Higher limits and advanced workflow features',
    features: [
      'Everything in Pro',
      'Earlier deal alerts',
      'More markets',
      'Advanced filtering',
      'Priority support',
    ],
    cta: 'Join Pro+',
    featured: false,
  },
]

export default function Pricing() {
  return (
    <section className="py-24 px-6 md:px-8 bg-[#111113] border-y border-white/[0.06]" id="pricing">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-14" data-reveal>
          <p className="font-mono text-[11px] font-semibold tracking-[0.12em] uppercase text-brand-500 mb-4">Pricing</p>
          <h2 className="text-3xl md:text-4xl font-bold tracking-[-0.02em]">
            Simple pricing. Cancel anytime.
          </h2>
        </div>

        <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto" data-reveal data-reveal-delay="100">
          {tiers.map((tier) => (
            <div
              key={tier.name}
              className={`rounded-[10px] p-8 flex flex-col transition-all hover:-translate-y-0.5 ${
                tier.featured
                  ? 'border border-brand-500/30 bg-gradient-to-b from-brand-500/[0.03] to-[#161618]'
                  : 'border border-white/[0.06] bg-[#161618] hover:border-white/10'
              }`}
            >
              {tier.featured && (
                <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.06em] text-brand-500 bg-brand-500/10 px-2 py-1 rounded self-start mb-3">Recommended</span>
              )}
              <h3 className="text-sm font-bold mb-1">{tier.name}</h3>
              <p className="text-[13px] text-[#A1A1AA] mb-5">{tier.description}</p>
              <div className="text-[40px] font-bold tracking-[-0.02em] mb-6">
                {tier.price}<span className="text-sm font-normal text-[#52525B]">{tier.period}</span>
              </div>
              <ul className="flex-1 mb-7 space-y-1.5">
                {tier.features.map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-[13px] text-[#A1A1AA] py-1">
                    <svg className="w-3 h-3 mt-1 flex-shrink-0" viewBox="0 0 12 12" fill="none">
                      <path d="M2 6l3 3 5-5" stroke="#22C55E" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    {f}
                  </li>
                ))}
              </ul>
              <a
                href="#early-access"
                className={`w-full py-3 rounded-md text-sm font-medium text-center transition-all hover:-translate-y-px ${
                  tier.featured
                    ? 'bg-brand-600 hover:bg-brand-500 text-white'
                    : 'border border-white/10 text-white hover:bg-white/5 hover:border-white/20'
                }`}
              >
                {tier.cta}
              </a>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
