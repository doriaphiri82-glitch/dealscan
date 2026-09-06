import 'server-only'

/** A public operator contact must exist before collecting signup requests. */
export function supportContact(): string | null {
  const value=process.env.WAITLIST_CONTACT_EMAIL?.trim()
  return value && value.length<=254 && /^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$/.test(value) ? value : null
}
