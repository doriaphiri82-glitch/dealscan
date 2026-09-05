'use client'

import Link from 'next/link'

export default function InvestorDashboard({ email }: { email: string }) {
  return (
    <main className="min-h-screen bg-[#f7f9f7] px-4 py-10 text-[#15211b] sm:px-8">
      <div className="mx-auto max-w-6xl">
        <header className="flex flex-col gap-4 border-b border-[#dfe7e2] pb-7 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <span className="text-[10px] font-black uppercase tracking-[.16em] text-[#176b45]">DealScan · Investor workspace</span>
            <h1 className="mt-2 text-3xl font-black tracking-[-.04em] sm:text-4xl">Your deal desk</h1>
            <p className="mt-2 text-sm text-[#69766f]">Signed in as {email || 'investor'}</p>
          </div>
          <Link href="/deals" className="rounded-xl bg-[#153025] px-5 py-3 text-center text-sm font-bold text-white transition hover:bg-[#176b45]">Explore deals →</Link>
        </header>

        <section className="mt-8 grid gap-4 md:grid-cols-3">
          {[
            ['Saved opportunities', '0', 'Build your watchlist from verified deals.'],
            ['Recent research', '0', 'Your research workspace will appear here.'],
            ['Verified deals', 'Live', 'Only published opportunities should surface here.'],
          ].map(([label, value, description]) => (
            <article key={label} className="rounded-3xl border border-[#dfe7e2] bg-white p-6 shadow-[0_18px_60px_rgba(23,42,32,.06)]">
              <p className="text-xs font-bold text-[#69766f]">{label}</p>
              <p className="mt-3 text-3xl font-black tracking-[-.04em]">{value}</p>
              <p className="mt-2 text-sm leading-6 text-[#69766f]">{description}</p>
            </article>
          ))}
        </section>

        <section className="mt-6 rounded-3xl border border-[#dfe7e2] bg-white p-6 shadow-[0_18px_60px_rgba(23,42,32,.06)] sm:p-8">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs font-black uppercase tracking-[.14em] text-[#176b45]">Portfolio intelligence</p>
              <h2 className="mt-2 text-2xl font-black tracking-[-.03em]">Start with verified opportunities</h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[#69766f]">Browse DealScan's published opportunities, inspect property evidence, compare deals, and save the ones worth deeper research.</p>
            </div>
            <Link href="/deals" className="rounded-xl border border-[#dfe7e2] px-5 py-3 text-sm font-bold text-[#34423b] hover:border-[#176b45] hover:text-[#176b45]">Browse marketplace</Link>
          </div>
        </section>
      </div>
    </main>
  )
}
