import { expect, it } from 'vitest'
import { countyFingerprint, countyHealth } from '../lib/county-health'
import fixture from './fixtures/source_fingerprint.json'
const now = Date.parse('2026-09-05T12:00:00Z')

it('matches the Python authorization fingerprint including Unicode and composite fields', () => {
  expect(countyFingerprint(fixture.county)).toBe(fixture.fingerprint)
})

it('requires current, complete, configuration-bound validation and explicit authorization', () => {
  const snapshot = { county:{...fixture.county,last_run_status:'ok',ingestion_status:'ingested',persisted_count:2}, stored_total:10, verified_total:0 }
  const good = countyHealth(snapshot,now)
  expect(good.ingestion_ready).toBe(true); expect(good.status).toBe('active')
  expect(good.published).toBe(0); expect(good.records).toBe(10)
  expect(good.data_freshness).toBeNull()
  for (const patch of [
    { last_validated_at:'2020-01-01T00:00:00Z' }, { validation_pagination_checked:false },
    { field_mapping:{apn:'OTHER'} }, { ingestion_authorized:false }, { authority_reviewed:false },
    { source_county_geoid:'99999' },
  ]) {
    const result = countyHealth({...snapshot,county:{...snapshot.county,...patch}},now)
    expect(result.ingestion_ready).toBe(false); expect(result.status).not.toBe('active')
  }
})


it('does not call an empty current inventory active because old run counters are nonzero',()=>{
  const county={...fixture.county,last_run_status:'ok',ingestion_status:'ingested',persisted_count:100}
  const result=countyHealth({county,stored_total:0,verified_total:0},now)
  expect(result.ingested).toBe(false)
  expect(result.status).not.toBe('active')
  expect(result.records).toBe(0)
})


it.each([
  {validation_source_fields_checked:'true'}, {validation_pagination_checked:'false'},
  {validation_sample_checked:6}, {validation_sample_checked:'5'},
  {authority_evidence_url:'https://user:password@county.example/gis'},
  {geoid:'invalid',source_county_geoid:'invalid'},
])('does not describe malformed validation proof as ready: %j',patch=>{
  const county={...fixture.county,...patch}
  const fingerprint=countyFingerprint(county)
  county.validated_source_fingerprint=county.authorized_source_fingerprint=fingerprint
  const result=countyHealth({county,stored_total:5,verified_total:0},now)
  expect(result.ingestion_ready).toBe(false)
})
