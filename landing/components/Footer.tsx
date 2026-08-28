export default function Footer() {
  return (
    <footer className="py-16 px-6 md:px-8 border-t border-white/[0.06]">
      <div className="max-w-6xl mx-auto">
        <div className="text-[24px] font-bold tracking-[0.02em] mb-2">
          DEAL<span className="text-brand-500">SCAN</span>
        </div>
        <p className="text-sm text-[#A1A1AA] mb-12">Land deal intelligence for investors.</p>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-10 md:gap-12 mb-12">
          <div>
            <h4 className="font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-[#52525B] mb-3.5">Product</h4>
            <a href="#pricing" className="block text-[13px] text-[#A1A1AA] hover:text-white py-1 transition-colors">Pricing</a>
            <a href="#deal-example" className="block text-[13px] text-[#A1A1AA] hover:text-white py-1 transition-colors">Example analysis</a>
            <a href="#capabilities" className="block text-[13px] text-[#A1A1AA] hover:text-white py-1 transition-colors">Capabilities</a>
            <a href="#how-it-works" className="block text-[13px] text-[#A1A1AA] hover:text-white py-1 transition-colors">Workflow</a>
          </div>
          <div>
            <h4 className="font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-[#52525B] mb-3.5">Resources</h4>
            <a href="#deal-example" className="block text-[13px] text-[#A1A1AA] hover:text-white py-1 transition-colors">Deal analysis</a>
            <a href="#faq" className="block text-[13px] text-[#A1A1AA] hover:text-white py-1 transition-colors">FAQ</a>
            <a href="#early-access" className="block text-[13px] text-[#A1A1AA] hover:text-white py-1 transition-colors">Early access</a>
          </div>
          <div>
            <h4 className="font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-[#52525B] mb-3.5">Legal</h4>
            <a href="#disclaimer" className="block text-[13px] text-[#A1A1AA] hover:text-white py-1 transition-colors">Disclaimer</a>
          </div>
        </div>

        <div id="disclaimer" className="border-t border-white/[0.06] pt-7">
          <p className="text-xs text-[#52525B] leading-[1.7] max-w-[640px]">
            DealScan provides informational analysis and screening tools only. Example reports and demo parcels on this site use fictional data for illustration. Data may be incomplete or inaccurate and should be independently verified with county and authoritative sources. DealScore and valuation estimates are not investment advice, appraisals, or guarantees of profitability. Screening is not a substitute for due diligence. Waitlist emails are used only to contact you about early access. Terms and privacy policy will be published at launch. &copy; 2026 DealScan. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  )
}
