export default function Footer() {
  return (
    <footer className="py-16 px-6 md:px-8 border-t border-[#e1e8e3] bg-white">
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6 mb-12">
          <div>
            <div className="text-[24px] font-bold tracking-[0.02em] text-[#15211b]">DEAL<span className="text-[#176b45]">SCAN</span></div>
            <p className="text-sm text-[#7a867f] mt-2">Land deal intelligence for investors.</p>
          </div>
          <a href="/deals" className="inline-flex w-fit items-center gap-2 rounded-xl bg-[#f0f5f1] px-4 py-2.5 text-[13px] font-semibold text-[#176b45] hover:bg-[#e5f2ea] transition-colors">Explore deals <span aria-hidden="true">→</span></a>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-10 md:gap-12 mb-12">
          <div>
            <h4 className="font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-[#8a958f] mb-3.5">Product</h4>
            {['Pricing', 'Example analysis', 'Capabilities', 'Workflow'].map((x, i) => <a key={x} href={['#pricing','#deal-example','#capabilities','#how-it-works'][i]} className="block text-[13px] text-[#64716a] hover:text-[#176b45] py-1 transition-colors">{x}</a>)}
          </div>
          <div>
            <h4 className="font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-[#8a958f] mb-3.5">Resources</h4>
            {['Deal analysis', 'FAQ', 'Early access'].map((x, i) => <a key={x} href={['#deal-example','#faq','#early-access'][i]} className="block text-[13px] text-[#64716a] hover:text-[#176b45] py-1 transition-colors">{x}</a>)}
          </div>
          <div>
            <h4 className="font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-[#8a958f] mb-3.5">Legal</h4>
            <a href="#disclaimer" className="block text-[13px] text-[#64716a] hover:text-[#176b45] py-1 transition-colors">Disclaimer</a>
          </div>
        </div>
        <div id="disclaimer" className="border-t border-[#e5ebe7] pt-7">
          <p className="text-xs text-[#8a958f] leading-[1.7] max-w-[700px]">DealScan provides informational analysis and screening tools only. Example reports and demo parcels on this site use fictional data for illustration. Data may be incomplete or inaccurate and should be independently verified with county and authoritative sources. DealScore and valuation estimates are not investment advice, appraisals, or guarantees of profitability. Screening is not a substitute for due diligence. Waitlist emails are used only to contact you about early access. Terms and privacy policy will be published at launch. © 2026 DealScan. All rights reserved.</p>
        </div>
      </div>
    </footer>
  )
}
