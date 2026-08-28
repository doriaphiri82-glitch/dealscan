'use client'

import { useState } from 'react'

const faqs = [
  {
    q: 'Is DealScan an investment advisor?',
    a: 'No. DealScan provides data and screening tools. Users are responsible for conducting their own due diligence and making their own investment decisions.',
  },
  {
    q: 'Are the property values guaranteed?',
    a: 'No. Valuations are estimates based on available data and should be independently verified before making any purchase decision.',
  },
  {
    q: 'Does DealScan guarantee profitable deals?',
    a: 'No. DealScan identifies parcels that may be worth investigating based on available data. Profitability depends on many factors including acquisition cost, holding costs, market conditions, and your ability to find a buyer.',
  },
  {
    q: 'Which markets are supported?',
    a: 'Currently: Cochise County AZ, Mohave County AZ, and El Paso County TX. Huerfano County CO and Socorro County NM are in development. Additional markets are planned based on data availability.',
  },
  {
    q: 'How often is data updated?',
    a: 'County records are checked on a regular schedule. Comparable sales data is refreshed as new transactions are recorded. Update frequency varies by county based on data source availability.',
  },
  {
    q: 'Can I cancel?',
    a: 'Yes. You can cancel your subscription at any time. No long-term contracts or commitments.',
  },
]

export default function FAQ() {
  const [open, setOpen] = useState<number | null>(null)

  return (
    <section className="py-24 px-6 md:px-8" id="faq">
      <div className="max-w-[680px] mx-auto">
        <div className="mb-10" data-reveal>
          <p className="font-mono text-[11px] font-semibold tracking-[0.12em] uppercase text-brand-500 mb-4">FAQ</p>
          <h2 className="text-3xl md:text-4xl font-bold tracking-[-0.02em]">Common questions</h2>
        </div>

        <div data-reveal data-reveal-delay="100">
          {faqs.map((faq, i) => {
            const panelId = `faq-panel-${i}`
            const buttonId = `faq-button-${i}`
            return (
              <div key={i} className="border-b border-white/[0.06]">
                <button
                  id={buttonId}
                  onClick={() => setOpen(open === i ? null : i)}
                  className="w-full py-[18px] text-left flex items-center justify-between gap-4 text-[15px] font-medium text-white hover:text-brand-500 transition-colors"
                  aria-expanded={open === i}
                  aria-controls={panelId}
                >
                  <span>{faq.q}</span>
                  <span className={`text-[10px] text-[#52525B] transition-transform duration-300 ${open === i ? 'rotate-180' : ''}`} aria-hidden="true">&#9660;</span>
                </button>
                <div
                  id={panelId}
                  role="region"
                  aria-labelledby={buttonId}
                  className={`overflow-hidden transition-all duration-300 ${open === i ? 'max-h-[320px] pb-[18px]' : 'max-h-0'}`}
                >
                  <p className="text-sm text-[#A1A1AA] leading-[1.7]">{faq.a}</p>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
