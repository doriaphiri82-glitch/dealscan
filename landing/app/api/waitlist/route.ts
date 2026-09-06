import { createHmac } from 'node:crypto'
import { NextRequest, NextResponse } from 'next/server'
import { privateRpc, privateSupabaseConfig } from '@/lib/supabase-private'
import { supportContact } from '@/lib/support'
import { readJsonBody, RequestBodyError } from '@/lib/request-body'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'
export const maxDuration = 15
const headers = { 'Cache-Control': 'no-store' }
const MAX_BODY = 2048
const emailPattern = /^[^\s@<>"\\]+@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$/i

function sameOrigin(request:NextRequest):boolean {
  try {
    const header=request.headers.get('origin')||''
    const origin=new URL(header)
    const incoming=new URL(request.url)
    const host=request.headers.get('host')||incoming.host
    const previewHost=new URL('https://'+host).hostname.toLowerCase()
    // Known deployment proxies terminate TLS before forwarding to Next. Do not
    // trust a caller-supplied forwarded-protocol header as an origin override.
    const protocol=process.env.VERCEL==='1'||previewHost.endsWith('.e2b.app')?'https:':incoming.protocol
    const expected=new URL(protocol+'//'+host)
    return ['https:','http:'].includes(origin.protocol) && header===origin.origin
      && !expected.username && !expected.password && !expected.search && !expected.hash && expected.pathname==='/' && origin.origin===expected.origin
  } catch {return false}
}

export async function POST(request: NextRequest) {
  // JSON + same-origin browser requests; never accept a cross-site HTML form.
  if(!sameOrigin(request))return NextResponse.json({error:'Same-origin request required'},{status:403,headers})
  if (request.headers.get('content-type')?.split(';')[0].trim().toLowerCase() !== 'application/json') {
    return NextResponse.json({ error: 'JSON request required' }, { status: 415, headers })
  }
  let input: Record<string, unknown>
  try {
    const value = await readJsonBody(request,MAX_BODY,5000)
    if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error()
    input = value as Record<string, unknown>
  } catch(error) { return NextResponse.json({ error: error instanceof RequestBodyError?error.message:'Invalid request' }, { status: error instanceof RequestBodyError?error.status:400, headers }) }
  const email = typeof input.email === 'string' ? input.email.trim().toLowerCase() : ''
  if (!email || email.length > 254 || !emailPattern.test(email) || email.split('@')[0].length > 64) {
    return NextResponse.json({ error: 'Please enter a valid email address.' }, { status: 400, headers })
  }
  if (input.consent !== true) {
    return NextResponse.json({ error: 'Please consent to product updates before signing up.' }, { status: 400, headers })
  }
  try {
    // Trust proxy-provided client IPs only on the target Vercel deployment.
    // Other hosts share a conservative rate bucket; no raw IP is persisted.
    if (!supportContact()) throw new Error('Operator contact not configured')
    const ip = process.env.VERCEL === '1'
      ? (request.headers.get('x-vercel-forwarded-for') || request.headers.get('x-forwarded-for'))?.split(',')[0].trim() || 'unknown'
      : 'unknown'
    const requestKey = createHmac('sha256', privateSupabaseConfig().key).update(ip.slice(0,128)).digest('hex')
    const accepted = await privateRpc('join_waitlist', {
      p_email: email, p_source: input.source === 'final_cta' ? 'final_cta' : 'website', p_request_key: requestKey,
    })
    if (accepted === false) return NextResponse.json({ error: 'Too many requests. Please try again later.' }, { status: 429, headers: { ...headers, 'Retry-After': '3600' } })
    if (accepted !== true) throw new Error()
    // Identical response for existing and new addresses; no membership/count leak.
    return NextResponse.json({ ok: true, message: 'Your request for product updates is saved.' }, { status: 202, headers })
  } catch {
    // No Redis, filesystem or /tmp fallback can pretend a signup was durable.
    return NextResponse.json({ error: 'Signups are temporarily unavailable. Please try again later.' }, { status: 503, headers })
  }
}

export async function GET() {
  return NextResponse.json({ error: 'Method not allowed' }, { status: 405, headers: { ...headers, Allow: 'POST' } })
}
