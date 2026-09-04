'use client'

import { useState } from 'react'

const faqs = [
  { q: 'Is DealScan an investment advisor?', a: 'No. DealScan provides data and screening tools. Users are responsible for conducting their own due diligence and making their own investment decisions.' },
  { q: 'Are the property values guaranteed?', a: 'No. Valuations are estimates based on available data and should be independently verified before making any purchase decision.' },
  { q: 'Does DealScan guarantee profitable deals?', a: 'No. DealScan identifies parcels that may be worth investigating based on available data. Profitability depends on many factors including acquisition cost, holding costs, market conditions, and your ability to find a buyer.' },
  { q: 'Which markets are supported?', a: 'Currently: Cochise County AZ, Mohave County AZ, and El Paso County TX. Huerfano County CO and Socorro County NM are in development. Additional markets are planned based on data availability.' },
  { q: 'How often is data updated?', a: 'County records are checked on a regular schedule. Comparable sales data is refreshed as new transactions are recorded. Update frequency varies by county based on data source availability.' },
  { q: 'Can I cancel?', a: 'Yes. You can cancel your subscription at any time. No long-term contracts or commitments.' },
]

export default function FAQ() {
  const [open, setOpen] = useState<number | null>(null)
  return (
    <section className="py-24 px-6 md:px-8" id="faq">
      <div className="max-w-[720px] mx-auto">
        <div className="mb-10" data-reveal>
          <p className="font-mono text-[11px] font-semibold tracking-[0.12em] uppercase text-brand-500 mb-4">FAQ</p>
          <h2 className="text-3xl md:text-4xl font-bold tracking-[-0.02em] text-[#15211b]">Common questions</h2>
        </div>
        <div className="rounded-2xl border border-[#dfe7e2] bg-white px-5 md:px-7 shadow-[0_12px_30px_rgba(31,61,47,0.05)]" data-reveal data-reveal-delay="100">
          {faqs.map((faq, i) => {
            const panelId = `faq-panel-${i}`
            const buttonId = `faq-button-${i}`
            const isOpen = open === i
            return (
              <div key={i} className="border-b border-[#e5ebe7] last:border-0">
                <button id={buttonId} onClick={() => setOpen(isOpen ? null : i)} className="w-full py-5 text-left flex items-center justify-between gap-4 text-[15px] font-semibold text-[#26352d] hover:text-[#176b45] transition-colors" aria-expanded={isOpen} aria-controls={panelId}>
                  <span>{faq.q}</span>
                  <span className={`flex h-7 w-7 items-center justify-center rounded-full border border-[#dfe7e2] text-[#7a867f] transition-all duration-300 ${isOpen ? 'rotate-180 bg-[#e5f2ea] text-[#176b45]' : ''}`} aria-hidden="true">&#9660;</span>
                </button>
                <div id={panelId} role="region" aria-labelledby={buttonId} className={`overflow-hidden transition-all duration-300 ${isOpen ? 'max-h-[320px] pb-5' : 'max-h-0'}`}>
                  <p className="text-sm text-[#64716a] leading-[1.75] pr-10">{faq.a}</p>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
