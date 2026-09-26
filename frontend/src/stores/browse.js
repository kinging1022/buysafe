import { ref } from 'vue'
import { defineStore } from 'pinia'

// Browse results for the last query, kept so going back from a listing shows
// the same items (and Load more pages) at the same scroll position.
export const useBrowseStore = defineStore('browse', () => {
  const key = ref('')
  const items = ref([])
  const count = ref(0)
  const page = ref(0)
  const hasMore = ref(false)
  const scrollY = ref(0)

  function reset(newKey) {
    key.value = newKey
    items.value = []
    count.value = 0
    page.value = 0
    hasMore.value = false
    scrollY.value = 0
  }

  return { key, items, count, page, hasMore, scrollY, reset }
})
