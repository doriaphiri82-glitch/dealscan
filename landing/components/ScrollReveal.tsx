'use client'

import { useEffect } from 'react'

/**
 * Global scroll-reveal controller.
 * Observes every [data-reveal] element and adds `.revealed` when it enters
 * the viewport. Optional `data-reveal-delay` (ms) staggers children.
 */
export default function ScrollReveal() {
  useEffect(() => {
    document.documentElement.classList.add('js')
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const els = Array.from(document.querySelectorAll<HTMLElement>('[data-reveal]'))

    if (prefersReduced) {
      els.forEach((el) => el.classList.add('revealed'))
      return
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const el = entry.target as HTMLElement
            const delay = el.dataset.revealDelay
            if (delay) el.style.setProperty('--reveal-delay', `${delay}ms`)
            el.classList.add('revealed')
            observer.unobserve(el)
          }
        })
      },
      { threshold: 0.15, rootMargin: '0px 0px -40px 0px' }
    )

    els.forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [])

  return null
}
