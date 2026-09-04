'use client'

import { useEffect, useRef } from 'react'

const scoreBreakdown = [
  { label: 'Value', val: 91, evidence: 'Nearby sales suggest substantial price support.' },
  { label: 'Market', val: 79, evidence: 'Recent activity provides a useful local benchmark.' },
  { label: 'Seller', val: 84, evidence: 'Long ownership and absentee ownership signals.' },
  { label: 'Access', val: 72, evidence: 'Legal access should be independently verified.' },
  { label: 'Risk', val: 88, evidence: 'Screening indicators are favorable, but verification remains required.' },
]

const comps = [
  ['Lot 8, Sierra Vista Estates', '0.3 mi', '2.1', '$8,500', '$4,048/ac', 'Jun 2026'],
  ['Lot 14, Sierra Vista Estates', '0.5 mi', '2.5', '$11,200', '$4,480/ac', 'May 2026'],
  ['Lot 3, Sierra Vista Estates', '0.7 mi', '1.8', '$7,800', '$4,333/ac', 'Apr 2026'],
  ['Lot 22, Sierra Vista Estates', '0.9 mi', '2.4', '$9,400', '$3,917/ac', 'Mar 2026'],
]

export default function SampleDeal() {
  const scoreRef = useRef<HTMLDivElement>(null)
  const tableRef = useRef<HTMLTableElement>(null)

  useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const observers: IntersectionObserver[] = []
    if (scoreRef.current) {
      const observer = new IntersectionObserver(([entry]) => {
        if (!entry.isIntersecting) return
        entry.target.querySelectorAll<HTMLElement>('.score-bar-fill').forEach((bar, i) => {
          setTimeout(() => { bar.style.width = `${bar.dataset.w ?? 0}%` }, reduced ? 0 : i * 100)
        })
        observer.unobserve(entry.target)
      }, { threshold: 0.25 })
      observer.observe(scoreRef.current); observers.push(observer)
    }
    if (tableRef.current) {
      const observer = new IntersectionObserver(([entry]) => {
        if (!entry.isIntersecting) return
        entry.target.querySelectorAll('tbody tr').forEach((row, i) => setTimeout(() => row.classList.add('row-visible'), reduced ? 0 : i * 90))
        observer.unobserve(entry.target)
      }, { threshold: 0.2 })
      observer.observe(tableRef.current); observers.push(observer)
    }
    return () => observers.forEach((observer) => observer.disconnect())
  }, [])

  return (
    <section className="relative overflow-hidden border-y border-[#e1e9e3] bg-white px-4 py-24 sm:px-6 md:px-8" id="deal-example">
      <div className="absolute inset-0 parcel-grid opacity-10 pointer-events-none" />
      <div className="relative mx-auto max-w-6xl">
        <div className="mb-10 grid gap-8 lg:grid-cols-[.72fr_1.28fr] lg:items-end" data-reveal>
          <div>
            <p className="mb-4 font-mono text-[10px] font-bold uppercase tracking-[.13em] text-[#176b45]">Example analysis</p>
            <h2 className="max-w-[560px] text-3xl font-black tracking-[-.035em] text-[#15211b] sm:text-4xl">A research report built for the first serious look.</h2>
          </div>
          <p className="max-w-[560px] text-[14px] leading-[1.8] text-[#64716a]">A fictional walkthrough of the evidence, economics, screening signals, and verification questions a DealScan report can organize. Nothing below represents a real property.</p>
        </div>

        <article className="overflow-hidden rounded-[28px] border border-[#dce6df] bg-white shadow-[0_28px_80px_rgba(25,49,38,.10)]" data-reveal>
          <header className="flex flex-col gap-4 border-b border-[#e7ede9] bg-[#fbfcfb] px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-7">
            <div><p className="text-base font-black text-[#203029]">Cochise County, AZ</p><p className="mt-1 font-mono text-[10px] text-[#8a958f]">APN 123-45-678A · 2.31 acres</p></div>
            <span className="w-fit rounded-full border border-[#eadcb9] bg-[#fff8e8] px-2.5 py-1 font-mono text-[9px] font-bold uppercase tracking-wide text-[#9a701b]">Demo · fictional data</span>
          </header>
          <div className="border-b border-[#eee5d2] bg-[#fffaf0] px-5 py-3 text-[11px] leading-[1.6] text-[#766746] sm:px-7">Illustrative example only. Property, pricing, comparable and risk data shown here are fictional and do not represent a real property.</div>

          <div className="p-5 sm:p-7">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {[['Asking price','$4,900'],['Est. market value','$9,700'],['Potential spread','$4,800'],['DealScore','87 / 100']].map(([label,value], i) => <div key={label} className="rounded-2xl border border-[#e4ebe6] bg-[#f8faf8] p-4"><p className="font-mono text-[9px] font-bold uppercase tracking-[.08em] text-[#8a958f]">{label}</p><p className={`mt-1.5 text-xl font-black tabular-nums ${i===2?'text-[#176b45]':'text-[#203029]'}`}>{value}</p></div>)}
            </div>
            <p className="mt-3 text-[11px] text-[#8a958f]">Estimated value and spread are preliminary screening estimates, not appraisals.</p>

            <div ref={scoreRef} className="mt-8 rounded-2xl border border-[#dfe8e2] bg-[#f5f8f6] p-5 sm:p-6">
              <div className="mb-5 flex items-end justify-between"><div><p className="font-mono text-[9px] font-bold uppercase tracking-[.1em] text-[#7c8881]">DealScore breakdown</p><p className="mt-1 text-sm font-semibold text-[#34433b]">Five dimensions for initial triage</p></div><div className="text-3xl font-black text-[#176b45] tabular-nums">87<span className="ml-1 text-xs font-medium text-[#8a958f]">/100</span></div></div>
              <div className="grid gap-x-10 md:grid-cols-2">{scoreBreakdown.map(item => <div key={item.label} className="border-b border-[#e2e9e4] py-3 last:border-0"><div className="grid grid-cols-[55px_1fr_28px] items-center gap-3"><span className="text-[10px] font-semibold text-[#64716a]">{item.label}</span><div className="h-1.5 overflow-hidden rounded-full bg-[#dfe8e2]"><div className="score-bar-fill h-full w-0 rounded-full bg-[#176b45] transition-[width] duration-700" data-w={item.val}/></div><span className="text-right font-mono text-[9px] text-[#68756e]">{item.val}</span></div><p className="mt-1.5 text-[11px] leading-[1.6] text-[#7a8780]">{item.evidence}</p></div>)}</div>
            </div>

            <div className="mt-8 grid gap-6 lg:grid-cols-2">
              <div className="rounded-2xl border border-[#e4ebe6] p-5"><div className="mb-3 flex items-center justify-between"><h3 className="font-mono text-[10px] font-bold uppercase tracking-[.1em] text-[#7c8881]">Screening signals</h3><span className="rounded-full bg-[#eef5f0] px-2 py-1 font-mono text-[8px] font-bold uppercase text-[#176b45]">Preliminary</span></div><ul>{['Below comparable pricing','Absentee ownership','Long ownership history (18 years)','Tax history requires review'].map((text,i)=><li key={text} className="flex gap-2.5 border-b border-[#edf1ee] py-2.5 text-xs text-[#59675f] last:border-0"><span className={i===3?'text-[#b17d18]':'text-[#176b45]'}>{i===3?'⚠':'✓'}</span>{text}</li>)}</ul></div>
              <div className="rounded-2xl border border-[#e4ebe6] p-5"><h3 className="mb-3 font-mono text-[10px] font-bold uppercase tracking-[.1em] text-[#7c8881]">Verification queue</h3><ul>{[['Legal and physical access','Review'],['Tax history','Needs review'],['Zoning compatibility','Unverified'],['Flood zone','Unverified'],['Utilities availability','Unverified']].map(([text,status])=><li key={text} className="flex items-center justify-between gap-3 border-b border-[#edf1ee] py-2.5 text-xs text-[#59675f] last:border-0"><span>{text}</span><span className="whitespace-nowrap rounded-full bg-[#fff4d9] px-2 py-1 font-mono text-[8px] font-bold uppercase text-[#9a701b]">{status}</span></li>)}</ul></div>
            </div>

            <div className="mt-8 rounded-2xl border border-[#dce7df] bg-[#f7faf8] p-5"><p className="mb-2 font-mono text-[9px] font-bold uppercase tracking-[.1em] text-[#176b45]">How DealScore works</p><p className="text-[12px] leading-[1.75] text-[#64716a]">DealScore combines Value, Market, Seller, Access, and Risk into a 0–100 screening score that helps prioritize parcels for deeper review. It is not investment advice, an appraisal, or a guarantee of profitability.</p></div>

            <div className="mt-8"><div className="mb-3 flex items-center justify-between"><h3 className="font-mono text-[10px] font-bold uppercase tracking-[.1em] text-[#7c8881]">Comparable sales</h3><span className="font-mono text-[8px] font-bold uppercase text-[#8a958f]">Example records</span></div><div className="overflow-x-auto rounded-2xl border border-[#e4ebe6]"><table ref={tableRef} className="w-full min-w-[620px] text-[11px]"><thead className="bg-[#f7f9f7]"><tr>{['Property','Distance','Acres','Sale price','$/acre','Date'].map((h,i)=><th key={h} className={`${i?'text-right':'text-left'} px-4 py-3 font-mono text-[8px] font-bold uppercase tracking-[.07em] text-[#8a958f]`}>{h}</th>)}</tr></thead><tbody>{comps.map(row=><tr key={row[0]} className="table-row-reveal border-t border-[#edf1ee] hover:bg-[#f8faf8]">{row.map((v,i)=><td key={i} className={`${i?'text-right':'text-left'} px-4 py-3 ${i===0?'font-semibold text-[#34433b]':'text-[#68756e]'}`}>{v}</td>)}</tr>)}</tbody></table></div></div>

            <div className="mt-8 grid gap-6 lg:grid-cols-[1.15fr_.85fr]">
              <div className="rounded-2xl border border-[#dce6df] bg-[#f4f7f5] p-4"><div className="mb-3 flex items-center justify-between"><h3 className="font-mono text-[10px] font-bold uppercase tracking-[.1em] text-[#7c8881]">Parcel vicinity</h3><span className="font-mono text-[8px] text-[#8a958f]">Stylized example</span></div><div className="relative h-52 overflow-hidden rounded-xl border border-[#dce6df] bg-[#edf3ef]" style={{backgroundImage:'linear-gradient(#d7e3db 1px,transparent 1px),linear-gradient(90deg,#d7e3db 1px,transparent 1px)',backgroundSize:'28px 28px'}}><div className="absolute left-[9%] top-[13%] h-[37%] w-[23%] border border-[#bdccc2] bg-white/45"/><div className="absolute left-[33%] top-[13%] h-[37%] w-[23%] border-2 border-[#176b45] bg-[#dceee3]/75"><span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 font-mono text-[9px] font-bold text-[#176b45]">SUBJECT</span></div><div className="absolute right-[9%] top-[13%] h-[37%] w-[23%] border border-[#bdccc2] bg-white/45"/><div className="absolute left-0 right-0 top-[61%] h-5 -translate-y-1/2 border-y border-[#c5d2ca] bg-white/60"/><div className="absolute left-[18%] top-[30%] h-2.5 w-2.5 rounded-full border-2 border-white bg-[#9a701b] shadow"/><div className="absolute left-[44%] top-[24%] h-2.5 w-2.5 rounded-full border-2 border-white bg-[#9a701b] shadow"/><div className="absolute right-[17%] top-[30%] h-2.5 w-2.5 rounded-full border-2 border-white bg-[#9a701b] shadow"/></div></div>
              <div className="rounded-2xl border border-[#e4ebe6] p-5"><p className="font-mono text-[9px] font-bold uppercase tracking-[.1em] text-[#7c8881]">Suggested next steps</p><ul className="mt-3 space-y-2">{['Verify legal access','Confirm tax status','Check flood zone maps','Verify zoning with county','Order title search'].map((step,i)=><li key={step} className="flex items-center gap-2 text-xs text-[#59675f]"><span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#e8f3ec] font-mono text-[8px] font-bold text-[#176b45]">{i+1}</span>{step}</li>)}</ul><p className="mt-4 text-[10px] leading-[1.6] text-[#8a958f]">No data in this example has been independently verified. Screening is not a substitute for due diligence.</p></div>
            </div>
          </div>
          <footer className="flex items-center justify-between border-t border-[#e7ede9] bg-[#fbfcfb] px-5 py-3 font-mono text-[9px] font-bold uppercase tracking-[.08em] text-[#8a958f] sm:px-7"><span>Demo dataset · illustrative</span><span>Example data</span></footer>
        </article>
      </div>
    </section>
  )
}
