export default function Hero() {
  const requirements = [
    ['Source identity', 'A reviewed county source, live schema checks and a traceable parcel record.'],
    ['Vacancy evidence', 'Source-backed vacant land — not an empty field or an unoccupied building.'],
    ['Real economics', 'An actual asking price, documented costs and relevant recorded land sales.'],
    ['Separate verification', 'Evidence checked before publication, with a bounded verification expiry.'],
  ]
  return <section className="relative overflow-hidden bg-[#f7f9f7] px-4 pb-16 pt-32 sm:px-6 lg:pb-24 lg:pt-40">
    <div className="pointer-events-none absolute inset-0 parcel-grid opacity-20" aria-hidden="true" />
    <div className="relative mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2">
      <div>
        <p className="text-[11px] font-black uppercase tracking-[.16em] text-[#176b45]">Evidence-first land research</p>
        <h1 className="mt-5 text-5xl font-black tracking-[-.05em] text-[#15211b] sm:text-6xl">Find land worth <span className="text-[#176b45]">looking at.</span></h1>
        <p className="mt-6 max-w-xl text-base leading-8 text-[#64716a]">A conservative screening workflow for source-backed parcels. Understand the evidence and economics, then do your own due diligence before acting.</p>
        <div className="mt-8 flex flex-wrap gap-3"><a href="/deals" className="rounded-xl bg-[#153025] px-6 py-3.5 text-sm font-bold text-white hover:bg-[#176b45]">Explore verified opportunities →</a><a href="#how-it-works" className="rounded-xl border border-[#d5dfd8] bg-white px-6 py-3.5 text-sm font-bold text-[#34423b]">How it works</a></div>
        <p className="mt-5 text-xs leading-5 text-[#7c8981]">Missing evidence stays missing. Screening is not an investment guarantee.</p>
      </div>
      <div className="overflow-hidden rounded-[28px] border border-[#d9e4dc] bg-white shadow-[0_28px_80px_rgba(25,49,38,.10)]">
        <div className="border-b border-[#e7ede9] bg-[#f8faf9] px-6 py-5"><p className="text-[10px] font-black uppercase tracking-[.16em] text-[#176b45]">Publication requirements</p><h2 className="mt-2 text-xl font-black text-[#203029]">Evidence before opportunity.</h2></div>
        <ol className="divide-y divide-[#e7ede9] px-6">{requirements.map(([title,description],i) => <li key={title} className="flex gap-4 py-5"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[#edf5f0] text-xs font-black text-[#176b45]">{i+1}</span><div><h3 className="text-sm font-bold text-[#203029]">{title}</h3><p className="mt-1 text-xs leading-6 text-[#69776f]">{description}</p></div></li>)}</ol>
        <p className="border-t border-[#e7ede9] bg-[#f8faf9] px-6 py-4 text-xs leading-5 text-[#69776f]">This is the review process, not a property listing. The published feed may be empty.</p>
      </div>
    </div>
  </section>
}
