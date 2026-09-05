'use client'

const tiers = [
  { name:'Explorer',price:'Free',period:'',description:'Current verified opportunities when available',features:['Public verified feed','Source-backed evidence','County-scoped parcel research','No subscription checkout'],cta:'Open Explorer',href:'/deals',featured:false },
  { name:'Pro · planned',price:'Not live',period:'',description:'Expanded research tools under consideration',features:['No paid plan is currently activated','No daily deal volume is promised','Features and pricing are not finalized'],cta:'Get product updates',href:'#early-access',featured:true },
  { name:'Pro+ · planned',price:'Not live',period:'',description:'Future workflow capabilities',features:['No premium checkout is available','No priority alerts are currently sent','Join updates to hear about changes'],cta:'Get product updates',href:'#early-access',featured:false },
]

export default function Pricing() {
  return (
    <section className="py-24 px-6 md:px-8 bg-[#f0f4f1] border-y border-[#e1e8e3]" id="pricing">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-14" data-reveal>
          <p className="font-mono text-[11px] font-semibold tracking-[0.12em] uppercase text-brand-500 mb-4">Pricing</p>
          <h2 className="text-3xl md:text-4xl font-bold tracking-[-0.02em] text-[#15211b]">Explore now. Paid plans are not live.</h2>
        </div>
        <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto" data-reveal data-reveal-delay="100">
          {tiers.map((tier) => (
            <div key={tier.name} className={`relative rounded-2xl p-7 md:p-8 flex flex-col bg-white transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_20px_40px_rgba(31,61,47,0.09)] ${tier.featured ? 'border-2 border-[#176b45] shadow-[0_12px_32px_rgba(23,107,69,0.10)]' : 'border border-[#dfe7e2]'}`}>
              {tier.featured && <span className="absolute -top-3 left-6 font-mono text-[10px] font-semibold uppercase tracking-[0.06em] text-white bg-[#176b45] px-3 py-1.5 rounded-full">Planned</span>}
              <h3 className="text-sm font-bold text-[#26352d] mb-1">{tier.name}</h3>
              <p className="text-[13px] text-[#7a867f] mb-5">{tier.description}</p>
              <div className="text-[40px] font-bold tracking-[-0.02em] text-[#15211b] mb-6">{tier.price}<span className="text-sm font-normal text-[#8a958f]">{tier.period}</span></div>
              <ul className="flex-1 mb-7 space-y-1.5">
                {tier.features.map((f) => <li key={f} className="flex items-start gap-2.5 text-[13px] text-[#64716a] py-1"><svg className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" viewBox="0 0 14 14" fill="none"><path d="M2.5 7l2.8 2.8L11.5 4" stroke="#176b45" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>{f}</li>)}
              </ul>
              <a href={tier.href} className={`w-full py-3 rounded-xl text-sm font-medium text-center transition-all hover:-translate-y-px ${tier.featured ? 'bg-[#176b45] hover:bg-[#0f5637] text-white shadow-[0_8px_20px_rgba(23,107,69,0.16)]' : 'border border-[#cfdad3] text-[#26352d] hover:bg-[#f2f6f3] hover:border-[#aebfb4]'}`}>{tier.cta}</a>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
