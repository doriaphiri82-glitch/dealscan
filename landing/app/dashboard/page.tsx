import { cookies } from 'next/headers'
import { createServerClient } from '@supabase/ssr'
import InvestorDashboard from './InvestorDashboard'

export default async function DashboardPage() {
  const cookieStore = cookies()
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { cookies: { getAll: () => cookieStore.getAll(), setAll: () => {} } },
  )
  const { data: { user } } = await supabase.auth.getUser()

  if (!user) {
    return (
      <main className="grid min-h-screen place-items-center bg-[#f7f9f7] px-4 py-16 text-[#15211b]">
        <div className="w-full max-w-lg rounded-[2rem] border border-[#dfe7e2] bg-white p-8 text-center shadow-[0_24px_80px_rgba(23,42,32,.08)]">
          <span className="rounded-full bg-[#e8f4ec] px-3 py-1.5 text-[10px] font-black uppercase tracking-[.14em] text-[#176b45]">Investor dashboard</span>
          <h1 className="mt-5 text-3xl font-black tracking-[-.04em]">Your deal desk starts here.</h1>
          <p className="mt-3 text-sm leading-6 text-[#69766f]">Sign in to see your saved opportunities, recent research and the strongest verified deals currently published by DealScan.</p>
          <div className="mt-7 flex justify-center gap-2">
            <a href="/auth" className="rounded-xl bg-[#153025] px-5 py-3 text-sm font-bold text-white hover:bg-[#176b45]">Sign in →</a>
            <a href="/deals" className="rounded-xl border border-[#dfe7e2] px-5 py-3 text-sm font-bold text-[#34423b]">Explore deals</a>
          </div>
        </div>
      </main>
    )
  }

  return <InvestorDashboard email={user.email ?? ''} />
}
