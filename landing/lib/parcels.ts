export interface ParcelRef { apn: string; county_id?: string }
const validApn = (value: unknown): value is string => typeof value === 'string' && !!value.trim() && value.length <= 200 && !/[\u0000-\u001f\u007f]/.test(value)
const validCounty = (value: unknown): value is string => typeof value === 'string' && /^[a-zA-Z0-9_-]{1,150}$/.test(value)

/** New keys are county-scoped. Legacy bare APNs remain unresolved, never guessed. */
export function parcelKey(parcel: ParcelRef): string { return 'v2:'+JSON.stringify([parcel.county_id ?? null,parcel.apn]) }
export function parseParcelKey(key: string): ParcelRef | null {
  try {
    const value: unknown = key.startsWith('v2:') ? JSON.parse(key.slice(3)) : null
    if (Array.isArray(value) && value.length === 2 && validApn(value[1]) && (value[0] === null || validCounty(value[0]))) {
      return { apn:value[1],county_id:value[0] ?? undefined }
    }
  } catch { /* legacy APN; the detail API resolves ambiguity, never a partial list */ }
  return validApn(key) ? { apn:key } : null
}
export function parcelHref(parcel: ParcelRef): string {
  return `/deals/${encodeURIComponent(parcel.apn)}${parcel.county_id ? `?county_id=${encodeURIComponent(parcel.county_id)}` : ''}`
}
export function parcelLabel(key: string): string {
  const ref = parseParcelKey(key)
  return ref ? `${ref.apn}${ref.county_id ? ` · ${ref.county_id.replaceAll('_',' ')}` : ' · select county if ambiguous'}` : 'Invalid saved reference'
}
export function compareHref(keys: string[]): string {
  const params = new URLSearchParams()
  for (const key of keys.slice(0,3)) if (parseParcelKey(key)) params.append('parcel',key)
  return `/compare?${params}`
}
export function comparisonRefs(search: string): ParcelRef[] {
  const query = new URLSearchParams(search)
  const keys = query.getAll('parcel')
  const legacy = query.get('apns')?.split(',') ?? []
  return (keys.length ? keys : legacy).slice(0,3).map(parseParcelKey).filter((ref): ref is ParcelRef => ref !== null)
}
export function readParcelList(kind: 'saved'|'recent'): string[] {
  const value: unknown = JSON.parse(localStorage.getItem(`dealscan:${kind}`) || '[]')
  if (!Array.isArray(value)) throw new Error('Invalid browser storage')
  return [...new Set(value.filter((key): key is string => typeof key === 'string' && parseParcelKey(key) !== null))].slice(0,500)
}
export function writeParcelList(kind: 'saved'|'recent', keys: string[]): void {
  const unique=[...new Set(keys)]
  if (unique.length>500) throw new Error('Browser list limit reached')
  localStorage.setItem(`dealscan:${kind}`,JSON.stringify(unique))
}
