// The pre-launch waitlist: states, roles, phone rule and the API call.
// The phone rule mirrors backend/apps/waitlist/phone.py.
import { NG_STATES } from '@/config/states'

// [key, label], in config/states.js order. The page says "FCT Abuja" where the
// app says "Abuja (FCT)" (design/prelaunch.reference.html).
export const WAITLIST_STATES = NG_STATES.map(([key, label]) => [key, key === 'fct' ? 'FCT Abuja' : label])

export const ROLES = [
  ['buy', 'Buy'],
  ['sell', 'Sell'],
  ['both', 'Both'],
  ['vendor', 'I run a declutter page'],
]

/** +234XXXXXXXXXX, or null. Strips non-digits, then a leading 234, then a leading 0. */
export function normalizeWaitlistPhone(value) {
  let digits = String(value ?? '').replace(/\D/g, '')
  if (digits.startsWith('234')) digits = digits.slice(3)
  if (digits.startsWith('0')) digits = digits.slice(1)
  return /^[789][01]\d{8}$/.test(digits) ? `+234${digits}` : null
}

/** Where the visitor came from: the referrer, else this host, plus any utm_* params. */
export function attribution(loc = window.location, referrer = document.referrer) {
  const params = new URLSearchParams(loc.search)
  return {
    source: (referrer || loc.hostname || 'local').slice(0, 200),
    utm_source: params.get('utm_source') || '',
    utm_medium: params.get('utm_medium') || '',
    utm_campaign: params.get('utm_campaign') || '',
  }
}

/**
 * POST /api/waitlist/. Resolves to the HTTP status (0 on a network failure).
 * Not api() from api/http.js: the endpoint is CSRF-exempt, so this skips the
 * extra /api/auth/csrf/ round trip a first-time visitor would otherwise make.
 */
export async function joinWaitlist(payload) {
  try {
    const res = await fetch('/api/waitlist/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(payload),
    })
    return res.status
  } catch {
    return 0
  }
}
