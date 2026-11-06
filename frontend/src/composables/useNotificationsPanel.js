import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

// Set when the panel closes, so the next page's header puts focus back on
// the bell (each page mounts its own AppHeader).
let refocusBell = false
export const takeBellFocus = () => {
  const value = refocusBell
  refocusBell = false
  return value
}

// The mobile notifications panel is the /notifications route, so it's
// linkable and the phone's back button closes it. The bell toggles it:
// opening pushes history; closing goes back (or home, if it was opened
// from a link and there's nothing to go back to).
export function useNotificationsPanel() {
  const route = useRoute()
  const router = useRouter()

  const isOpen = computed(() => route.name === 'notifications')

  function open() {
    if (!isOpen.value) router.push({ name: 'notifications' })
  }

  function close() {
    if (!isOpen.value) return
    refocusBell = true
    if (window.history.state?.back) router.back()
    else router.replace('/listings')
  }

  const toggle = () => (isOpen.value ? close() : open())

  return { isOpen, open, close, toggle }
}
