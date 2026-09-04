'use client'

import { useEffect, useRef } from 'react'

export default function HowItWorks() {
  const lineRef = useRef<HTMLDivElement>(null)
  const steps = [
    { num: '01', label: 'Discover', desc: 'Screen parcels across configured markets' },
    { num: '02', label: 'Understand', desc: 'Score the economics and seller signals' },
    { num: '03', label: 'Compare', desc: 'Benchmark against nearby sales' },
    { num: '04', label: 'Verify', desc: 'Flag risks for due diligence' },
    { num: '05', label: 'Act', desc: 'Know what deserves a closer look' },
  ]

  useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) {
        if (reduced) lineRef.current?.classList.add('drawn')
        else setTimeout(() => lineRef.current?.classList.add('drawn'), 300)
        observer.disconnect()
      }
    }, { threshold: 0.3 })
    if (lineRef.current?.parentElement) observer.observe(lineRef.current.parentElement)
    return () => observer.disconnect()
  }, [])

  return (
    <section className="py-24 px-6 md:px-8" id="how-it-works">
      <div className="max-w-6xl mx-auto">
        <div className="mb-10" data-reveal>
          <p className="font-mono text-[11px] font-semibold tracking-[0.12em] uppercase text-brand-500 mb-4">Workflow</p>
          <h2 className="text-3xl md:text-4xl font-bold tracking-[-0.02em] max-w-[560px] text-[#15211b]">From discovery to a better-informed decision.</h2>
        </div>
        <div className="relative grid grid-cols-1 md:grid-cols-5 gap-3 md:gap-0 py-2" ref={lineRef?.current ? undefined : undefined}>
          <div ref={lineRef} className="workflow-line hidden md:block" aria-hidden="true" />
          {steps.map((step, i) => (
            <div key={step.num} className="relative z-10" data-reveal data-reveal-delay={i * 120}>
              <div className="h-full rounded-2xl border border-[#e2e9e4] bg-white p-5 md:mx-1.5 transition-all duration-300 hover:-translate-y-1 hover:border-[#c8dbcf] hover:shadow-[0_16px_34px_rgba(31,61,47,0.08)]">
                <div className="flex items-center justify-between mb-7">
                  <span className="font-mono text-[11px] font-semibold text-[#176b45]">{step.num}</span>
                  <span className="w-2 h-2 rounded-full bg-[#d7e8dc] ring-4 ring-[#f3f8f4]" aria-hidden="true" />
                </div>
                <h3 className="text-[14px] font-bold uppercase tracking-[0.05em] text-[#26352d]">{step.label}</h3>
                <p className="text-xs text-[#7a867f] mt-2 leading-[1.6]">{step.desc}</p>
              </div>
            </div>
          ))}
        </div>
        <p className="text-center text-[12px] text-[#8a958f] mt-8" data-reveal>DISCOVER → UNDERSTAND → VERIFY → ACT</p>
      </div>
    </section>
  )
}
