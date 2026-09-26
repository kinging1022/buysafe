import { onBeforeUnmount, onMounted, ref } from 'vue'

/** Reactive matchMedia. The account pages aren't prerendered, so it's safe to read on setup. */
export function useMediaQuery(query) {
  const mql = typeof window === 'undefined' ? null : window.matchMedia(query)
  const matches = ref(mql?.matches ?? false)
  const update = (e) => (matches.value = e.matches)
  onMounted(() => mql?.addEventListener('change', update))
  onBeforeUnmount(() => mql?.removeEventListener('change', update))
  return matches
}

// Account pages follow the landing breakpoints: phone layout below 768px.
export const useIsMobile = () => useMediaQuery('(max-width: 767px)')
