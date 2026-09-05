import { formatCurrency } from '../lib/format'
import { publishedDeal } from './support/public-deal'
import { expect, it, vi } from 'vitest'
import { fetchTopDeals, fetchDealByApn, ParcelAmbiguous } from '../lib/deals'
import { parcelKey, parseParcelKey, parcelHref, compareHref, comparisonRefs, readParcelList, writeParcelList } from '../lib/parcels'

it('keeps same-APN parcels in different counties distinct, including literal punctuation', () => {
  const first={apn:'50%, A/B?C#D',county_id:'first_county'}
  const second={...first,county_id:'second_county'}
  expect(parcelKey(first)).not.toBe(parcelKey(second))
  expect(parseParcelKey(parcelKey(first))).toEqual(first)
  expect(comparisonRefs(compareHref([parcelKey(first),parcelKey(second)]).split('?')[1])).toEqual([first,second])
  expect(parcelHref(first)).toContain('county_id=first_county')
  expect(parseParcelKey('old-apn')).toEqual({apn:'old-apn'})
  expect(parseParcelKey('["literal","apn"]')).toEqual({apn:'["literal","apn"]'})
})

it('reads individual selections rather than searching only the first feed page', async () => {
  const fetch=vi.fn().mockResolvedValue(Response.json({}, {status:404}));vi.stubGlobal('fetch',fetch)
  expect(await fetchDealByApn('50%','second_county')).toBeNull()
  expect(fetch.mock.calls[0][0]).toBe('/api/deals/50%25?county_id=second_county')
})

it('does not equate unavailable or ambiguous data with a successful empty feed', async () => {
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(Response.json({}, {status:503})))
  await expect(fetchTopDeals()).rejects.toThrow(/unavailable/)
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(Response.json({}, {status:409})))
  await expect(fetchDealByApn('same')).rejects.toBeInstanceOf(ParcelAmbiguous)
})

it('rejects stale or non-Supabase response bodies instead of treating them as current deals', async () => {
  const body={deals:[{apn:'fixture',county_id:'fixture',verification_status:'verified',verified_at:'2020-01-01',verification_expires_at:'2020-01-02'}],meta:{storage_source:'supabase'}}
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(Response.json(body)))
  await expect(fetchTopDeals()).rejects.toThrow()
})

it('makes blocked storage observable and never reports a truncated write as saved', () => {
  vi.stubGlobal('localStorage',{getItem:()=>{throw new Error('blocked')},setItem:vi.fn()})
  expect(()=>readParcelList('saved')).toThrow()
  expect(()=>writeParcelList('saved',Array.from({length:501},(_,i)=>`parcel-${i}`))).toThrow(/limit/)
})

it('preserves clearly identified browser-local parcel references', () => {
  const stored=new Map<string,string>()
  vi.stubGlobal('localStorage',{getItem:(key:string)=>stored.get(key)??null,setItem:(key:string,value:string)=>stored.set(key,value)})
  const keys=[parcelKey({apn:'1',county_id:'a'}),parcelKey({apn:'1',county_id:'b'})]
  writeParcelList('saved',keys)
  expect(readParcelList('saved')).toEqual(keys)
})


it('accepts a complete verified response without inventing optional property information',async()=>{
  const deal=publishedDeal({address:null,zoning:null})
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(Response.json({count:1,deals:[deal],meta:{status:'ok',storage_source:'supabase'}})))
  expect((await fetchTopDeals()).deals).toEqual([deal])
})

it.each([{asking_price:null},{asking_price:0},{estimated_costs:-1},{estimated_profit_high:999999},{source_record_id:null},{latitude:null}])('rejects a claimed verified opportunity with incomplete or contradictory facts: %j',async patch=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(Response.json({count:1,deals:[publishedDeal(patch)],meta:{status:'ok',storage_source:'supabase'}})))
  await expect(fetchTopDeals()).rejects.toThrow(/unavailable/)
})

it('does not accept another parcel from a successful detail response',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(Response.json({deal:publishedDeal({apn:'different'})})))
  await expect(fetchDealByApn('requested','fixture_county')).rejects.toThrow()
})

it('rejects malformed counts and repeated parcels rather than inflating available inventory',async()=>{
  const deal=publishedDeal()
  for(const body of [{count:999,deals:[deal]},{count:2,deals:[deal,deal]}]){
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(Response.json({...body,meta:{status:'ok',storage_source:'supabase'}})))
    await expect(fetchTopDeals()).rejects.toThrow()
  }
})


it('never treats corrupt versioned keys as bare parcel identifiers',()=>{
  for(const key of ['v2:not-json','v2:[]','v2:["invalid county","apn"]','v2:["a",null]'])expect(parseParcelKey(key)).toBeNull()
})

it('comparison references are distinct rather than multiple copies of one parcel',()=>{
  const a=parcelKey({apn:'same',county_id:'a'}),b=parcelKey({apn:'same',county_id:'b'})
  expect(comparisonRefs(new URLSearchParams([['parcel',a],['parcel',a],['parcel',b]]).toString())).toEqual([{apn:'same',county_id:'a'},{apn:'same',county_id:'b'}])
})

it('corrupt or oversized browser storage cannot be silently truncated and overwritten',()=>{
  const setItem=vi.fn()
  vi.stubGlobal('localStorage',{getItem:()=>JSON.stringify(['v2:bad']),setItem})
  expect(()=>readParcelList('saved')).toThrow(/Invalid/)
  expect(()=>writeParcelList('saved',['v2:bad'])).toThrow(/Invalid/)
  vi.stubGlobal('localStorage',{getItem:()=>JSON.stringify(Array.from({length:501},(_,i)=>String(i))),setItem})
  expect(()=>readParcelList('saved')).toThrow(/limit/)
  expect(setItem).not.toHaveBeenCalled()
})

it('caller cancellation closes an in-flight read and releases its deadline timer',async()=>{
  vi.useFakeTimers()
  try{
    const caller=new AbortController()
    const fetch=vi.fn((_url,options)=>new Promise<Response>((_resolve,reject)=>options.signal.addEventListener('abort',()=>reject(options.signal.reason))))
    vi.stubGlobal('fetch',fetch)
    const request=fetchDealByApn('fixture-parcel','fixture_county',{signal:caller.signal})
    const failed=expect(request).rejects.toHaveProperty('name','AbortError')
    caller.abort();await failed
    expect(fetch.mock.calls[0][1].signal.aborted).toBe(true)
    expect(vi.getTimerCount()).toBe(0)
  }finally{vi.useRealTimers()}
})

it('the deadline covers response-body parsing, not just initial response headers',async()=>{
  vi.useFakeTimers()
  try{
    vi.stubGlobal('fetch',vi.fn((_url,options)=>Promise.resolve({ok:true,status:200,json:()=>new Promise((_resolve,reject)=>options.signal.addEventListener('abort',()=>reject(options.signal.reason)))})))
    const failed=expect(fetchTopDeals()).rejects.toThrow(/unavailable/)
    await vi.advanceTimersByTimeAsync(12000);await failed
    expect(vi.getTimerCount()).toBe(0)
  }finally{vi.useRealTimers()}
})


it('keeps cents from source prices and does not turn unavailable values into zero',()=>{
  expect(formatCurrency(.49)).toBe('$0.49')
  expect(formatCurrency(25000.25)).toBe('$25,000.25')
  expect(formatCurrency(25000)).toBe('$25,000')
  expect(formatCurrency(0)).toBe('$0')
  for(const missing of [null,undefined,NaN,Infinity])expect(formatCurrency(missing)).toBe('—')
})

it('does not present an error-tagged payload as a healthy feed',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(Response.json({count:1,deals:[publishedDeal()],meta:{status:'unavailable',storage_source:'supabase'}})))
  await expect(fetchTopDeals()).rejects.toThrow(/unavailable/)
})
