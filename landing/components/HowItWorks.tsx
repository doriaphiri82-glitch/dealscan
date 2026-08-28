'use client'

import { useEffect, useRef } from 'react'

export default function HowItWorks() {
  const lineRef = useRef<HTMLDivElement>(null)

  const steps = [
    { num: '01', label: 'Discover', desc: 'Screen parcels across configured markets' },
    { num: '02', label: 'Screen', desc: 'Score each parcel on key metrics' },
    { num: '03', label: 'Compare', desc: 'Benchmark against nearby sales' },
    { num: '04', label: 'Verify', desc: 'Flag risks for due diligence' },
    { num: '05', label: 'Decide', desc: 'Know what deserves a closer look' },
  ]

  useEffect(() => {
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          if (prefersReduced) {
            lineRef.current?.classList.add('drawn')
          } else {
            setTimeout(() => lineRef.current?.classList.add('drawn'), 300)
          }
          observer.unobserve(entry.target)
        }
      })
    }, { threshold: 0.3 })
    if (lineRef.current?.parentElement) observer.observe(lineRef.current.parentElement)
    return () => observer.disconnect()
  }, [])

  return (
    <section className="py-24 px-6 md:px-8" id="how-it-works">
      <div className="max-w-6xl mx-auto">
        <div className="mb-10" data-reveal>
          <p className="font-mono text-[11px] font-semibold tracking-[0.12em] uppercase text-brand-500 mb-4">Workflow</p>
          <h2 className="text-3xl md:text-4xl font-bold tracking-[-0.02em] max-w-[560px]">
            From property search to informed decision.
          </h2>
        </div>

        <div className="relative flex flex-col md:flex-row items-center md:items-start justify-center gap-2 md:gap-0 py-8">
          <div ref={lineRef} className="workflow-line hidden md:block" aria-hidden="true" />
          {steps.map((step, i) => (
            <div
              key={step.num}
              className="flex flex-col md:flex-row items-center"
              data-reveal
              data-reveal-delay={i * 120}
            >
              <div className="flex flex-col items-center px-7 py-5 group cursor-default">
                <span className="font-mono text-[11px] font-semibold text-[#52525B] group-hover:text-brand-500 transition-colors mb-2">{step.num}</span>
                <span className="text-[13px] font-semibold uppercase tracking-[0.06em] text-[#A1A1AA] group-hover:text-white transition-colors">{step.label}</span>
                <span className="text-xs text-[#52525B] mt-1.5 text-center max-w-[140px]">{step.desc}</span>
              </div>
              {i < steps.length - 1 && (
                <div className="hidden md:block w-10 h-px bg-white/10 mt-9 relative" aria-hidden="true">
                  <div className="absolute right-[-2px] top-[-2px] w-[5px] h-[5px] border-r border-t border-[#52525B] rotate-45" />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
