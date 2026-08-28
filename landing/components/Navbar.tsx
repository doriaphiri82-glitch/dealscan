'use client'

import { useEffect, useRef, useState } from 'react'

const links = [
  { href: '#deal-example', label: 'Example' },
  { href: '#capabilities', label: 'Capabilities' },
  { href: '#who-its-for', label: 'Who it\u2019s for' },
  { href: '#how-it-works', label: 'Workflow' },
  { href: '#pricing', label: 'Pricing' },
  { href: '#faq', label: 'FAQ' },
]

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  /* Close mobile menu on outside click and Escape */
  useEffect(() => {
    if (!open) return
    const onPointerDown = (e: MouseEvent | TouchEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setOpen(false)
    }
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('touchstart', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('touchstart', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  return (
    <header
      className={`fixed top-0 inset-x-0 z-50 transition-all duration-300 ${
        scrolled || open
          ? 'bg-[#0A0A0B]/90 backdrop-blur-md border-b border-white/[0.06]'
          : 'bg-transparent border-b border-transparent'
      }`}
    >
      <div
        className={`max-w-6xl mx-auto px-6 md:px-8 flex items-center justify-between transition-all duration-300 ${
          scrolled ? 'h-14' : 'h-16'
        }`}
      >
        <a href="#" className="text-[15px] font-bold tracking-[0.02em] text-white" aria-label="DealScan home">
          DEAL<span className="text-brand-500">SCAN</span>
        </a>

        <nav aria-label="Primary" className="hidden md:flex items-center gap-7">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-[13px] text-[#A1A1AA] hover:text-white transition-colors"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <a
            href="#early-access"
            className="group hidden sm:inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-brand-600 hover:bg-brand-500 text-white text-[13px] font-medium transition-all hover:-translate-y-px"
          >
            Start exploring
            <span aria-hidden="true" className="transition-transform duration-200 group-hover:translate-x-0.5">&rarr;</span>
          </a>
          <button
            type="button"
            onClick={() => setOpen(!open)}
            aria-expanded={open}
            aria-controls="mobile-menu"
            aria-label={open ? 'Close menu' : 'Open menu'}
            className="md:hidden inline-flex items-center justify-center w-9 h-9 rounded-md text-[#A1A1AA] hover:text-white hover:bg-white/5 transition-colors"
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
              {open ? (
                <path d="M4 4l10 10M14 4L4 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              ) : (
                <path d="M2 4.5h14M2 9h14M2 13.5h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              )}
            </svg>
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      <div id="mobile-menu" ref={menuRef} className="md:hidden" hidden={!open}>
        <nav aria-label="Mobile" className="px-6 pb-4 pt-1 flex flex-col bg-[#0A0A0B]/95 backdrop-blur-md">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              onClick={() => setOpen(false)}
              className="py-3 text-sm text-[#A1A1AA] hover:text-white border-b border-white/[0.04] last:border-0 transition-colors"
            >
              {link.label}
            </a>
          ))}
          <a
            href="#early-access"
            onClick={() => setOpen(false)}
            className="mt-3 inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-md bg-brand-600 hover:bg-brand-500 text-white text-[13px] font-medium"
          >
            Start exploring
            <span aria-hidden="true">&rarr;</span>
          </a>
        </nav>
      </div>
    </header>
  )
}

