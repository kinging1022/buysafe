<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/http'
import { naira } from '@/utils/format'
import { rowMoney, rowPill, rowTime, rowWho } from '@/utils/dealRows'
import { useIsMobile } from '@/composables/useMediaQuery'
import AppHeader from '@/components/account/AppHeader.vue'
import '@/styles/account.css'

// /deals: Deals & messages (design/deals-1…4-*). Every chat belongs to a
// deal. Tabs are synced to ?tab=; deals waiting on you come first, then by
// deadline (the API's order). Refreshed every 30s while the tab is visible.
const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()

const TABS = [
  { key: 'active', label: 'Active', short: 'Active' },
  { key: 'completed', label: 'Completed', short: 'Done' },
  { key: 'refunded', label: 'Refunded', short: 'Refunded' },
]
const POLL_MS = 30_000

const tab = computed(() => (TABS.some((t) => t.key === route.query.tab) ? route.query.tab : 'active'))
const data = ref(null)
const failed = ref(false)

async function load() {
  const res = await api(`/deals/?tab=${tab.value}`)
  if (res.ok) {
    data.value = res.data
    failed.value = false
  } else if (!data.value) {
    failed.value = true
  }
}

function select(key) {
  router.replace({ query: key === 'active' ? {} : { tab: key } })
}

// Arrow keys move between tabs (tablist pattern).
function onTabKey(e, index) {
  const step = { ArrowRight: 1, ArrowLeft: -1 }[e.key]
  if (!step) return
  e.preventDefault()
  const next = TABS[(index + step + TABS.length) % TABS.length]
  select(next.key)
  document.getElementById(`deals-tab-${next.key}`)?.focus()
}

watch(tab, () => {
  data.value = null
  load()
})

let timer = null
function onVisibility() {
  clearInterval(timer)
  if (document.visibilityState === 'visible') {
    load()
    timer = setInterval(load, POLL_MS)
  }
}
onMounted(() => {
  load()
  timer = setInterval(load, POLL_MS)
  document.addEventListener('visibilitychange', onVisibility)
})
onBeforeUnmount(() => {
  clearInterval(timer)
  document.removeEventListener('visibilitychange', onVisibility)
})

const rows = computed(() =>
  (data.value?.results || []).map((row) => ({
    ...row,
    pill: rowPill(row, isMobile.value),
    who: rowWho(row),
    time: rowTime(row, isMobile.value),
    money: rowMoney(row),
    mine: row.turn === 'me',
  })),
)
const counts = computed(() => data.value?.counts || { active: 0, completed: 0, refunded: 0 })
</script>

<template>
  <div class="acct dl" :class="{ 'dl--m': isMobile }">
    <AppHeader />

    <main id="main" class="dl-main" :class="{ 'acct-wrap': !isMobile }">
      <div class="dl-head">
        <div class="dl-titles">
          <h1 class="dl-h1">Deals &amp; <span class="dl-serif">messages.</span></h1>
          <span v-if="!isMobile" class="dl-sub">Every chat belongs to a deal. Deals waiting on you come first.</span>
        </div>
        <div role="tablist" aria-label="Deal status" class="dl-tabs">
          <button
            v-for="(t, i) in TABS"
            :id="`deals-tab-${t.key}`"
            :key="t.key"
            type="button"
            role="tab"
            class="dl-tab"
            :aria-selected="tab === t.key"
            :tabindex="tab === t.key ? 0 : -1"
            aria-controls="deals-panel"
            @click="select(t.key)"
            @keydown="onTabKey($event, i)"
          >
            {{ isMobile ? t.short : t.label }}
            <span class="dl-tab__n num">{{ isMobile ? '' : '· ' }}{{ counts[t.key] }}</span>
          </button>
        </div>
      </div>

      <div id="deals-panel" role="tabpanel" :aria-labelledby="`deals-tab-${tab}`" class="dl-panel">
        <p v-if="failed" class="dl-error" role="alert">We couldn’t load your deals. Check your connection and try again.</p>

        <div v-else-if="data && !rows.length" class="dl-empty">
          <span class="dl-empty__h">No deals yet.</span>
          <span class="dl-empty__p">
            <template v-if="!isMobile">When you buy something or someone pays for your item, the deal and its chat appear here. Chat only opens after payment, so everyone is protected.</template>
            <template v-else>When you buy something or someone pays for your item, the deal and its chat appear here.</template>
          </span>
          <RouterLink to="/listings" class="dl-empty__btn">Browse items</RouterLink>
        </div>

        <div v-else-if="rows.length" class="dl-list">
          <RouterLink
            v-for="row in rows"
            :key="row.id"
            :to="`/deals/${row.id}`"
            class="dl-row"
            :class="{ 'dl-row--turn': row.mine }"
          >
            <span class="dl-photo photo"><img v-if="row.listing.photo" :src="row.listing.photo" alt="" /></span>

            <span class="dl-who">
              <span class="dl-title" :class="{ 'dl-title--turn': row.mine }">{{ row.listing.title }}</span>
              <span v-if="!isMobile" class="dl-by">{{ row.who.verb }} <strong>{{ row.who.name }}</strong> · <span class="dl-no">DEAL {{ row.id }}</span></span>
              <span v-else class="dl-by">{{ row.who.verb }} {{ row.who.name }}</span>
              <span v-if="isMobile" class="dl-tags">
                <span class="dl-pill" :class="`dl-pill--${row.pill.tone}`">{{ row.pill.text }}</span>
                <span v-if="row.time.text" class="dl-time num" :class="{ 'dl-time--urgent': row.time.urgent }">{{ row.time.text }}</span>
              </span>
            </span>

            <template v-if="!isMobile">
              <span class="dl-pill" :class="`dl-pill--${row.pill.tone}`">{{ row.pill.text }}</span>
              <span class="dl-time num" :class="{ 'dl-time--urgent': row.time.urgent }">{{ row.time.text }}</span>
              <span class="dl-money">
                <span class="dl-amount num">{{ naira(row.money.amount) }}</span>
                <span class="dl-money__k" :class="{ 'dl-money__k--amber': row.money.tone === 'amber' }">{{ row.money.label }}</span>
              </span>
              <span class="dl-unread-col">
                <span v-if="row.unread" class="dl-unread num" :aria-label="`${row.unread} unread messages`">{{ row.unread }}</span>
              </span>
            </template>
            <span v-else class="dl-right">
              <span class="dl-amount num">{{ naira(row.amount) }}</span>
              <span v-if="row.unread" class="dl-unread num" :aria-label="`${row.unread} unread`">{{ row.unread }}</span>
            </span>
          </RouterLink>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.photo {
  background-color: #e4dbc6;
  background-image: repeating-linear-gradient(135deg, rgba(18, 20, 16, 0.035) 0 10px, rgba(18, 20, 16, 0) 10px 20px);
  overflow: hidden;
  flex-shrink: 0;
}

.photo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.dl-main {
  flex-grow: 1;
  padding-top: 56px;
  padding-bottom: 96px;
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.dl-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 24px;
}

.dl-titles {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.dl-h1 {
  margin: 0;
  font-size: 72px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.045em;
}

.dl-serif {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 400;
  color: var(--released);
}

.dl-sub {
  font-size: 17px;
  color: var(--ink-2);
}

.dl-tabs {
  display: flex;
  gap: 6px;
  padding: 6px;
  background: var(--paper-deep);
  border-radius: 14px;
  flex-shrink: 0;
}

.dl-tab {
  height: 44px;
  padding: 0 20px;
  border: 0;
  border-radius: 10px;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
  background: transparent;
  color: var(--ink-2);
  cursor: pointer;
  white-space: nowrap;
}

.dl-tab[aria-selected='true'] {
  background: var(--ink);
  color: var(--paper);
}

.dl-tab__n {
  font-family: var(--font-mono);
  font-weight: 500;
  opacity: 0.7;
}

.dl-list {
  display: flex;
  flex-direction: column;
  border-top: 2px solid var(--ink);
}

.acct .dl-row {
  text-decoration: none;
  color: var(--ink);
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr) 300px 140px 150px 36px;
  gap: 24px;
  align-items: center;
  padding: 18px 16px;
  margin: 0 -16px;
  border-bottom: 1px solid rgba(18, 20, 16, 0.14);
}

.acct .dl-row:hover {
  color: var(--ink);
  background: rgba(18, 20, 16, 0.03);
}

.acct .dl-row--turn,
.acct .dl-row--turn:hover {
  background: rgba(245, 184, 46, 0.1);
}

.dl-photo {
  width: 72px;
  height: 72px;
  border-radius: 12px;
}

.dl-who {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.dl-title {
  font-size: 19px;
  font-weight: 600;
}

.dl-title--turn {
  font-weight: 800;
}

.dl-by {
  font-size: 14px;
  color: var(--muted);
}

.dl-by strong {
  color: var(--ink);
  font-weight: 600;
}

.dl-no {
  font-family: var(--font-mono);
  font-size: 12px;
}

.dl-pill {
  justify-self: start;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.1em;
  padding: 8px 12px;
  border-radius: 999px;
  border: 0;
}

.dl-pill--turn {
  background: var(--accent);
  color: var(--ink);
}

.dl-pill--wait {
  color: var(--muted);
  border: 1.5px solid rgba(18, 20, 16, 0.22);
}

.dl-pill--meetup {
  color: var(--released);
  border: 1.5px solid var(--released);
}

.dl-pill--done {
  background: rgba(30, 107, 69, 0.12);
  color: var(--released);
}

.dl-pill--refunded {
  background: rgba(163, 54, 31, 0.08);
  color: #a3361f;
}

.dl-time {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
}

.dl-time--urgent {
  color: #a3361f;
}

.dl-money {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.dl-amount {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.dl-money__k {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  color: var(--muted);
  text-align: right;
}

.dl-money__k--amber {
  color: var(--amber-ink);
}

.dl-unread-col {
  display: flex;
  justify-content: flex-end;
}

.dl-unread {
  min-width: 24px;
  height: 24px;
  padding: 0 7px;
  box-sizing: border-box;
  border-radius: 12px;
  background: var(--ink);
  color: var(--paper);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.dl-empty {
  border: 1.5px dashed rgba(18, 20, 16, 0.3);
  border-radius: 20px;
  padding: 56px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: flex-start;
}

.dl-empty__h {
  font-size: 34px;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.dl-empty__p {
  font-size: 17px;
  line-height: 1.55;
  color: var(--ink-2);
  max-width: 620px;
}

.acct .dl-empty__btn {
  margin-top: 8px;
  height: 52px;
  display: flex;
  align-items: center;
  padding: 0 24px;
  text-decoration: none;
  background: var(--forest);
  color: var(--paper);
  border-radius: 12px;
  font-size: 16px;
  font-weight: 700;
}

.dl-error {
  margin: 0;
  font-size: 16px;
  color: #a3361f;
}

/* Tablet widths: drop the fixed pill column so rows fit. */
@media (max-width: 1279px) and (min-width: 768px) {
  .acct .dl-row {
    grid-template-columns: 72px minmax(0, 1fr) auto 110px 130px 28px;
    gap: 16px;
  }

  .dl-h1 {
    font-size: 56px;
  }

  .dl-head {
    flex-wrap: wrap;
  }
}

/* ---- Mobile (design/deals-*-mobile) ---- */

.dl--m .dl-main {
  padding: 0;
  gap: 0;
}

.dl--m .dl-head {
  padding: 24px 20px 12px;
  flex-direction: column;
  align-items: stretch;
  gap: 14px;
}

.dl--m .dl-h1 {
  font-size: 36px;
  letter-spacing: -0.04em;
}

.dl--m .dl-tabs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 4px;
  padding: 4px;
  border-radius: 12px;
}

.dl--m .dl-tab {
  height: 42px;
  padding: 0;
  border-radius: 9px;
  font-size: 14px;
}

.dl--m .dl-list {
  border-top: 1px solid rgba(18, 20, 16, 0.14);
}

.dl--m.acct .dl-row {
  grid-template-columns: 56px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: start;
  padding: 14px 20px;
  margin: 0;
}

.dl--m .dl-photo {
  width: 56px;
  height: 56px;
  border-radius: 10px;
}

.dl--m .dl-who {
  gap: 3px;
}

.dl--m .dl-title {
  font-size: 15px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dl--m .dl-by {
  font-size: 12px;
}

.dl-tags {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 3px;
  flex-wrap: wrap;
}

.dl--m .dl-pill {
  font-size: 9px;
  letter-spacing: 0.08em;
  padding: 4px 8px;
}

.dl--m .dl-pill--wait {
  border: 1px solid rgba(18, 20, 16, 0.25);
}

.dl--m .dl-pill--meetup {
  border-width: 1px;
}

.dl--m .dl-time {
  font-size: 10px;
}

.dl-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.dl--m .dl-amount {
  font-size: 15px;
  letter-spacing: 0;
}

.dl--m .dl-unread {
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  border-radius: 11px;
  font-size: 10px;
}

.dl--m .dl-empty {
  margin: 12px 20px;
  border-radius: 16px;
  padding: 24px;
  gap: 8px;
}

.dl--m .dl-empty__h {
  font-size: 22px;
  letter-spacing: 0;
}

.dl--m .dl-empty__p {
  font-size: 14px;
}

.dl--m.acct .dl-empty__btn {
  align-self: flex-start;
  margin-top: 6px;
  height: 48px;
  padding: 0 18px;
  font-size: 15px;
}

.dl--m .dl-error {
  padding: 12px 20px;
}
</style>
