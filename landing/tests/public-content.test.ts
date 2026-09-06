import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { expect, it } from 'vitest'
import Hero from '../components/Hero'
import Solution from '../components/Solution'
import LiveOpportunities from '../components/LiveOpportunities'
import ResearchWorkspace from '../components/ResearchWorkspace'
import type { Deal } from '../lib/deals'

it('does not ship fictional parcels, sale tables or scores as public marketing',()=>{
  const html=[Hero,Solution,LiveOpportunities].map(Component=>renderToStaticMarkup(createElement(Component))).join('')
  expect(html).not.toMatch(/123-45-678|Sierra Vista Estates|\$4,900|\$9,700|Demo|fictional/i)
  expect(html).toContain('Checking the verified feed')
})

it('does not invent market or competition ratings from missing data',()=>{
  const deal:Deal={apn:'fixture',county_id:'fixture',verification_status:'verified',verified_at:new Date().toISOString(),verification_expires_at:new Date(Date.now()+3600000).toISOString()}
  const html=renderToStaticMarkup(createElement(ResearchWorkspace,{deal}))
  expect(html).not.toContain('60/100')
  expect(html).not.toContain('90/100')
  expect(html).not.toContain('$0')
})
