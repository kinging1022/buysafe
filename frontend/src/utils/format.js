// Display formatting shared by the account, browse and sell pages. Money is whole naira.

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const MONTHS_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'June', 'July', 'Aug', 'Sept', 'Oct', 'Nov', 'Dec']
const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

/** 185000 -> '₦185,000' */
export const naira = (amount) => '₦' + Math.round(amount).toLocaleString('en-NG')

/** Digits only, e.g. '₦185,000' -> '185000'. */
export const digitsOnly = (value) => String(value ?? '').replace(/\D/g, '')

/** 'September 2026' (or 'Sept 2026' with short: true) */
export function monthYear(iso, { short = false } = {}) {
  const d = new Date(iso)
  return `${(short ? MONTHS_SHORT : MONTHS)[d.getMonth()]} ${d.getFullYear()}`
}

/** 'Sat, 2pm' or 'Sat, 2:30pm', in the viewer's time zone. */
export function dayTime(iso) {
  const d = new Date(iso)
  const h = d.getHours() % 12 || 12
  const m = d.getMinutes()
  return `${WEEKDAYS[d.getDay()]}, ${h}${m ? `:${String(m).padStart(2, '0')}` : ''}${d.getHours() < 12 ? 'am' : 'pm'}`
}

/** 'today', '3 days ago', '1 week ago', '2 months ago'… */
export function relativeTime(iso, now = new Date()) {
  const then = new Date(iso)
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const days = Math.round((startOfDay(now) - startOfDay(then)) / 86400000)
  const ago = (n, unit) => `${n} ${unit}${n === 1 ? '' : 's'} ago`
  if (days <= 0) return 'today'
  if (days < 7) return ago(days, 'day')
  if (days < 30) return ago(Math.floor(days / 7), 'week')
  if (days < 365) return ago(Math.floor(days / 30), 'month')
  return ago(Math.floor(days / 365), 'year')
}

/** Browse cards: 'Just now', '2h ago', 'Today', 'Yesterday', '3d ago', '2w ago', '3mo ago'. */
export function shortAgo(iso, now = new Date()) {
  const then = new Date(iso)
  const hours = (now - then) / 3600000
  if (hours < 1) return 'Just now'
  if (hours < 6) return `${Math.floor(hours)}h ago`
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const days = Math.round((startOfDay(now) - startOfDay(then)) / 86400000)
  if (days <= 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days}d ago`
  if (days < 30) return `${Math.floor(days / 7)}w ago`
  if (days < 365) return `${Math.floor(days / 30)}mo ago`
  return `${Math.floor(days / 365)}y ago`
}

/** Q&A meta: 'JUST NOW', '20 MIN AGO', '2H AGO', 'YESTERDAY', '3 DAYS AGO', '2 WKS AGO', '3 MOS AGO'. */
export function qaAge(iso, now = new Date()) {
  const then = new Date(iso)
  const minutes = Math.floor((now - then) / 60000)
  if (minutes < 1) return 'JUST NOW'
  if (minutes < 60) return `${minutes} MIN AGO`
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const days = Math.round((startOfDay(now) - startOfDay(then)) / 86400000)
  if (days <= 0) return `${Math.floor(minutes / 60)}H AGO`
  if (days === 1) return 'YESTERDAY'
  if (days < 7) return `${days} DAYS AGO`
  if (days < 30) return `${Math.floor(days / 7)} WK${days < 14 ? '' : 'S'} AGO`
  const months = Math.max(1, Math.floor(days / 30))
  return `${months} MO${months === 1 ? '' : 'S'} AGO`
}
