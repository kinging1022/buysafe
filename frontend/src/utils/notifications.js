// Display helpers for the notifications panel (design/notifications-2-*).

/** "20 MIN", "1H", "YESTERDAY", "3 DAYS", "3 WKS", "2 MOS" — by the viewer's local date. */
export function notificationAge(iso, now = new Date()) {
  const then = new Date(iso)
  const minutes = Math.floor((now - then) / 60000)
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const days = Math.round((startOfDay(now) - startOfDay(then)) / 86400000)
  if (days <= 0) {
    if (minutes < 60) return `${Math.max(1, minutes)} MIN`
    return `${Math.floor(minutes / 60)}H`
  }
  if (days === 1) return 'YESTERDAY'
  if (days < 7) return `${days} DAYS`
  if (days < 30) {
    const weeks = Math.floor(days / 7)
    return `${weeks} WK${weeks === 1 ? '' : 'S'}`
  }
  const months = Math.max(1, Math.floor(days / 30))
  return `${months} MO${months === 1 ? '' : 'S'}`
}

export const isToday = (iso, now = new Date()) => new Date(iso).toDateString() === now.toDateString()

/** Type-label colour for each category from the API. */
export const CATEGORY_COLORS = {
  offer: '#A86A0C',
  action: '#A3361F',
  money: '#1E6B45',
  info: '#5B5E55',
}
