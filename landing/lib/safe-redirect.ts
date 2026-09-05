const DEFAULT_DESTINATION = '/my-dealscan'
const VALIDATION_ORIGIN = 'https://dealscan.invalid'

/** Accept only canonical same-origin paths, including after percent decoding. */
export function safeNext(value: string | null | undefined): string {
  if (!value || value !== value.trim()) return DEFAULT_DESTINATION
  let decoded = value
  // Reject nested encoding rather than relying on differences between browsers,
  // Next's router, and URL parsers (notably /\\host and encoded //host).
  for (let i = 0; i < 5; i++) {
    if (!decoded.startsWith('/') || decoded.startsWith('//') || /[\\\u0000-\u0020\u007f]/.test(decoded)) {
      return DEFAULT_DESTINATION
    }
    try {
      const url = new URL(decoded, VALIDATION_ORIGIN)
      if (url.origin !== VALIDATION_ORIGIN) return DEFAULT_DESTINATION
      const next = decodeURIComponent(decoded)
      if (next === decoded) return value
      decoded = next
    } catch {
      return DEFAULT_DESTINATION
    }
  }
  return DEFAULT_DESTINATION
}
