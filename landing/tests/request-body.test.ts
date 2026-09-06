import { expect,it,vi } from 'vitest'
import { readJsonBody } from '../lib/request-body'
import { POST } from '../app/api/waitlist/route'
import { NextRequest } from 'next/server'

function streaming(stream:ReadableStream<Uint8Array>,signal?:AbortSignal){
  const init:RequestInit&{duplex:'half'}={method:'POST',body:stream,duplex:'half',signal}
  return new Request('https://app.example/api/waitlist',init)
}

it('caps elapsed time even if a body already contains valid JSON but never finishes',async()=>{
  vi.useFakeTimers()
  try{
    const cancel=vi.fn()
    const stream=new ReadableStream<Uint8Array>({start(controller){controller.enqueue(new TextEncoder().encode('{"consent":true}'))},cancel})
    const failed=expect(readJsonBody(streaming(stream),2048,5000)).rejects.toMatchObject({status:408})
    await vi.advanceTimersByTimeAsync(5000);await failed
    expect(cancel).toHaveBeenCalledTimes(1)
    expect(vi.getTimerCount()).toBe(0)
  }finally{vi.useRealTimers()}
})

it('does not let a hanging cancel implementation delay the timeout response',async()=>{
  vi.useFakeTimers()
  try{
    const stream=new ReadableStream<Uint8Array>({cancel(){return new Promise(()=>{})}})
    const failed=expect(readJsonBody(streaming(stream),2048,100)).rejects.toMatchObject({status:408})
    await vi.advanceTimersByTimeAsync(100);await failed
  }finally{vi.useRealTimers()}
})

it('releases the reader and deadline when the caller aborts',async()=>{
  vi.useFakeTimers()
  try{
    const controller=new AbortController(),cancel=vi.fn()
    const stream=new ReadableStream<Uint8Array>({cancel})
    const failed=expect(readJsonBody(streaming(stream,controller.signal))).rejects.toMatchObject({status:400})
    controller.abort();await failed
    expect(cancel).toHaveBeenCalledTimes(1)
    expect(stream.locked).toBe(false)
    expect(vi.getTimerCount()).toBe(0)
  }finally{vi.useRealTimers()}
})

it.each(['-1','NaN','3.5','10junk'])('rejects malformed declared body sizes: %s',async length=>{
  const request=new Request('https://app.example',{method:'POST',headers:{'content-length':length},body:'{}'})
  await expect(readJsonBody(request)).rejects.toMatchObject({status:400})
})

it('uses actual bytes rather than trusting an understated content length',async()=>{
  const request=new Request('https://app.example',{method:'POST',headers:{'content-length':'1'},body:'{"extra":"long value"}'})
  await expect(readJsonBody(request,5)).rejects.toMatchObject({status:413})
})

it('handles complete UTF-8 JSON split across byte boundaries',async()=>{
  const bytes=new TextEncoder().encode('{"name":"é"}')
  const stream=new ReadableStream<Uint8Array>({start(controller){for(const byte of bytes)controller.enqueue(new Uint8Array([byte]));controller.close()}})
  expect(await readJsonBody(streaming(stream))).toEqual({name:'é'})
  expect(stream.locked).toBe(false)
})

it('the waitlist route reports a stalled body without making a private write',async()=>{
  vi.useFakeTimers()
  try{
    const fetch=vi.fn();vi.stubGlobal('fetch',fetch)
    const stream=new ReadableStream<Uint8Array>({start(controller){controller.enqueue(new TextEncoder().encode('{"email":"person@example.com","consent":true}'))}})
    const incoming=new NextRequest('https://app.example/api/waitlist',{method:'POST',headers:{origin:'https://app.example','content-type':'application/json'},body:stream})
    const result=POST(incoming)
    await vi.advanceTimersByTimeAsync(5000)
    const response=await result
    expect(response.status).toBe(408)
    expect((await response.json()).error).toContain('timed out')
    expect(fetch).not.toHaveBeenCalled()
  }finally{vi.useRealTimers()}
})
