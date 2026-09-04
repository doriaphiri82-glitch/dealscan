import { cookies } from 'next/headers'
import { createServerClient } from '@supabase/ssr'
import SignOutButton from './SignOutButton'

export default async function MyDealScanPage() {
  const cookieStore = cookies()
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { cookies: { getAll: () => cookieStore.getAll(), setAll: () => {} } }
  )
  const { data: { user } } = await supabase.auth.getUser()

  if (!user) {
    return (
      <main className="min-h-screen bg-[#f7f9f7] px-4 py-20 text-center">
        <div className="mx-auto max-w-lg rounded-[28px] border border-[#dbe5df] bg-white p-8 shadow-sm">
          <p className="font-mono text-[10px] font-bold uppercase tracking-[.14em] text-[#176b45]">My DealScan</p>
          <h1 className="mt-3 text-3xl font-black tracking-[-.04em] text-[#15211b]">Sign in to access your workspace.</h1>
          <p className="mt-3 text-sm leading-6 text-[#69766f]">Your saved research and personal DealScan workspace will live here.</p>
          <a href="/auth" className="mt-7 inline-flex rounded-xl bg-[#153025] px-5 py-3 text-sm font-bold text-white hover:bg-[#176b45]">Sign in →</a>
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen bg-[#f7f9f7] px-4 py-8 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <header className="flex items-center justify-between rounded-2xl border border-[#dbe5df] bg-white px-4 py-3 shadow-sm sm:px-5">
          <a href="/" className="text-lg font-black tracking-[-.04em] text-[#153025]">Deal<span className="text-[#176b45]">Scan</span></a>
          <div className="flex items-center gap-3"><span className="hidden text-xs text-[#69766f] sm:block">{user.email}</span><SignOutButton /></div>
        </header>
        <section className="mt-8">
          <p className="font-mono text-[10px] font-bold uppercase tracking-[.14em] text-[#176b45]">My DealScan</p>
          <h1 className="mt-2 text-4xl font-black tracking-[-.04em] text-[#15211b]">Your deal workspace.</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-[#69766f]">You’re signed in. Saved deals, searches, notes, and verification workflows can build out here without changing the live deal-scoring pipeline.</p>
        </section>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {['Saved deals','Saved searches','Research notes'].map((title) => <div key={title} className="rounded-2xl border border-[#dbe5df] bg-white p-6 shadow-sm"><div className="font-mono text-[9px] font-bold uppercase tracking-[.1em] text-[#8a958f]">Workspace</div><h2 className="mt-2 text-lg font-black text-[#203029]">{title}</h2><p className="mt-2 text-xs leading-5 text-[#78847e]">Nothing saved yet. Explore deals to start building your workspace.</p><a href="/deals" className="mt-5 inline-flex text-xs font-bold text-[#176b45] hover:underline">Explore deals →</a></div>)}
        </div>
      </div>
    </main>
  )
}
