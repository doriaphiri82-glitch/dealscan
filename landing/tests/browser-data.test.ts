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
