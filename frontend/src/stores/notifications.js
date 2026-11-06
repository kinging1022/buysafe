import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/http'

// The header's two counts: unread notifications (the bell / Notifications
// pill) and Deals & messages (unread messages plus deals waiting on you: the
// speech bubble / Deals & messages pill). The server's numbers are the truth;
// views cap what they show at "9+". Refreshed on route change (App.vue), when
// the window regains focus or the tab becomes visible, and every 30s while
// the tab is visible. No Django Channels yet, so this polls.
const POLL_MS = 30_000

export const useNotificationsStore = defineStore('notifications', () => {
  const unread = ref(0)
  const deals = ref(0)
  let timer = null
  let running = false

  async function refresh() {
    const [notes, attention] = await Promise.all([api('/notifications/unread-count/'), api('/deals/badge/')])
    if (notes.ok) unread.value = notes.data.count
    if (attention.ok) deals.value = attention.data.count
  }

  function schedule() {
    clearInterval(timer)
    timer = document.visibilityState === 'visible' ? setInterval(refresh, POLL_MS) : null
  }

  function onVisibility() {
    if (document.visibilityState === 'visible') refresh()
    schedule()
  }

  function start() {
    if (running) return
    running = true
    refresh()
    schedule()
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('focus', refresh)
  }

  function stop() {
    running = false
    clearInterval(timer)
    timer = null
    unread.value = 0
    deals.value = 0
    document.removeEventListener('visibilitychange', onVisibility)
    window.removeEventListener('focus', refresh)
  }

  async function markRead(id) {
    const res = await api(`/notifications/${id}/read/`, { method: 'POST' })
    refresh()
    return res
  }

  /** Optimistic: the count drops to 0 at once and comes back if the request fails. */
  async function markAllRead() {
    const before = unread.value
    unread.value = 0
    const res = await api('/notifications/read-all/', { method: 'POST' })
    if (!res.ok) unread.value = before
    return res
  }

  return { unread, deals, refresh, start, stop, markRead, markAllRead }
})

/** "3", "9", then "9+". Empty at 0 (no badge, no dot). */
export const badgeText = (count) => (count > 9 ? '9+' : count > 0 ? String(count) : '')
