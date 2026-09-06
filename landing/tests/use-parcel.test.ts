import { createElement } from 'react'
import { act, create, type ReactTestRenderer } from 'react-test-renderer'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useParcel } from '../lib/use-parcel'
import { publishedDeal } from './support/public-deal'
import type { Deal } from '../lib/deals'
import type { ParcelRef } from '../lib/parcels'

const mocks=vi.hoisted(()=>({fetch:vi.fn()}))
vi.mock('../lib/deals',()=>({fetchDealByApn:mocks.fetch}))
let renderer:ReactTestRenderer|undefined
let latest:ReturnType<typeof useParcel>
let renders:{requested?:string;displayed?:string}[]=[]
function Probe(props:ParcelRef){latest=useParcel(props,0);renders.push({requested:props.county_id,displayed:latest.deal?.county_id});return null}
const mount=(props:ParcelRef)=>act(()=>{renderer=create(createElement(Probe,props))})
function deferred(){
  let resolve!:(value:{deal:Deal}|null)=>void
  let reject!:(error:Error)=>void
  const promise=new Promise<{deal:Deal}|null>((yes,no)=>{resolve=yes;reject=no})
  return {promise,resolve,reject}
}
beforeEach(()=>{vi.useFakeTimers();mocks.fetch.mockReset();renders=[]})
afterEach(()=>{act(()=>renderer?.unmount());renderer=undefined;vi.useRealTimers()})

it('never renders the previous county while switching the same APN',async()=>{
  const a=deferred(),b=deferred()
  mocks.fetch.mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise)
  mount({apn:'same',county_id:'a'})
  await act(async()=>a.resolve({deal:publishedDeal({apn:'same',county_id:'a'})}))
  expect(latest.deal?.county_id).toBe('a')
  act(()=>renderer!.update(createElement(Probe,{apn:'same',county_id:'b'})))
  expect(latest.loading).toBe(true);expect(latest.deal).toBeNull()
  expect(renders.some(row=>row.requested==='b'&&row.displayed==='a')).toBe(false)
  await act(async()=>b.resolve({deal:publishedDeal({apn:'same',county_id:'b'})}))
  expect(latest.deal?.county_id).toBe('b')
})

it('ignores a late response even when transport does not honor cancellation',async()=>{
  const a=deferred(),b=deferred()
  mocks.fetch.mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise)
  mount({apn:'same',county_id:'a'})
  const oldSignal=mocks.fetch.mock.calls[0][2].signal as AbortSignal
  act(()=>renderer!.update(createElement(Probe,{apn:'same',county_id:'b'})))
  expect(oldSignal.aborted).toBe(true)
  await act(async()=>b.resolve({deal:publishedDeal({apn:'same',county_id:'b'})}))
  await act(async()=>a.resolve({deal:publishedDeal({apn:'same',county_id:'a'})}))
  expect(latest.deal?.county_id).toBe('b')
})

it('the most recent retry wins for the same parcel',async()=>{
  const first=deferred(),second=deferred()
  mocks.fetch.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
  mount({apn:'same',county_id:'a'})
  act(()=>{void latest.load()})
  await act(async()=>second.resolve({deal:publishedDeal({apn:'same',county_id:'a',address:'Newest evidence'})}))
  await act(async()=>first.resolve({deal:publishedDeal({apn:'same',county_id:'a',address:'Old response'})}))
  expect(latest.deal?.address).toBe('Newest evidence')
})

it('a failed refresh hides earlier data rather than labeling it current',async()=>{
  mocks.fetch.mockResolvedValueOnce({deal:publishedDeal()}).mockRejectedValueOnce(new Error('Feed unavailable'))
  mount({apn:'fixture-parcel',county_id:'fixture_county'})
  await act(async()=>{})
  expect(latest.deal).not.toBeNull()
  await act(async()=>latest.load(true))
  expect(latest.deal).toBeNull();expect(latest.error).toBe('Feed unavailable')
})

it('expires displayed evidence at its deadline',async()=>{
  mocks.fetch.mockResolvedValue({deal:publishedDeal({verification_expires_at:new Date(Date.now()+100).toISOString()})})
  mount({apn:'fixture-parcel',county_id:'fixture_county'})
  await act(async()=>{})
  act(()=>{vi.advanceTimersByTime(101)})
  expect(latest.deal).toBeNull();expect(latest.error).toContain('expired')
})

it('unmount aborts requests and a missing parcel remains a not-found state',async()=>{
  const pending=deferred()
  mocks.fetch.mockReturnValue(pending.promise)
  mount({apn:'missing',county_id:'a'})
  await act(async()=>pending.resolve(null))
  expect(latest.loading).toBe(false);expect(latest.error).toBe('');expect(latest.deal).toBeNull()
  const signal=mocks.fetch.mock.calls[0][2].signal as AbortSignal
  act(()=>renderer!.unmount())
  expect(signal.aborted).toBe(true)
})
