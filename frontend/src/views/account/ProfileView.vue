<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/api/http'
import { ROUTES } from '@/config/account'
import { stateLabel } from '@/config/states'
import { monthYear } from '@/utils/format'
import { useIsMobile } from '@/composables/useMediaQuery'
import AppHeader from '@/components/account/AppHeader.vue'
import UserAvatar from '@/components/account/UserAvatar.vue'
import ListingCard from '@/components/account/ListingCard.vue'
import ListingRow from '@/components/account/ListingRow.vue'
import '@/styles/auth.css'
import '@/styles/account.css'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()

const user = computed(() => auth.user)
const location = computed(() => [user.value.area, stateLabel(user.value.state)].filter(Boolean).join(', '))

// ---- Password-updated confirmation (set by /profile/password) ----

const toast = ref(auth.flash)
auth.flash = ''
let toastTimer
if (toast.value) toastTimer = setTimeout(() => (toast.value = ''), 5000)

// ---- Stats ----

const stats = ref(null)

async function loadStats() {
  const res = await api('/me/listing-stats/')
  if (res.ok) stats.value = res.data
}

// ---- Tabs (synced to ?tab=, default all) ----

const TABS = [
  { key: 'active', label: 'Active', caption: 'Live on buysafe right now, including items with a deal in progress.' },
  { key: 'all', label: 'All listings', caption: 'Everything you’ve ever posted: live, in review, not approved and sold.' },
]

const tab = computed(() => (route.query.tab === 'active' ? 'active' : 'all'))
const tabCount = (key) => (stats.value ? (key === 'active' ? stats.value.live + stats.value.in_escrow : stats.value.all) : null)

function selectTab(key) {
  if (key === tab.value) return
  router.replace({ query: { ...route.query, tab: key === 'all' ? undefined : key } })
}

// Arrow keys move between tabs (roving tabindex).
async function onTabKeydown(e) {
  const i = TABS.findIndex((t) => t.key === tab.value)
  const next = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: TABS.length - 1 }[e.key]
  if (next === undefined) return
  e.preventDefault()
  const key = TABS[(next + TABS.length) % TABS.length].key
  selectTab(key)
  await nextTick()
  document.getElementById(`tab-${key}`)?.focus()
}

// ---- Listings (12 per page, "Load more") ----

const items = ref([])
const page = ref(0)
const hasMore = ref(false)
const loading = ref(false)
const loadError = ref(false)
let request = 0

async function loadPage(reset = false) {
  const id = ++request
  loading.value = true
  loadError.value = false
  if (reset) {
    items.value = []
    page.value = 0
  }
  const res = await api(`/me/listings/?tab=${tab.value}&page=${page.value + 1}`)
  if (id !== request) return // a newer tab/page request superseded this one
  loading.value = false
  if (!res.ok) {
    loadError.value = true
    return
  }
  items.value = [...items.value, ...res.data.results]
  page.value += 1
  hasMore.value = !!res.data.next
}

watch(tab, () => loadPage(true))

onMounted(() => {
  loadStats()
  loadPage(true)
})
onBeforeUnmount(() => clearTimeout(toastTimer))
</script>

<template>
  <div class="acct">
    <AppHeader />

    <main id="main" class="profile">
      <div v-if="toast" class="toast" role="status">
        <div class="af-box toast__box">
          <span class="af-box__label toast__label">DONE</span>
          <span>{{ toast }}</span>
        </div>
      </div>

      <!-- Header band -->
      <section class="hero on-dark" aria-labelledby="profile-name">
        <div class="guilloche hero__ring" aria-hidden="true"></div>
        <div class="acct-wrap hero__in">
          <div class="hero__who">
            <div class="hero__avatar">
              <div class="guilloche hero__avatar-ring" aria-hidden="true"></div>
              <UserAvatar
                :first-name="user.first_name"
                :last-name="user.last_name"
                :color="user.avatar_color"
                :size="isMobile ? 104 : 168"
                :ring="isMobile ? 5 : 6"
              />
              <span v-if="user.phone_verified" class="stamp stamp--m">PHONE VERIFIED</span>
            </div>
            <div class="hero__text">
              <div class="hero__eyebrow">YOUR PROFILE</div>
              <div class="hero__name-row">
                <h1 id="profile-name" class="hero__name">{{ user.first_name }} {{ user.last_name }}</h1>
                <span v-if="user.phone_verified" class="stamp stamp--d">PHONE VERIFIED</span>
              </div>
              <div class="hero__meta hero__meta--d">
                <template v-if="location"><span>{{ location }}</span><span class="sep">·</span></template>
                <span>Member since {{ monthYear(user.date_joined) }}</span><span class="sep">·</span>
                <span class="hero__phone">{{ user.masked_phone }}</span>
              </div>
              <div class="hero__meta hero__meta--m">
                <span>{{ [location, `Since ${monthYear(user.date_joined, { short: true })}`].filter(Boolean).join(' · ') }}</span>
                <span class="hero__phone">{{ user.masked_phone }}</span>
              </div>
              <p v-if="user.bio" class="hero__bio">“{{ user.bio }}”</p>
            </div>
          </div>
          <div class="hero__actions">
            <RouterLink to="/profile/edit" class="hero__btn hero__btn--primary">Edit profile</RouterLink>
            <RouterLink to="/profile/password" class="hero__btn hero__btn--outline">Change password</RouterLink>
          </div>
        </div>
      </section>

      <!-- Stats strip -->
      <div class="stats-band">
        <dl class="acct-wrap stats num">
          <div class="stat">
            <dt class="stat__label"><span class="d">LIVE NOW</span><span class="m">LIVE</span></dt>
            <dd class="stat__n">{{ stats?.live ?? '–' }}</dd>
          </div>
          <div class="stat">
            <dt class="stat__label stat__label--amber"><span class="d">IN ESCROW</span><span class="m">ESCROW</span></dt>
            <dd class="stat__n">{{ stats?.in_escrow ?? '–' }}</dd>
          </div>
          <div class="stat">
            <dt class="stat__label stat__label--green">SOLD</dt>
            <dd class="stat__n">{{ stats?.sold ?? '–' }}</dd>
          </div>
          <div class="stat">
            <dt class="stat__label"><span class="d">ALL LISTINGS</span><span class="m">ALL</span></dt>
            <dd class="stat__n">{{ stats?.all ?? '–' }}</dd>
          </div>
        </dl>
      </div>

      <!-- Listings -->
      <section class="acct-wrap listings" aria-labelledby="listings-title">
        <div class="listings__head">
          <div class="listings__title-col">
            <h2 id="listings-title" class="listings__title">Your listings</h2>
            <div role="tablist" aria-label="Filter listings" class="tabs" @keydown="onTabKeydown">
              <button
                v-for="t in TABS"
                :id="`tab-${t.key}`"
                :key="t.key"
                type="button"
                role="tab"
                class="tab"
                :aria-selected="tab === t.key"
                aria-controls="listings-panel"
                :tabindex="tab === t.key ? 0 : -1"
                @click="selectTab(t.key)"
              >
                {{ t.label }}<span v-if="tabCount(t.key) !== null" class="tab__count"> · {{ tabCount(t.key) }}</span>
              </button>
            </div>
          </div>
          <RouterLink :to="ROUTES.sell" class="acct-btn-outline listings__post" aria-label="Post an item">
            <span class="d" aria-hidden="true">+  Post an item</span><span class="m" aria-hidden="true">+</span>
          </RouterLink>
        </div>
        <p class="caption d">{{ TABS.find((t) => t.key === tab).caption }}</p>

        <div id="listings-panel" role="tabpanel" :aria-labelledby="`tab-${tab}`" :aria-busy="loading">
          <!-- First load: card-shaped blocks, no shimmer -->
          <div v-if="loading && !items.length" :class="isMobile ? 'rows' : 'grid'" aria-hidden="true">
            <template v-for="n in isMobile ? 4 : 8" :key="n">
              <div v-if="isMobile" class="sk sk--row"><span class="sk__thumb"></span><span class="sk__lines"><i></i><i></i><i></i></span></div>
              <div v-else class="sk sk--card"><span class="sk__photo"></span><span class="sk__lines"><i></i><i></i><i></i></span></div>
            </template>
          </div>

          <div v-else-if="loadError && !items.length" class="empty" role="alert">
            <p class="caption">We couldn’t load your listings. Check your connection and try again.</p>
            <button type="button" class="acct-btn-outline" @click="loadPage(true)">Try again</button>
          </div>

          <div v-else-if="!items.length" class="empty">
            <template v-if="tab === 'active'">
              <p class="caption">Nothing live right now.</p>
              <RouterLink :to="ROUTES.sell" class="acct-btn-outline">Post an item</RouterLink>
            </template>
            <p v-else class="caption">You haven’t posted anything yet.</p>
          </div>

          <template v-else>
            <div v-if="isMobile" class="rows">
              <ListingRow v-for="(item, i) in items" :key="item.id" :item="item" :index="i" />
            </div>
            <div v-else class="grid">
              <ListingCard v-for="(item, i) in items" :key="item.id" :item="item" :index="i" />
            </div>
            <div v-if="hasMore || loadError" class="more">
              <p v-if="loadError" class="caption" role="alert">We couldn’t load more. Try again.</p>
              <button type="button" class="acct-btn-outline" :disabled="loading" @click="loadPage()">
                {{ loading ? 'Loading…' : 'Load more' }}
              </button>
            </div>
          </template>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.profile {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
}

.m {
  display: none;
}

/* ---------- Toast ---------- */

.toast {
  position: fixed;
  z-index: 60;
  top: 92px;
  left: 0;
  right: 0;
  display: flex;
  justify-content: center;
  padding: 0 20px;
  pointer-events: none;
}

.toast__box {
  pointer-events: auto;
  max-width: 520px;
  box-shadow: 0 12px 30px rgba(18, 20, 16, 0.12);
}

.toast__label {
  color: var(--released);
}

/* ---------- Header band ---------- */

.hero {
  position: relative;
  overflow: hidden;
  background: var(--forest);
  color: var(--paper);
}

.hero__ring {
  position: absolute;
  width: 700px;
  height: 700px;
  border-radius: 50%;
  /* Anchored to the 1440 column's right edge, as in the reference. */
  right: max(-200px, calc((100% - 1440px) / 2 - 200px));
  top: -330px;
}

.hero__in {
  position: relative;
  padding-top: 64px;
  padding-bottom: 72px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 48px;
}

.hero__who {
  display: flex;
  gap: 40px;
  align-items: center;
  min-width: 0;
}

.hero__avatar {
  position: relative;
  flex-shrink: 0;
}

.hero__avatar-ring {
  position: absolute;
  inset: -22px;
  border-radius: 50%;
}

.hero__avatar .avatar {
  position: relative;
}

.hero__text {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.hero__eyebrow {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.14em;
  color: var(--accent);
}

.hero__name-row {
  display: flex;
  align-items: center;
  gap: 24px;
}

.hero__name {
  margin: 0;
  font-size: 72px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.045em;
  overflow-wrap: anywhere;
}

.stamp {
  flex-shrink: 0;
  transform: rotate(-6deg);
  border: 2.5px solid var(--lime);
  outline: 1.5px solid var(--lime);
  outline-offset: 3px;
  color: var(--lime);
  font-family: var(--font-mono);
  font-weight: 600;
  font-size: 13px;
  letter-spacing: 0.14em;
  padding: 5px 10px;
  border-radius: 4px;
  white-space: nowrap;
}

.stamp--m {
  display: none;
}

.hero__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 17px;
  color: var(--on-forest-2);
}

.hero__meta--m {
  display: none;
}

.sep {
  opacity: 0.5;
}

.hero__phone {
  font-family: var(--font-mono);
  font-size: 15px;
}

.hero__bio {
  margin: 4px 0 0;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 26px;
  line-height: 1.3;
  max-width: 640px;
  overflow-wrap: anywhere;
}

.hero__actions {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 230px;
  flex-shrink: 0;
}

.hero__btn {
  height: 52px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  border-radius: 12px;
  font-size: 16px;
}

.hero .hero__btn--primary,
.hero .hero__btn--primary:hover {
  background: var(--accent);
  color: var(--ink);
  font-weight: 700;
}

.hero .hero__btn--outline,
.hero .hero__btn--outline:hover {
  color: var(--paper);
  border: 1.5px solid rgba(243, 237, 224, 0.5);
  font-weight: 600;
}

/* ---------- Stats ---------- */

.stats-band {
  background: var(--paper-deep);
}

.stats {
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.stat {
  padding: 32px 0 32px 40px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-right: 1px solid rgba(18, 20, 16, 0.15);
}

.stat:first-child {
  padding-left: 0;
}

.stat:last-child {
  border-right: 0;
}

.stat__label {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.14em;
  color: var(--muted);
}

.stat__label--amber {
  color: var(--amber-ink);
}

.stat__label--green {
  color: var(--released);
}

.stat__n {
  margin: 0;
  font-size: 52px;
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 1;
}

/* ---------- Listings ---------- */

.listings {
  flex-grow: 1;
  padding-top: 80px;
  padding-bottom: 96px;
  display: flex;
  flex-direction: column;
  gap: 40px;
}

.listings__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 24px;
}

.listings__title-col {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.listings__title {
  margin: 0;
  font-size: 56px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.tabs {
  display: flex;
  gap: 6px;
  padding: 6px;
  background: var(--paper-deep);
  border-radius: 14px;
  align-self: flex-start;
}

.tab {
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

.tab[aria-selected='true'] {
  background: var(--ink);
  color: var(--paper);
}

.tab__count {
  font-family: var(--font-mono);
  font-weight: 500;
  opacity: 0.7;
}

.caption {
  margin: -12px 0 0;
  font-size: 16px;
  color: var(--muted);
}

.grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 28px;
}

.rows {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 20px;
}

.empty .caption,
.more .caption {
  margin: 0;
}

.more {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  margin-top: 40px;
}

/* Skeletons: paper blocks in the cards' shape. */
.sk {
  background: #efe9dc;
  overflow: hidden;
}

.sk--card {
  border-radius: 16px;
  height: 384px;
  display: flex;
  flex-direction: column;
}

.sk__photo {
  height: 200px;
  background: var(--paper-deep);
}

.sk__lines {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 18px 20px;
}

.sk__lines i {
  display: block;
  height: 14px;
  border-radius: 4px;
  background: var(--paper-deep);
}

.sk__lines i:nth-child(1) {
  width: 70%;
}

.sk__lines i:nth-child(2) {
  width: 45%;
}

.sk__lines i:nth-child(3) {
  width: 55%;
  height: 22px;
}

.sk--row {
  border-radius: 14px;
  padding: 12px;
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 14px;
}

.sk__thumb {
  height: 96px;
  border-radius: 10px;
  background: var(--paper-deep);
}

.sk--row .sk__lines {
  padding: 4px 0;
}

/* ---------- 768–1279: stacked buttons, 2 columns ---------- */

@media (max-width: 1279px) {
  .hero__in {
    flex-direction: column;
    align-items: flex-start;
    gap: 32px;
  }

  .hero__actions {
    flex-direction: row;
    width: auto;
  }

  .hero__btn {
    width: 230px;
  }

  .hero__name {
    font-size: 60px;
  }

  .grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

/* ---------- Phone ---------- */

@media (max-width: 767px) {
  .d {
    display: none;
  }

  .m {
    display: inline;
  }

  .toast {
    top: 76px;
  }

  .hero__ring {
    width: 440px;
    height: 440px;
    right: -220px;
    top: -200px;
    background: repeating-radial-gradient(circle at 50% 50%, rgba(243, 237, 224, 0) 0 8px, rgba(243, 237, 224, 0.1) 8px 9px);
  }

  .hero__in {
    padding-top: 36px;
    padding-bottom: 40px;
    align-items: stretch;
    gap: 18px;
  }

  .hero__who {
    flex-direction: column;
    align-items: stretch;
    gap: 18px;
  }

  .hero__avatar {
    display: flex;
    align-items: center;
    gap: 20px;
  }

  .hero__avatar-ring,
  .hero__eyebrow,
  .stamp--d,
  .hero__meta--d {
    display: none;
  }

  .stamp--m {
    display: inline-block;
    border-width: 2px;
    outline-offset: 2px;
    font-size: 11px;
    letter-spacing: 0.12em;
    padding: 4px 8px;
    border-radius: 3px;
  }

  .hero__text {
    gap: 18px;
  }

  .hero__name {
    margin-top: 6px;
    font-size: 44px;
  }

  .hero__meta--m {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 15px;
  }

  .hero__meta--m .hero__phone {
    font-size: 13px;
  }

  .hero__bio {
    margin: 0;
    font-size: 21px;
  }

  .hero__actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
    margin-top: 6px;
  }

  .hero__btn {
    width: auto;
    height: 50px;
    font-size: 15px;
  }

  .stats {
    padding: 0 12px;
  }

  .stat {
    padding: 18px 8px 18px 12px;
    gap: 4px;
  }

  .stat:first-child {
    padding-left: 8px;
  }

  .stat__label {
    font-size: 9px;
    letter-spacing: 0.1em;
  }

  .stat__n {
    font-size: 30px;
  }

  .listings {
    padding-top: 40px;
    padding-bottom: 56px;
    gap: 20px;
  }

  /* Title and "+" share a row; the tabs wrap below at full width. */
  .listings__head {
    align-items: center;
    flex-wrap: wrap;
    gap: 20px 12px;
  }

  .listings__title-col {
    display: contents;
  }

  .listings__title {
    font-size: 32px;
  }

  .tabs {
    order: 3;
    flex-basis: 100%;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    padding: 5px;
  }

  .tab {
    padding: 0 8px;
    font-size: 15px;
  }

  .tab__count {
    font-family: inherit;
    font-weight: inherit;
    opacity: 1;
  }

  .listings__post {
    width: 44px;
    height: 44px;
    padding: 0;
    font-size: 22px;
    font-weight: 600;
  }

  .more {
    margin-top: 20px;
  }
}
</style>
