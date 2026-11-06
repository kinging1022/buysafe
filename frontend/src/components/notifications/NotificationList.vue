<script setup>
import { computed, onBeforeUnmount, onMounted, ref, useTemplateRef, watch } from 'vue'
import { api } from '@/api/http'
import { useNotificationsStore } from '@/stores/notifications'
import { CATEGORY_COLORS, isToday, notificationAge } from '@/utils/notifications'

// The notification rows, grouped TODAY / EARLIER by the viewer's local date,
// 30 at a time with infinite scroll. Used by the mobile panel and the desktop
// page (design/notifications-2-panel-open-mobile). No icons in rows: the
// coloured type label does that job.
const props = defineProps({
  // The scrolling element for infinite scroll (the panel); null = the page.
  scrollRoot: { type: Object, default: null },
})
const emit = defineEmits(['navigate'])
const store = useNotificationsStore()

const items = ref([])
const nextPage = ref(1)
const loading = ref(false)
const loaded = ref(false)
const error = ref('')
const now = ref(new Date())

async function loadMore() {
  if (loading.value || !nextPage.value) return
  loading.value = true
  const page = nextPage.value
  const res = await api(`/notifications/?page=${page}`)
  loading.value = false
  loaded.value = true
  if (!res.ok) {
    error.value = 'Something went wrong. Please try again.'
    return
  }
  error.value = ''
  items.value = page === 1 ? res.data.results : [...items.value, ...res.data.results]
  nextPage.value = res.data.next ? page + 1 : null
}

function reload() {
  nextPage.value = 1
  return loadMore()
}

const groups = computed(() => {
  const today = items.value.filter((i) => isToday(i.created_at, now.value))
  const earlier = items.value.filter((i) => !isToday(i.created_at, now.value))
  return [
    { key: 'today', label: 'TODAY', items: today },
    { key: 'earlier', label: 'EARLIER', items: earlier },
  ].filter((g) => g.items.length)
})

const hasUnread = computed(() => store.unread > 0 || items.value.some((i) => !i.read_at))

function onClick(e, item) {
  if (!item.read_at) {
    item.read_at = new Date().toISOString()
    store.markRead(item.id)
  }
  // Modified clicks (new tab/window) keep the browser's default.
  if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return
  e.preventDefault()
  emit('navigate', item)
}

/** Optimistic. Returns false (and restores the rows) if the request failed. */
async function markAllRead() {
  const before = items.value.map((i) => i.read_at)
  const stamp = new Date().toISOString()
  items.value.forEach((i) => (i.read_at ||= stamp))
  const res = await store.markAllRead()
  if (!res.ok) items.value.forEach((i, n) => (i.read_at = before[n]))
  return res.ok
}

// New ones arrived (the count went up): reload from the top.
watch(
  () => store.unread,
  (count, before) => count > before && reload(),
)

const sentinel = useTemplateRef('sentinel')
let observer = null
let clock = null

onMounted(() => {
  loadMore()
  observer = new IntersectionObserver((entries) => entries[0].isIntersecting && loaded.value && loadMore(), {
    root: props.scrollRoot,
    rootMargin: '200px',
  })
  if (sentinel.value) observer.observe(sentinel.value)
  clock = setInterval(() => (now.value = new Date()), 60_000)
})
onBeforeUnmount(() => {
  observer?.disconnect()
  clearInterval(clock)
})

defineExpose({ markAllRead, hasUnread, reload })
</script>

<template>
  <div class="nl">
    <template v-for="group in groups" :key="group.key">
      <span class="nl__group">{{ group.label }}</span>
      <!-- A real link (open in new tab works); a plain click marks it read and
           the parent decides how to navigate. -->
      <RouterLink v-for="item in group.items" :key="item.id" v-slot="{ href }" :to="item.target_url" custom>
        <a
          :href="href"
          class="nl__row"
          :class="{ 'nl__row--unread': !item.read_at, 'nl__row--earlier': group.key === 'earlier' }"
          @click="onClick($event, item)"
        >
          <span class="nl__label" :style="{ color: CATEGORY_COLORS[item.category] || CATEGORY_COLORS.info }">{{ item.label }}</span>
          <span class="nl__time num">{{ notificationAge(item.created_at, now) }}</span>
          <span class="nl__text">
            {{ item.title_text }}<span v-if="!item.read_at" class="visually-hidden"> (unread)</span>
          </span>
        </a>
      </RouterLink>
    </template>

    <div v-if="loaded && !items.length && !error" class="nl__empty">
      <span class="nl__empty-h">You’re all caught up.</span>
      <span class="nl__empty-p">New offers and deal updates will show up here.</span>
    </div>
    <p v-if="error" class="nl__error" role="alert">{{ error }}</p>
    <div ref="sentinel" class="nl__sentinel" aria-hidden="true"></div>
  </div>
</template>

<style scoped>
.nl {
  display: flex;
  flex-direction: column;
}

.nl__group {
  padding: 18px 20px 6px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.14em;
  color: var(--muted);
}

.nl__group:first-child {
  padding-top: 16px;
}

.nl__row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 4px 12px;
  padding: 14px 20px 14px 17px;
  border-left: 3px solid transparent;
  border-bottom: 1px solid rgba(18, 20, 16, 0.1);
  background: transparent;
  color: var(--ink);
  text-decoration: none;
}

.nl__row--unread {
  background: #ffffff;
  border-left-color: var(--accent);
}

.nl__label {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.12em;
}

.nl__time {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--muted);
  text-align: right;
}

.nl__text {
  grid-column: span 2;
  font-size: 15px;
  line-height: 1.4;
  font-weight: 400;
}

.nl__row--unread .nl__text {
  font-weight: 600;
}

/* Read rows in EARLIER are softer. */
.nl__row--earlier:not(.nl__row--unread) .nl__text {
  color: var(--ink-2);
}

.nl__row:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}

.nl__empty {
  padding: 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.nl__empty-h {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.nl__empty-p {
  font-size: 15px;
  line-height: 1.5;
  color: var(--ink-2);
}

.nl__error {
  margin: 16px 20px;
  font-size: 15px;
  color: #a3361f;
}

.nl__sentinel {
  height: 1px;
}
</style>
