'use client'
import { formatCurrency } from '@/lib/format'
import { useEffect, useState } from 'react'
import { fetchTopDeals, currentDeal, type Deal } from '@/lib/deals'
import { parcelHref, parcelKey } from '@/lib/parcels'
const money=(value?:number|null)=>formatCurrency(value,'Not published')

export default function LiveOpportunities() {
  const [deals,setDeals] = useState<Deal[]>([])
  const [status,setStatus] = useState<'loading'|'ready'|'error'>('loading')
  useEffect(() => {
    let active = true
    const load = async () => {
      try { const data=await fetchTopDeals(3); if (active) { setDeals(data.deals); setStatus('ready') } }
      catch { if (active) { setDeals([]); setStatus('error') } }
    }
    void load(); const timer=window.setInterval(() => void load(),60000)
    return () => { active=false; window.clearInterval(timer) }
  },[])
  useEffect(()=>{if(!deals.length)return;const expiry=Math.min(...deals.map(d=>Date.parse(d.verification_expires_at)));const timer=window.setTimeout(()=>setDeals(current=>current.filter(currentDeal)),Math.max(0,expiry-Date.now()+1));return()=>window.clearTimeout(timer)},[deals])
  const visible=deals.filter(currentDeal)
  return <section className="border-y border-[#e1e9e3] bg-white px-6 py-24 md:px-8" id="verified-opportunities">
    <div className="mx-auto max-w-6xl"><p className="text-[11px] font-bold uppercase tracking-[.12em] text-[#176b45]">Published feed</p><h2 className="mt-4 text-3xl font-black tracking-[-.035em] text-[#15211b] sm:text-4xl">Only evidence-backed opportunities.</h2>
      <p className="mt-4 max-w-2xl text-sm leading-7 text-[#64716a]">A small view of the current verified feed. County records without sufficient vacancy or financial evidence are not promoted into listings.</p>
      <div className="mt-8 rounded-[28px] border border-[#dce6df] bg-[#f8faf9] p-7" aria-live="polite" aria-busy={status==='loading'}>
        {status==='loading' ? <p className="text-sm text-[#64716a]">Checking the verified feed…</p> : status==='error' ? <p role="status" className="text-sm leading-7 text-[#64716a]">The verified feed is temporarily unavailable. No sample records or cached opportunities are being substituted.</p> : !visible.length ? <p className="text-sm leading-7 text-[#64716a]">No verified opportunities are currently available. An empty feed is preferable to unsupported prices, sales or profit estimates.</p> : <div className="grid gap-4 md:grid-cols-3">{visible.map(deal=><a key={parcelKey(deal)} href={parcelHref(deal)} className="rounded-2xl border border-[#dfe7e2] bg-white p-5 hover:border-[#176b45]"><p className="text-xs font-bold uppercase text-[#176b45]">{deal.county_id.replaceAll('_',' ')}</p><h3 className="mt-3 font-bold text-[#203029]">{deal.address || `Parcel ${deal.apn}`}</h3><p className="mt-2 text-xs text-[#64716a]">APN {deal.apn}</p><p className="mt-4 text-sm font-semibold text-[#203029]">Asking {money(deal.asking_price)}</p><span className="mt-4 block text-xs font-bold text-[#176b45]">Review the evidence →</span></a>)}</div>}
      </div><a href="/deals" className="mt-6 inline-flex rounded-xl bg-[#153025] px-6 py-3 text-sm font-bold text-white hover:bg-[#176b45]">Open Explorer →</a>
    </div>
  </section>
}
