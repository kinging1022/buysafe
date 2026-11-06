// Display helpers for offers. The rules themselves (minimum, maximum) come
// from the API's `offer_rules`; fees come from the API's quotes.

const QUICK_PICK_PERCENTS = [5, 10, 15]
const QUICK_PICK_STEP = 500

// Round to the nearest step, halves to the even step. This gives the
// reference's picks for ₦185,000: ₦176,000, ₦166,500, ₦157,000.
function roundToStep(value, step) {
  const units = value / step
  const floor = Math.floor(units)
  const diff = units - floor
  const rounded = diff > 0.5 || (diff === 0.5 && floor % 2 === 1) ? floor + 1 : floor
  return rounded * step
}

/** [{ percent: 5, amount: 176000 }, …] for "−5% · ₦176,000" chips. */
export const quickPicks = (price) =>
  QUICK_PICK_PERCENTS.map((percent) => ({ percent, amount: roundToStep((price * (100 - percent)) / 100, QUICK_PICK_STEP) }))

/** 165000 on 185000 -> 11 */
export const belowPercent = (amount, price) => Math.round(((price - amount) / price) * 100)

/** "20 MIN AGO", "2H AGO", "YESTERDAY", "3D AGO" (offer cards' mono meta). */
export function offerAge(iso, now = new Date()) {
  const minutes = Math.floor((now - new Date(iso)) / 60000)
  if (minutes < 60) return `${Math.max(1, minutes)} MIN AGO`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}H AGO`
  const days = Math.floor(hours / 24)
  return days === 1 ? 'YESTERDAY' : `${days}D AGO`
}

/** Time until `iso`: "47H", or "35M" in the last hour. */
export function timeLeft(iso, now = new Date()) {
  const minutes = Math.max(0, Math.floor((new Date(iso) - now) / 60000))
  return minutes >= 60 ? `${Math.floor(minutes / 60)}H` : `${minutes}M`
}

/** "Samsung fridge, 2 doors" -> "SAMSUNG FRIDGE" (the offer dialog's eyebrow). */
export const shortTitle = (title) => title.split(',')[0].trim().toUpperCase()
