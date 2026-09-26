// Nigerian mobile numbers. Mirrors backend/apps/users/phone.py.

/**
 * Extract up to 10 national digits from anything the user typed or pasted:
 * 0803…, 803…, +234803…, 234803… (spaces, dashes, brackets ignored).
 */
export function toNationalDigits(raw) {
  // National numbers never start with 0, 1 or 2, so a leading 234 is always
  // the country code and a leading 0 always the trunk prefix.
  let digits = String(raw ?? '').replace(/\D/g, '')
  if (digits.startsWith('234')) digits = digits.slice(3)
  else if (digits.startsWith('0')) digits = digits.slice(1)
  return digits.slice(0, 10)
}

/** '8031234567' -> '803 123 4567' (partial input formats progressively). */
export function formatNational(digits) {
  return [digits.slice(0, 3), digits.slice(3, 6), digits.slice(6, 10)].filter(Boolean).join(' ')
}

export const isValidNational = (digits) => /^[789]\d{9}$/.test(digits)

/** National digits -> E.164, or null if not a valid mobile number. */
export const toE164 = (digits) => (isValidNational(digits) ? `+234${digits}` : null)

/** '+2348031234567' -> '+234 803 ••• 4567' */
export function maskE164(e164) {
  const n = e164.slice(4)
  return `+234 ${n.slice(0, 3)} ••• ${n.slice(-4)}`
}
