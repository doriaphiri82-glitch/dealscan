import { readFileSync } from 'node:fs'
import { expect, it, vi } from 'vitest'
import { supportContact } from '../lib/support'

it('pins the tested Vercel Node runtime and carries the operator-provided public contact',()=>{
  const config=JSON.parse(readFileSync(new URL('../vercel.json',import.meta.url),'utf8'))
  const pkg=JSON.parse(readFileSync(new URL('../package.json',import.meta.url),'utf8'))
  expect(pkg.engines.node).toBe('22.x')
  expect(config.framework).toBe('nextjs')
  expect(config.installCommand).toBe('npm ci')
  expect(config.env.WAITLIST_CONTACT_EMAIL).toBe('doriaphiri82@gmail.com')
  expect(config.build.env.WAITLIST_CONTACT_EMAIL).toBe(config.env.WAITLIST_CONTACT_EMAIL)
  expect(Object.keys(config.env)).toEqual(['WAITLIST_CONTACT_EMAIL'])
  vi.stubEnv('WAITLIST_CONTACT_EMAIL',config.env.WAITLIST_CONTACT_EMAIL)
  expect(supportContact()).toBe('doriaphiri82@gmail.com')
})
