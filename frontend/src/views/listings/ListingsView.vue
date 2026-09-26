<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { useBrowseStore } from '@/stores/browse'
import { NG_STATES, stateLabel } from '@/config/states'
import { CONDITIONS, SORTS, shortCategory } from '@/config/listing'
import { digitsOnly } from '@/utils/format'
import { useIsMobile } from '@/composables/useMediaQuery'
import AppHeader from '@/components/account/AppHeader.vue'
import BrowseCard from '@/components/browse/BrowseCard.vue'
import BottomSheet from '@/components/ui/BottomSheet.vue'
import NativeSelect from '@/components/ui/NativeSelect.vue'
import '@/styles/account.css'

// Browse (/listings). The query string is the source of truth for every
// filter: ?state=&area=&category=&condition=a,b&min=&max=&sort=
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const store = useBrowseStore()
const isMobile = useIsMobile()

const QUICK_PICKS = 5
const STATE_OPTIONS = NG_STATES.map(([value, label]) => ({ value, label }))
const SORT_OPTIONS = SORTS.map((s) => ({ value: s.key, label: s.label }))

// ---- Filters from the URL ----

const q = computed(() => ({
  state: String(route.query.state || ''),
  area: String(route.query.area || ''),
  category: String(route.query.category || ''),
  conditions: String(route.query.condition || '').split(',').filter((c) => CONDITIONS.some((x) => x.key === c)),
  min: digitsOnly(route.query.min),
  max: digitsOnly(route.query.max),
  sort: SORTS.some((s) => s.key === route.query.sort) ? String(route.query.sort) : 'newest',
}))

function toQuery(f) {
  const out = {
    state: f.state || undefined,
    area: f.area?.trim() || undefined,
    category: f.category || undefined,
    condition: f.conditions?.length ? f.conditions.join(',') : undefined,
    min: f.min || undefined,
    max: f.max || undefined,
    sort: f.sort && f.sort !== 'newest' ? f.sort : undefined,
  }
  return Object.fromEntries(Object.entries(out).filter(([, v]) => v !== undefined))
}

// Discrete changes add a history entry; typing (debounced) replaces it.
function setFilters(patch, { replace = false } = {}) {
  const query = toQuery({ ...q.value, ...patch })
  return replace ? router.replace({ query }) : router.push({ query })
}

// ---- Text inputs: area, min, max (400ms debounce) ----

const areaText = ref(q.value.area)
const minText = ref(q.value.min)
const maxText = ref(q.value.max)
watch(() => q.value.area, (v) => v !== areaText.value.trim() && (areaText.value = v))
watch(() => q.value.min, (v) => (minText.value = v))
watch(() => q.value.max, (v) => (maxText.value = v))

const timers = {}
function debounced(field, value) {
  clearTimeout(timers[field])
  timers[field] = setTimeout(() => setFilters({ [field]: value }, { replace: true }), 400)
}

function onArea(e) {
  areaText.value = e.target.value
  debounced('area', areaText.value)
}

function onPrice(field, e) {
  const digits = digitsOnly(e.target.value)
  e.target.value = digits
  if (field === 'min') minText.value = digits
  else maxText.value = digits
  debounced(field, digits)
}

function showItems() {
  clearTimeout(timers.area)
  setFilters({ area: areaText.value })
}

// A new state starts fresh: all categories, no area from the old state.
function pickState(state) {
  clearTimeout(timers.area)
  areaText.value = ''
  setFilters({ state, area: '', category: '' })
}

const myLocation = computed(() => {
  const u = auth.user
  if (!u || !u.state || !u.area) return null
  return { state: u.state, area: u.area, label: `${u.area}, ${stateLabel(u.state)}` }
})

function useMyLocation() {
  clearTimeout(timers.area)
  areaText.value = myLocation.value.area
  setFilters({ state: myLocation.value.state, area: myLocation.value.area, category: '' })
}

function toggleCondition(key) {
  const set = new Set(q.value.conditions)
  set.has(key) ? set.delete(key) : set.add(key)
  setFilters({ conditions: CONDITIONS.map((c) => c.key).filter((k) => set.has(k)) })
}

function clearAll() {
  Object.values(timers).forEach(clearTimeout)
  areaText.value = minText.value = maxText.value = ''
  router.push({ query: toQuery({ sort: q.value.sort }) })
}

// ---- Facets: state chips (nationwide) and category counts (scoped) ----

const facets = ref(null)
let facetsReq = 0

async function loadFacets() {
  const id = ++facetsReq
  const params = new URLSearchParams({ state: q.value.state, area: q.value.area })
  const res = await api(`/listings/facets/?${params}`)
  if (id === facetsReq && res.ok) facets.value = res.data
}

const quickPicks = computed(() => {
  const states = facets.value?.states ?? []
  const top = states.slice(0, QUICK_PICKS)
  // The chosen state always has a chip, even outside the top five.
  const chosen = states.find((s) => s.key === q.value.state)
  if (q.value.state && !top.some((s) => s.key === q.value.state)) {
    top.push(chosen ?? { key: q.value.state, label: stateLabel(q.value.state), count: 0 })
  }
  return top
})

const categories = computed(() =>
  (facets.value?.categories ?? []).filter((c) => c.count > 0 || c.slug === q.value.category),
)
const currentCategory = computed(() => (facets.value?.categories ?? []).find((c) => c.slug === q.value.category))

// ---- Headline and count line ----

const headlineLead = computed(() => {
  if (!q.value.category) return 'Second-hand'
  if (!currentCategory.value) return 'Second-hand'
  return isMobile.value ? shortCategory(currentCategory.value) : currentCategory.value.label
})
const headlineTail = computed(() =>
  q.value.state ? `near you in ${stateLabel(q.value.state)}.` : 'anywhere in Nigeria.',
)
const where = computed(() => (q.value.state ? `in ${stateLabel(q.value.state)}` : 'across Nigeria'))

// ---- Results (the API pages at 24; Load more appends) ----

const loading = ref(false)
const loadError = ref(false)
let resultsReq = 0

const resultsKey = computed(() => new URLSearchParams(toQuery(q.value)).toString())

async function loadPage(reset) {
  const id = ++resultsReq
  if (reset) store.reset(resultsKey.value)
  loading.value = true
  loadError.value = false
  const params = new URLSearchParams({ ...toQuery(q.value), page: String(store.page + 1) })
  const res = await api(`/listings/?${params}`)
  if (id !== resultsReq) return
  loading.value = false
  if (!res.ok) {
    loadError.value = true
    return
  }
  store.items = reset ? res.data.results : [...store.items, ...res.data.results]
  store.count = res.data.count
  store.page += 1
  store.hasMore = !!res.data.next
}

watch(
  () => [q.value.state, q.value.area],
  () => loadFacets(),
)
watch(resultsKey, (key) => key !== store.key && loadPage(true))

// ---- Mobile Filters sheet (condition, price, sort) ----

const sheetOpen = ref(false)
const sheetCount = computed(
  () => q.value.conditions.length + (q.value.min ? 1 : 0) + (q.value.max ? 1 : 0) + (q.value.sort !== 'newest' ? 1 : 0),
)

// ---- Lifecycle: restore the last results and scroll position on back ----

onMounted(async () => {
  loadFacets()
  if (store.key === resultsKey.value && store.items.length) {
    await nextTick()
    window.scrollTo(0, store.scrollY)
  } else {
    loadPage(true)
  }
})

onBeforeUnmount(() => {
  store.scrollY = window.scrollY
  Object.values(timers).forEach(clearTimeout)
})

const itemsLabel = (n) => `${n.toLocaleString('en-NG')} ${n === 1 ? 'item' : 'items'}`
</script>

<template>
  <div class="acct browse">
    <AppHeader mobile-sell />

    <main id="main">
      <!-- Hero: headline, location bar, quick picks -->
      <section class="hero on-dark" aria-labelledby="browse-title">
        <div class="guilloche hero__ring" aria-hidden="true"></div>
        <div class="acct-wrap hero__in">
          <div class="hero__eyebrow">BROWSE · EVERY ITEM IS ESCROW-PROTECTED</div>
          <h1 id="browse-title" class="hero__h1">
            {{ headlineLead }}, <span class="hero__accent">{{ headlineTail }}</span>
          </h1>

          <form class="locbar" role="search" aria-label="Location" @submit.prevent="showItems">
            <label class="locbar__field locbar__field--state">
              <span class="locbar__label">STATE</span>
              <NativeSelect
                :model-value="q.state"
                :options="STATE_OPTIONS"
                placeholder="All of Nigeria"
                placeholder-selectable
                class="locbar__select"
                @change="pickState"
              />
            </label>
            <label class="locbar__field">
              <span class="locbar__label">AREA OR TOWN</span>
              <input
                class="locbar__input"
                type="text"
                :value="areaText"
                placeholder="e.g. Surulere, Wuse, GRA"
                autocomplete="address-level2"
                enterkeyhint="search"
                @input="onArea"
              />
            </label>
            <button type="submit" class="locbar__go">Show items</button>
          </form>

          <div class="picks">
            <span class="picks__label" aria-hidden="true">QUICK PICK</span>
            <div class="picks__chips">
              <button type="button" class="chip" :aria-pressed="!q.state" @click="pickState('')">
                All of Nigeria<span v-if="facets" class="chip__count"> {{ facets.total }}</span>
              </button>
              <button
                v-for="s in quickPicks"
                :key="s.key"
                type="button"
                class="chip"
                :aria-pressed="q.state === s.key"
                @click="pickState(s.key)"
              >
                {{ s.label }}<span class="chip__count"> {{ s.count }}</span>
              </button>
            </div>
            <button v-if="myLocation" type="button" class="picks__mine" @click="useMyLocation">
              Use my location ({{ myLocation.label }})
            </button>
          </div>
        </div>
      </section>

      <!-- Mobile: Filters button + category chips -->
      <div class="mbar">
        <button type="button" class="mbar__filters" aria-haspopup="dialog" @click="sheetOpen = true">
          Filters<template v-if="sheetCount"> · {{ sheetCount }}</template>
        </button>
        <button type="button" class="mchip" :aria-pressed="!q.category" @click="setFilters({ category: '' })">All</button>
        <button
          v-for="c in categories"
          :key="c.slug"
          type="button"
          class="mchip"
          :aria-pressed="q.category === c.slug"
          @click="setFilters({ category: c.slug })"
        >
          {{ shortCategory(c) }}
        </button>
      </div>

      <div class="acct-wrap body">
        <!-- Desktop sidebar -->
        <aside class="side" aria-label="Filters">
          <div class="side__group side__group--cats">
            <span id="f-cat" class="side__label">CATEGORY</span>
            <div role="group" aria-labelledby="f-cat" class="cats">
              <button type="button" class="cat" :aria-pressed="!q.category" @click="setFilters({ category: '' })">
                <span>All categories</span><span class="cat__n num">{{ facets?.scoped_total ?? '' }}</span>
              </button>
              <button
                v-for="c in categories"
                :key="c.slug"
                type="button"
                class="cat"
                :aria-pressed="q.category === c.slug"
                @click="setFilters({ category: c.slug })"
              >
                <span>{{ c.label }}</span><span class="cat__n num">{{ c.count }}</span>
              </button>
            </div>
          </div>

          <fieldset class="side__group">
            <legend class="side__label">CONDITION</legend>
            <label v-for="c in CONDITIONS" :key="c.key" class="check">
              <input type="checkbox" :checked="q.conditions.includes(c.key)" @change="toggleCondition(c.key)" />
              {{ c.label }}
            </label>
          </fieldset>

          <fieldset class="side__group">
            <legend class="side__label">PRICE (₦)</legend>
            <div class="prices">
              <input class="price" type="text" inputmode="numeric" placeholder="Min" aria-label="Minimum price" :value="minText" @input="onPrice('min', $event)" />
              <input class="price" type="text" inputmode="numeric" placeholder="Max" aria-label="Maximum price" :value="maxText" @input="onPrice('max', $event)" />
            </div>
          </fieldset>

          <button type="button" class="clear" @click="clearAll">Clear all filters</button>
        </aside>

        <!-- Results -->
        <section class="results" aria-labelledby="results-count">
          <div class="results__bar">
            <span id="results-count" class="results__count" aria-live="polite">
              <strong class="num">{{ itemsLabel(store.count) }}</strong> {{ where }}
            </span>
            <label class="sort">
              <span class="sort__label">Sort</span>
              <NativeSelect
                :model-value="q.sort"
                :options="isMobile ? SORTS.map((s) => ({ value: s.key, label: s.short })) : SORT_OPTIONS"
                class="sort__select"
                :chevron-size="12"
                @change="(sort) => setFilters({ sort })"
              />
            </label>
          </div>

          <div v-if="loading && !store.items.length" class="grid" aria-hidden="true">
            <div v-for="n in 6" :key="n" class="sk"><span class="sk__photo"></span><span class="sk__lines"><i></i><i></i><i></i></span></div>
          </div>

          <div v-else-if="loadError && !store.items.length" class="empty" role="alert">
            <span class="empty__title">We couldn’t load items.</span>
            <span class="empty__text">Check your connection and try again.</span>
            <button type="button" class="empty__btn" @click="loadPage(true)">Try again</button>
          </div>

          <div v-else-if="!store.items.length" class="empty">
            <span class="empty__title">Nothing here yet{{ q.state ? ` in ${stateLabel(q.state)}` : '' }}.</span>
            <span class="empty__text">
              <span class="d">Try a different category, or widen to all of Nigeria.</span>
              <span class="m">Try another category or all of Nigeria.</span>
            </span>
            <button type="button" class="empty__btn" @click="clearAll">Show everything</button>
          </div>

          <template v-else>
            <div class="grid">
              <BrowseCard v-for="(item, i) in store.items" :key="item.id" :item="item" :index="i" />
            </div>
            <div v-if="store.hasMore || loadError" class="more">
              <span v-if="loadError" class="empty__text" role="alert">We couldn’t load more. Try again.</span>
              <button type="button" class="acct-btn-outline" :disabled="loading" @click="loadPage(false)">
                {{ loading ? 'Loading…' : 'Load more' }}
              </button>
            </div>
          </template>
        </section>
      </div>
    </main>

    <!-- Mobile Filters sheet -->
    <BottomSheet :open="sheetOpen" title="Filters" full @close="sheetOpen = false">
      <fieldset class="side__group sheet-group">
        <legend class="side__label">CONDITION</legend>
        <label v-for="c in CONDITIONS" :key="c.key" class="check">
          <input type="checkbox" :checked="q.conditions.includes(c.key)" @change="toggleCondition(c.key)" />
          {{ c.label }}
        </label>
      </fieldset>
      <fieldset class="side__group sheet-group">
        <legend class="side__label">PRICE (₦)</legend>
        <div class="prices">
          <input class="price" type="text" inputmode="numeric" placeholder="Min" aria-label="Minimum price" :value="minText" @input="onPrice('min', $event)" />
          <input class="price" type="text" inputmode="numeric" placeholder="Max" aria-label="Maximum price" :value="maxText" @input="onPrice('max', $event)" />
        </div>
      </fieldset>
      <fieldset class="side__group sheet-group">
        <legend class="side__label">SORT</legend>
        <label v-for="s in SORTS" :key="s.key" class="check">
          <input type="radio" name="sheet-sort" :checked="q.sort === s.key" @change="setFilters({ sort: s.key })" />
          {{ s.label }}
        </label>
      </fieldset>
      <button type="button" class="clear" @click="clearAll">Clear all filters</button>
      <template #footer>
        <button type="button" class="sheet-go" aria-live="polite" @click="sheetOpen = false">
          Show {{ itemsLabel(store.count) }}
        </button>
      </template>
    </BottomSheet>
  </div>
</template>

<style scoped>
.m {
  display: none;
}

/* ---------- Hero ---------- */

.hero {
  position: relative;
  overflow: hidden;
  background: var(--forest);
  color: var(--paper);
}

.hero__ring {
  position: absolute;
  width: 760px;
  height: 760px;
  border-radius: 50%;
  right: max(-260px, calc((100% - 1440px) / 2 - 260px));
  top: -420px;
}

.hero__in {
  position: relative;
  padding-top: 56px;
  padding-bottom: 40px;
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.hero__eyebrow {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.14em;
  color: var(--accent);
}

.hero__h1 {
  margin: 0;
  font-size: 72px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.045em;
  text-wrap: balance;
}

.hero__accent {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 400;
  letter-spacing: -0.01em;
  color: var(--accent);
}

.locbar {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  background: var(--paper);
  border-radius: 16px;
  padding: 10px;
  color: var(--ink);
  max-width: 1000px;
  box-sizing: border-box;
}

.locbar__field {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 14px;
  min-width: 0;
}

.locbar__field--state {
  border-right: 1px solid rgba(18, 20, 16, 0.15);
}

.locbar__label {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--muted);
}

.locbar__select :deep(select),
.locbar__input {
  border: 0;
  padding: 0;
  background: transparent;
  font-family: var(--font-display);
  font-size: 18px;
  color: var(--ink);
  outline: none;
  min-height: 27px;
}

.locbar__select :deep(select) {
  font-weight: 700;
  padding-right: 24px;
}

.locbar__select :deep(.nsel__chevron) {
  right: 0;
}

.locbar__input {
  font-weight: 600;
  width: 100%;
}

.locbar__input::placeholder {
  color: #8c8e85;
  font-weight: 400;
}

/* The whole field shows the focus ring, as the inputs elsewhere. */
.locbar__field:focus-within {
  border-radius: 10px;
  box-shadow: 0 0 0 3px rgba(245, 184, 46, 0.6);
}

.locbar__select :deep(select):focus-visible,
.locbar__input:focus-visible {
  outline: none;
  box-shadow: none;
}

.locbar__go {
  height: 56px;
  padding: 0 28px;
  border: 0;
  border-radius: 12px;
  background: var(--forest);
  color: var(--paper);
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
  cursor: pointer;
}

.picks {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.picks__label {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.1em;
  color: var(--on-forest-muted);
  margin-right: 6px;
}

.picks__chips {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.chip {
  height: 44px;
  padding: 0 16px;
  border-radius: 999px;
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 600;
  background: transparent;
  color: var(--paper);
  border: 1.5px solid rgba(243, 237, 224, 0.4);
  cursor: pointer;
  white-space: nowrap;
}

.chip[aria-pressed='true'] {
  background: var(--accent);
  color: var(--ink);
  border-color: var(--accent);
}

.chip__count {
  margin-left: 0.3em;
  font-family: var(--font-mono);
  font-weight: 500;
  opacity: 0.65;
}

.picks__mine {
  margin-left: 8px;
  min-height: 44px;
  padding: 0;
  border: 0;
  background: none;
  color: var(--paper);
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 600;
  text-decoration: underline;
  cursor: pointer;
}

/* ---------- Mobile bar (hidden on desktop) ---------- */

.mbar {
  display: none;
}

/* ---------- Body ---------- */

.body {
  flex-grow: 1;
  padding-top: 48px;
  padding-bottom: 96px;
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 56px;
  align-items: start;
}

.side {
  display: flex;
  flex-direction: column;
  gap: 36px;
}

.side__group {
  display: flex;
  flex-direction: column;
  gap: 12px;
  border: 0;
  margin: 0;
  padding: 0;
  min-width: 0;
}

.side__group--cats {
  gap: 4px;
}

.side__label {
  display: block;
  width: 100%;
  padding: 0 0 10px;
  border-bottom: 2px solid var(--ink);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: var(--muted);
}

/* A legend can't take gap from its fieldset; match the 12px. */
legend.side__label {
  margin-bottom: 12px;
}

.cats {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cat {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 44px;
  padding: 0 12px;
  margin: 0 -12px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--ink);
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 400;
  text-align: left;
  cursor: pointer;
}

.cat[aria-pressed='true'] {
  background: var(--paper-deep);
  font-weight: 700;
}

.cat__n {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--muted);
}

.check {
  display: flex;
  gap: 12px;
  align-items: center;
  font-size: 16px;
  min-height: 32px;
  cursor: pointer;
}

.check input {
  position: relative;
  z-index: 1; /* above the row's enlarged touch area */
  width: 20px;
  height: 20px;
  margin: 0;
  accent-color: var(--forest);
}

/* 44px touch targets for the 32px rows. */
.check {
  position: relative;
}

.check::after {
  content: '';
  position: absolute;
  inset: -6px 0;
}

.prices {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.price {
  height: 46px;
  box-sizing: border-box;
  padding: 0 12px;
  background: #ffffff;
  border: 1.5px solid rgba(18, 20, 16, 0.22);
  border-radius: 10px;
  font-family: var(--font-display);
  font-size: 16px;
  color: var(--ink);
  outline: none;
  min-width: 0;
  font-variant-numeric: tabular-nums;
}

.price::placeholder {
  color: #8c8e85;
}

.price:focus {
  border: 2px solid var(--ink);
  box-shadow: 0 0 0 4px rgba(245, 184, 46, 0.45);
}

.clear {
  align-self: flex-start;
  background: transparent;
  border: 0;
  padding: 0;
  min-height: 44px;
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
  color: var(--forest);
  text-decoration: underline;
  cursor: pointer;
}

/* ---------- Results ---------- */

.results {
  display: flex;
  flex-direction: column;
  gap: 28px;
  min-width: 0;
}

.results__bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.results__count {
  font-size: 17px;
  color: var(--ink-2);
}

.results__count strong {
  color: var(--ink);
}

.sort {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
}

.sort__label {
  color: var(--muted);
}

.sort__select :deep(select) {
  height: 44px;
  padding: 0 36px 0 14px;
  background: #ffffff;
  border: 1.5px solid rgba(18, 20, 16, 0.22);
  border-radius: 10px;
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
}

.sort__select :deep(.nsel__chevron) {
  right: 14px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 28px;
}

.empty {
  border: 1.5px dashed rgba(18, 20, 16, 0.3);
  border-radius: 16px;
  padding: 56px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  align-items: flex-start;
}

.empty__title {
  font-size: 32px;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.empty__text {
  font-size: 17px;
  color: var(--ink-2);
}

.empty__btn {
  margin-top: 8px;
  height: 50px;
  padding: 0 22px;
  border: 1.5px solid var(--ink);
  background: transparent;
  border-radius: 12px;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
  cursor: pointer;
}

.more {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
}

/* Skeletons: paper blocks in the cards' shape, no shimmer. */
.sk {
  background: #efe9dc;
  border-radius: 16px;
  overflow: hidden;
  height: 420px;
  display: flex;
  flex-direction: column;
}

.sk__photo {
  height: 240px;
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
  width: 45%;
  height: 26px;
}

.sk__lines i:nth-child(2) {
  width: 75%;
}

.sk__lines i:nth-child(3) {
  width: 55%;
}

/* Mobile Filters sheet */
.sheet-group {
  padding-top: 20px;
}

.sheet-go {
  width: 100%;
  height: 54px;
  border: 0;
  border-radius: 12px;
  background: var(--forest);
  color: var(--paper);
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
  cursor: pointer;
}

/* ---------- 768–1279: 2 columns of cards ---------- */

@media (max-width: 1279px) {
  .hero__h1 {
    font-size: 60px;
  }

  .body {
    grid-template-columns: 220px minmax(0, 1fr);
    gap: 40px;
  }

  .grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1023px) {
  .locbar {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
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

  .hero__ring {
    width: 420px;
    height: 420px;
    right: -220px;
    top: -220px;
    background: repeating-radial-gradient(circle at 50% 50%, rgba(243, 237, 224, 0) 0 8px, rgba(243, 237, 224, 0.1) 8px 9px);
  }

  .hero__in {
    padding-top: 28px;
    padding-bottom: 24px;
    gap: 18px;
  }

  .hero__eyebrow,
  .locbar__go,
  .picks__label,
  .chip__count,
  .picks__mine {
    display: none;
  }

  .hero__h1 {
    font-size: 38px;
    letter-spacing: -0.04em;
  }

  .hero__accent {
    letter-spacing: normal;
  }

  .locbar {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 0;
    padding: 0;
    border-radius: 14px;
  }

  .locbar__field {
    padding: 10px 14px;
    gap: 0;
    min-height: 44px;
    box-sizing: border-box;
  }

  .locbar__field--state {
    border-right: 0;
    border-bottom: 1px solid rgba(18, 20, 16, 0.15);
  }

  .locbar__label {
    font-size: 10px;
  }

  .locbar__select :deep(select),
  .locbar__input {
    font-size: 17px;
  }

  .locbar__input {
    padding-top: 2px;
  }

  .locbar__select :deep(select) {
    padding-right: 28px;
  }

  .picks__chips {
    flex-wrap: nowrap;
    overflow-x: auto;
    margin: 0 -20px;
    padding: 0 20px;
    gap: 8px;
    scrollbar-width: none;
  }

  .picks__chips::-webkit-scrollbar {
    display: none;
  }

  .chip {
    flex-shrink: 0;
    padding: 0 14px;
    font-size: 14px;
  }

  .mbar {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    padding: 16px 20px;
    border-bottom: 1px solid rgba(18, 20, 16, 0.12);
    scrollbar-width: none;
  }

  .mbar::-webkit-scrollbar {
    display: none;
  }

  .mbar__filters,
  .mchip {
    flex-shrink: 0;
    height: 44px;
    padding: 0 14px;
    border-radius: 10px;
    font-family: var(--font-display);
    font-size: 14px;
    white-space: nowrap;
    cursor: pointer;
  }

  .mbar__filters {
    font-weight: 700;
    background: var(--ink);
    color: var(--paper);
    border: 0;
  }

  .mchip {
    font-weight: 600;
    background: transparent;
    color: var(--ink);
    border: 1.5px solid rgba(18, 20, 16, 0.2);
  }

  .mchip[aria-pressed='true'] {
    background: var(--paper-deep);
    border-color: var(--ink);
  }

  .body {
    display: block;
    padding-top: 20px;
    padding-bottom: 48px;
  }

  .side {
    display: none;
  }

  .results {
    gap: 16px;
  }

  .results__count {
    font-size: 14px;
  }

  .sort__label {
    display: none;
  }

  /* "Newest ▾" as text, still a real select. */
  .sort__select :deep(select) {
    height: 44px;
    padding: 0 18px 0 0;
    border: 0;
    background: transparent;
    font-size: 14px;
    font-weight: 700;
    text-align: right;
    text-align-last: right;
  }

  .sort__select :deep(.nsel__chevron) {
    right: 0;
  }

  .grid {
    gap: 12px;
  }

  .sk {
    height: 240px;
    border-radius: 14px;
  }

  .sk__photo {
    height: 150px;
  }

  .sk__lines {
    padding: 12px;
  }

  .empty {
    border-radius: 14px;
    padding: 28px 20px;
    gap: 10px;
  }

  .empty__title {
    font-size: 22px;
    letter-spacing: normal;
  }

  .empty__text {
    font-size: 15px;
  }

  .empty__btn {
    margin-top: 6px;
    height: 46px;
    padding: 0 18px;
    font-size: 15px;
  }
}
</style>
