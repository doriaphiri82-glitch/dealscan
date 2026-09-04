'use client'

import { useEffect, useRef, useState } from 'react'

const links = [
  { href: '/deals', label: 'Explore deals' },
  { href: '#deal-example', label: 'Example' },
  { href: '#capabilities', label: 'Capabilities' },
  { href: '#who-its-for', label: 'Who it’s for' },
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
    <header className={`fixed inset-x-0 top-0 z-50 transition-all duration-300 ${scrolled || open ? 'border-b border-[#dfe8e2] bg-white/90 shadow-[0_8px_30px_rgba(25,49,38,.06)] backdrop-blur-xl' : 'border-b border-transparent bg-white/55 backdrop-blur-sm'}`}>
      <div className={`mx-auto flex max-w-7xl items-center justify-between px-4 transition-all duration-300 sm:px-6 lg:px-8 ${scrolled ? 'h-14' : 'h-16'}`}>
        <a href="#" className="text-[15px] font-black tracking-[0.02em] text-[#15211b]" aria-label="DealScan home">DEAL<span className="text-[#176b45]">SCAN</span></a>
        <nav aria-label="Primary" className="hidden items-center gap-5 lg:flex">
          {links.map((link) => <a key={link.href} href={link.href} className="rounded-full px-2 py-1.5 text-[12px] font-semibold text-[#64716a] transition-colors hover:text-[#176b45]">{link.label}</a>)}
        </nav>
        <div className="flex items-center gap-2">
          <a href="/deals" className="group hidden items-center gap-1.5 rounded-xl bg-[#153025] px-4 py-2.5 text-[12px] font-bold text-white shadow-[0_8px_20px_rgba(21,48,37,.14)] transition-all hover:-translate-y-0.5 hover:bg-[#176b45] sm:inline-flex">Explore deals <span aria-hidden="true" className="transition-transform duration-200 group-hover:translate-x-0.5">&rarr;</span></a>
          <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} aria-controls="mobile-menu" aria-label={open ? 'Close menu' : 'Open menu'} className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[#d7e2db] bg-white text-[#34433b] shadow-sm transition-colors hover:border-[#b9cfc1] hover:text-[#176b45] lg:hidden">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">{open ? <path d="M4 4l10 10M14 4L4 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /> : <path d="M2 4.5h14M2 9h14M2 13.5h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />}</svg>
          </button>
        </div>
      </div>
      <div id="mobile-menu" ref={menuRef} className="border-t border-[#e6ece8] bg-white/95 shadow-[0_18px_45px_rgba(25,49,38,.08)] backdrop-blur-xl lg:hidden" hidden={!open}>
        <nav aria-label="Mobile" className="mx-auto flex max-w-7xl flex-col px-4 pb-5 pt-2 sm:px-6">
          {links.map((link) => <a key={link.href} href={link.href} onClick={() => setOpen(false)} className="border-b border-[#edf1ee] py-3.5 text-sm font-semibold text-[#59675f] transition-colors hover:text-[#176b45] last:border-0">{link.label}</a>)}
          <a href="/deals" onClick={() => setOpen(false)} className="mt-3 inline-flex items-center justify-center gap-1.5 rounded-xl bg-[#153025] px-4 py-3 text-[13px] font-bold text-white transition-colors hover:bg-[#176b45]">Open deal explorer <span aria-hidden="true">&rarr;</span></a>
        </nav>
      </div>
    </header>
  )
}
