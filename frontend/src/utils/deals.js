// Display helpers for payments and deals. Copy comes from design/pay-*,
// deals-* and deal-*; amounts and states come from the API.

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const pad = (n) => String(n).padStart(2, '0')

/** '5:17 PM' */
export function clock(iso) {
  const d = new Date(iso)
  return `${d.getHours() % 12 || 12}:${pad(d.getMinutes())} ${d.getHours() < 12 ? 'AM' : 'PM'}`
}

/** 'Sat 4 Oct, 10:00' (meetups use the 24-hour clock in the designs). */
export function meetupWhen(iso) {
  const d = new Date(iso)
  return `${WEEKDAYS[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}, ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 'Sat 10:00' */
export const meetupShort = (iso) => {
  const d = new Date(iso)
  return `${WEEKDAYS[d.getDay()]} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 'Sat 4 Oct, 11:04 AM' */
export function dayClock(iso) {
  const d = new Date(iso)
  return `${WEEKDAYS[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}, ${clock(iso)}`
}

/** 'Sat 11:04 AM' */
export const shortDayClock = (iso) => `${WEEKDAYS[new Date(iso).getDay()]} ${clock(iso)}`

/** Today: '5:17 PM'; another day: 'SAT 11:02 AM' (chat timestamps, mono). */
export function stamp(iso, now = new Date()) {
  const d = new Date(iso)
  return d.toDateString() === now.toDateString() ? clock(iso) : `${WEEKDAYS[d.getDay()].toUpperCase()} ${clock(iso)}`
}

/** '24:13' (the 30-minute transfer window) */
export function mmss(seconds) {
  const s = Math.max(0, Math.floor(seconds))
  return `${pad(Math.floor(s / 60))}:${pad(s % 60)}`
}

/** '3:12:40' (deal deadlines) */
export function hms(seconds) {
  const s = Math.max(0, Math.floor(seconds))
  return `${Math.floor(s / 3600)}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`
}

/** '3H 12M', '2H 05M', '40M' (the deals list) */
export function hoursMinutes(seconds) {
  const m = Math.max(0, Math.floor(seconds / 60))
  return m >= 60 ? `${Math.floor(m / 60)}H ${pad(m % 60)}M` : `${m}M`
}

/** '3 WKS AGO' / '1 MONTH AGO'; short: '3 WKS' / '1 MO' (the deals list). */
export function ago(iso, { short = false, now = new Date() } = {}) {
  const days = Math.floor((now - new Date(iso)) / 86400000)
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`
  let text
  if (days < 1) text = 'TODAY'
  else if (days < 7) text = plural(days, 'DAY', 'DAYS')
  else if (days < 30) text = plural(Math.floor(days / 7), 'WK', 'WKS')
  else if (days < 365) text = short ? `${Math.floor(days / 30)} MO` : plural(Math.floor(days / 30), 'MONTH', 'MONTHS')
  else text = plural(Math.floor(days / 365), 'YR', 'YRS')
  return short || text === 'TODAY' ? text : `${text} AGO`
}

/** '9900000317' -> '9900 0003 17' (the account number, grouped 4-4-2). */
export const groupAccount = (number) => (number || '').replace(/^(\d{4})(\d{4})(\d+)$/, '$1 $2 $3')

/** 'Samsung fridge, 2 doors' -> 'Samsung fridge' */
export const shortTitle = (title) => (title || '').split(',')[0].trim()

export const personName = (p) => `${p.first_name} ${p.last_initial}.`

/** Every refund reason as the refunded receipt and the list's pill say it. */
export const REFUND_REASONS = {
  seller_missed_video: { long: 'Seller missed the video deadline', pill: 'SELLER MISSED VIDEO DEADLINE', short: 'NO VIDEO' },
  cancelled_after_3_bad: { long: 'Cancelled after 3 bad videos', pill: 'CANCELLED AFTER 3 BAD VIDEOS', short: '3 BAD VIDEOS' },
  no_show: { long: 'Seller didn’t show up', pill: 'SELLER DIDN’T SHOW UP', short: 'NO-SHOW' },
}
