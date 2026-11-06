<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, upload } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { NG_STATES, stateLabel } from '@/config/states'
import { REVIEW_SLA, ROUTES } from '@/config/account'
import { CONDITIONS } from '@/config/listing'
import { naira } from '@/utils/format'
import { useMediaQuery } from '@/composables/useMediaQuery'
import AppHeader from '@/components/account/AppHeader.vue'
import NativeSelect from '@/components/ui/NativeSelect.vue'
import PhotoPicker from '@/components/sell/PhotoPicker.vue'
import ConditionSelect from '@/components/sell/ConditionSelect.vue'
import PriceInput from '@/components/sell/PriceInput.vue'
import FeeReceipt from '@/components/sell/FeeReceipt.vue'
import FeeTiers from '@/components/sell/FeeTiers.vue'
import PreviewCard from '@/components/sell/PreviewCard.vue'
import '@/styles/auth.css'
import '@/styles/account.css'

// Post an item (/sell) and edit (/sell/:id/edit). The fee is always the
// backend's: /listings/fee-quote/ for the live line, /listings/fee-schedule/
// for the table. Nothing here computes a fee.
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
// Below 1024px the payout column folds into the form: a <details> fee table
// under the price and a fixed bar with the payout and Submit.
const narrow = useMediaQuery('(max-width: 1023px)')

const editId = computed(() => (route.params.id ? Number(route.params.id) : null))
const DRAFT_KEY = 'buysafe.sellDraft'
const STATE_OPTIONS = NG_STATES.map(([value, label]) => ({ value, label }))
const GENERIC_ERROR = 'Something went wrong on our side. Check your connection and try again.'

const form = reactive({ title: '', category: '', condition: '', description: '', price: '', state: '', area: '' })
const photos = ref([])
const categories = ref([])
const schedule = ref(null)

// ---- Loading: categories, fee schedule, profile location or the listing ----

const loadingListing = ref(false)
const listing = ref(null) // edit mode: the saved listing
const lockedReason = ref('') // edit mode: in escrow or sold

function readDraft() {
  try {
    return JSON.parse(sessionStorage.getItem(DRAFT_KEY)) || null
  } catch {
    return null
  }
}

function writeDraft(value) {
  try {
    if (value) sessionStorage.setItem(DRAFT_KEY, JSON.stringify(value))
    else sessionStorage.removeItem(DRAFT_KEY)
  } catch {
    // storage unavailable: the form still works, it just won't survive a refresh
  }
}

// No payout account yet: the "PAYOUT NEEDED" note above Submit
// (design/payout-1-empty-desktop). Submitting still works.
const needsPayout = ref(false)
onMounted(async () => {
  const res = await api('/me/payout-account/')
  needsPayout.value = res.ok && !res.data.account
})

onMounted(async () => {
  api('/categories/').then((res) => res.ok && (categories.value = res.data))
  api('/listings/fee-schedule/').then((res) => res.ok && (schedule.value = res.data))

  if (editId.value) {
    loadingListing.value = true
    const res = await api(`/listings/${editId.value}/`)
    loadingListing.value = false
    if (!res.ok) {
      generalError.value = res.status === 404 ? 'We couldn’t find this item.' : GENERIC_ERROR
      return
    }
    listing.value = res.data
    Object.assign(form, {
      title: res.data.title,
      category: res.data.category,
      condition: res.data.condition,
      description: res.data.description,
      price: String(res.data.price),
      state: res.data.state,
      area: res.data.area,
    })
    photos.value = res.data.photos.map((p) => ({ key: `p${p.id}`, id: p.id, url: p.url }))
    if (['in_escrow', 'sold'].includes(res.data.display_status)) {
      lockedReason.value = 'This item has a deal in progress or is sold, so it can’t be edited.'
    }
    return
  }

  // New listing: location from the profile, then any unsent draft on top.
  form.state = auth.user?.state || ''
  form.area = auth.user?.area || ''
  const draft = readDraft()
  if (draft) Object.assign(form, draft)
})

// Keep the text fields (never photos) so a refresh doesn't lose them.
watch(form, (value) => !editId.value && writeDraft({ ...value }), { deep: true })

const fromProfile = computed(
  () => !!auth.user?.state && form.state === auth.user.state && form.area === (auth.user.area || ''),
)

// ---- The fee: quote from the API, 250ms after the price changes ----

const priceNumber = computed(() => (form.price ? Number(form.price) : null))
const quote = ref(null) // valid quote
const priceProblem = ref(null) // { detail, tier_key } below the minimum or above the maximum
let quoteTimer
let quoteReq = 0

watch(
  () => form.price,
  (price) => {
    clearTimeout(quoteTimer)
    if (!price) {
      quoteReq++
      quote.value = priceProblem.value = null
      return
    }
    // The previous numbers stay on screen until the new quote arrives.
    quoteTimer = setTimeout(async () => {
      const id = ++quoteReq
      const res = await api(`/listings/fee-quote/?price=${price}`)
      if (id !== quoteReq) return
      if (res.ok) {
        quote.value = res.data
        priceProblem.value = null
      } else if (res.status === 400 && res.data?.detail) {
        quote.value = null
        priceProblem.value = res.data
      }
      // Network errors and throttling keep the last numbers.
    }, 250)
  },
  { immediate: true },
)
onBeforeUnmount(() => clearTimeout(quoteTimer))

const tierKey = computed(() => quote.value?.tier_key || priceProblem.value?.tier_key || '')
const activeTierKey = computed(() => quote.value?.tier_key || '')
const tierTag = computed(() => schedule.value?.tiers.find((t) => t.key === tierKey.value)?.tag || '')

// ---- Preview ----

const coverUrl = computed(() => photos.value[0]?.url || null)
const place = computed(() => [form.area.trim(), stateLabel(form.state)].filter(Boolean).join(', '))
const conditionMeaning = computed(() => CONDITIONS.find((c) => c.key === form.condition)?.meaning || '')

// ---- Validation (same rules as the API) ----

const submitted = ref(false)
const serverErrors = reactive({})
const photoError = ref('') // from the picker (type, size, too many)
const generalError = ref('')

const clientErrors = computed(() => {
  const title = form.title.trim()
  const description = form.description.trim()
  const area = form.area.trim()
  return {
    photos: photos.value.length < 3 ? 'Add at least 3 photos.' : '',
    title: title.length < 5 || title.length > 120 ? 'Title must be 5–120 characters.' : '',
    category: form.category ? '' : 'Choose a category.',
    condition: form.condition ? '' : 'Choose the condition.',
    description: description.length < 20 || description.length > 1000 ? 'Description must be 20–1,000 characters.' : '',
    price: !form.price ? 'Enter a price.' : priceProblem.value ? priceProblem.value.detail : '',
    state: form.state ? '' : 'Choose a state.',
    area: area.length < 2 || area.length > 60 ? 'Enter the area or town (2–60 characters).' : '',
  }
})

const errors = computed(() =>
  Object.fromEntries(
    Object.keys(clientErrors.value).map((f) => [f, serverErrors[f] || (submitted.value ? clientErrors.value[f] : '')]),
  ),
)

function edited(field) {
  delete serverErrors[field]
  generalError.value = ''
}

const FIELD_TARGETS = {
  photos: '.pp [tabindex="0"], .pp button',
  title: '#sf-title',
  category: '#sf-category',
  condition: '#sf-condition',
  description: '#sf-description',
  price: '#sf-price',
  state: '#sf-state',
  area: '#sf-area',
}

async function focusFirstInvalid() {
  await nextTick()
  const first = Object.keys(FIELD_TARGETS).find((f) => errors.value[f])
  const el = first && document.querySelector(FIELD_TARGETS[first])
  if (!el) return
  el.scrollIntoView({ block: 'center', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
  el.focus({ preventScroll: true })
}

// ---- Submit: fields and photos in one request ----

const submitting = ref(false)
const progress = ref(0)

function buildForm() {
  const data = new FormData()
  data.append('title', form.title.trim())
  data.append('category', form.category)
  data.append('condition', form.condition)
  data.append('description', form.description.trim())
  data.append('price', form.price)
  data.append('state', form.state)
  data.append('area', form.area.trim())
  if (!editId.value) {
    photos.value.forEach((p) => data.append('photos', p.file, p.file.name))
    return data
  }
  let n = 0
  for (const p of photos.value) {
    if (p.id) {
      data.append('photo_order', `p${p.id}`)
    } else {
      data.append('photo_order', `n${n++}`)
      data.append('new_photos', p.file, p.file.name)
    }
  }
  return data
}

async function submit() {
  if (submitting.value || lockedReason.value) return
  submitted.value = true
  generalError.value = ''
  Object.keys(serverErrors).forEach((k) => delete serverErrors[k])
  if (Object.values(clientErrors.value).some(Boolean)) return focusFirstInvalid()

  submitting.value = true
  progress.value = 0
  const res = await upload(editId.value ? `/listings/${editId.value}/` : '/listings/', buildForm(), {
    method: editId.value ? 'PATCH' : 'POST',
    onProgress: (p) => (progress.value = p),
  })
  submitting.value = false

  if (res.ok) {
    writeDraft(null)
    photos.value.forEach((p) => p.file && URL.revokeObjectURL(p.url))
    auth.flash = 'Submitted for review. We’ll text you when it’s live.'
    return router.push({ path: '/profile', query: { tab: 'all' } })
  }
  if (res.status === 400 && res.data) {
    for (const field of Object.keys(FIELD_TARGETS)) {
      if (res.data[field]) serverErrors[field] = [].concat(res.data[field]).join(' ')
    }
    if (res.data.photo_order) serverErrors.photos = [].concat(res.data.photo_order).join(' ')
    if (Object.keys(serverErrors).length) return focusFirstInvalid()
  }
  if (res.status === 413) generalError.value = 'Those photos are too large to send. Try fewer or smaller photos.'
  else generalError.value = res.data?.detail || GENERIC_ERROR
}

const focusState = () => document.getElementById('sf-state')?.focus()
</script>

<template>
  <div class="acct sell">
    <AppHeader />

    <main id="main" class="sell__main">
      <div class="top">
        <div class="acct-wrap top__in">
          <RouterLink to="/profile" class="acct-back top__back">←  Back</RouterLink>
          <h1 class="top__h1">
            {{ editId ? 'Edit your item.' : 'Post an item.' }} <span class="top__accent">Get paid the safe way.</span>
          </h1>
        </div>
      </div>

      <div class="acct-wrap body">
        <form id="sell-form" class="form" novalidate @submit.prevent="submit">
          <div v-if="listing?.approval_status === 'rejected' && listing.rejection_reason" class="af-box form__box" role="alert">
            <span class="af-box__label af-box__label--error">NOT APPROVED</span> <span>{{ listing.rejection_reason }}</span>
          </div>
          <div v-if="lockedReason || generalError" class="af-box form__box" role="alert">
            <span class="af-box__label af-box__label--error">ERROR</span> <span>{{ lockedReason || generalError }}</span>
          </div>

          <!-- 01 Photos -->
          <section class="row row--first" aria-labelledby="sf-photos-label">
            <span class="row__n" aria-hidden="true">01</span>
            <div class="row__body">
              <div class="row__head">
                <span id="sf-photos-label" class="row__title"><span class="row__n-m" aria-hidden="true">01</span>Photos</span>
                <span class="row__count num">{{ photos.length }} OF 5</span>
              </div>
              <PhotoPicker
                v-model="photos"
                :invalid="!!errors.photos"
                describedby="sf-photos-help sf-photos-error"
                @update:model-value="edited('photos')"
                @error="(msg) => (photoError = msg)"
              />
              <span id="sf-photos-help" class="hint">
                <span class="d">The first photo is the cover. Drag to reorder. Clear daylight photos get approved faster.</span>
                <span class="m">First photo is the cover. Hold and drag to reorder.</span>
              </span>
              <p id="sf-photos-error" class="af-error" aria-live="polite">{{ photoError || errors.photos }}</p>
            </div>
          </section>

          <!-- 02 Title -->
          <section class="row">
            <span class="row__n" aria-hidden="true">02</span>
            <div class="row__body row__body--field">
              <label for="sf-title" class="row__title"><span class="row__n-m" aria-hidden="true">02</span>Title</label>
              <input
                id="sf-title"
                v-model="form.title"
                class="af-input field"
                :class="{ 'is-error': errors.title }"
                type="text"
                maxlength="120"
                :aria-invalid="!!errors.title || undefined"
                aria-describedby="sf-title-help sf-title-error"
                @input="edited('title')"
              />
              <span class="hint hint--split">
                <span id="sf-title-help" class="d">Say what it is, brand and size. “Samsung fridge, 2 doors” beats “Fridge for sale”.</span>
                <span class="counter num">{{ form.title.length }} / 120</span>
              </span>
              <p id="sf-title-error" class="af-error" aria-live="polite">{{ errors.title }}</p>
            </div>
          </section>

          <!-- 03–04 Category, condition -->
          <section class="row">
            <span class="row__n" aria-hidden="true">03–04</span>
            <div class="row__body row__pair">
              <div class="row__body--field">
                <label for="sf-category" class="row__title"><span class="row__n-m" aria-hidden="true">03</span>Category</label>
                <NativeSelect
                  id="sf-category"
                  v-model="form.category"
                  :options="categories.map((c) => ({ value: c.slug, label: c.label }))"
                  placeholder="Choose a category"
                  class="field-select"
                  :class="{ 'is-error': errors.category, 'is-empty': !form.category }"
                  :aria-invalid="!!errors.category || undefined"
                  aria-describedby="sf-category-error"
                  @change="edited('category')"
                />
                <p id="sf-category-error" class="af-error" aria-live="polite">{{ errors.category }}</p>
              </div>
              <div class="row__body--field">
                <span id="sf-condition-label" class="row__title"><span class="row__n-m" aria-hidden="true">04</span>Condition</span>
                <ConditionSelect
                  id="sf-condition"
                  v-model="form.condition"
                  labelledby="sf-condition-label"
                  :invalid="!!errors.condition"
                  describedby="sf-condition-meaning sf-condition-error"
                  @update:model-value="edited('condition')"
                />
                <span id="sf-condition-meaning" class="hint">{{ conditionMeaning }}</span>
                <p id="sf-condition-error" class="af-error" aria-live="polite">{{ errors.condition }}</p>
              </div>
            </div>
          </section>

          <!-- 05 Description -->
          <section class="row">
            <span class="row__n" aria-hidden="true">05</span>
            <div class="row__body row__body--field">
              <label for="sf-description" class="row__title"><span class="row__n-m" aria-hidden="true">05</span>Description</label>
              <textarea
                id="sf-description"
                v-model="form.description"
                class="af-input field field--area"
                :class="{ 'is-error': errors.description }"
                rows="5"
                maxlength="1000"
                :aria-invalid="!!errors.description || undefined"
                aria-describedby="sf-description-help sf-description-error"
                @input="edited('description')"
              ></textarea>
              <span class="hint hint--split">
                <span id="sf-description-help">
                  <span class="d">Be honest about faults. It protects you if the buyer raises a dispute.</span>
                  <span class="m">Be honest about faults.</span>
                </span>
                <span class="counter num">{{ form.description.length.toLocaleString('en-NG') }} / 1,000</span>
              </span>
              <p id="sf-description-error" class="af-error" aria-live="polite">{{ errors.description }}</p>
            </div>
          </section>

          <!-- 06 Price -->
          <section class="row">
            <span class="row__n" aria-hidden="true">06</span>
            <div class="row__body row__body--price">
              <label for="sf-price" class="row__title"><span class="row__n-m" aria-hidden="true">06</span>Price</label>
              <PriceInput
                id="sf-price"
                v-model="form.price"
                :invalid="!!errors.price"
                describedby="sf-payout"
                @update:model-value="edited('price')"
              />
              <div id="sf-payout" class="payout" aria-live="polite">
                <template v-if="quote">
                  <span class="payout__dot" aria-hidden="true"></span>
                  <span>You’ll receive <strong class="num payout__amount">{{ naira(quote.payout) }}</strong> after the {{ naira(quote.fee) }} fee ({{ quote.rate_label }}).</span>
                </template>
                <template v-else-if="priceProblem">
                  <span class="payout__dot payout__dot--error" aria-hidden="true"></span>
                  <span>{{ priceProblem.detail }} <strong class="num payout__none">₦0</strong></span>
                </template>
                <template v-else-if="submitted && errors.price">
                  <span class="payout__dot payout__dot--error" aria-hidden="true"></span>
                  <span>{{ errors.price }}</span>
                </template>
              </div>
              <div v-if="quote?.tip" class="tip">
                <span class="tip__label">TIP</span><span>{{ quote.tip }}</span>
              </div>
              <details v-if="narrow && schedule" class="howfee">
                <summary>How the fee works ▾</summary>
                <FeeTiers :tiers="schedule.tiers" :active-key="activeTierKey" compact />
              </details>
            </div>
          </section>

          <!-- 07–08 Location -->
          <section class="row row--last">
            <span class="row__n" aria-hidden="true">07–08</span>
            <div class="row__body">
              <div class="row__head">
                <span id="sf-where" class="row__title">
                  <span class="row__n-m" aria-hidden="true">07–08</span><span class="d">Where’s the item?</span><span class="m">Location</span>
                </span>
                <span v-if="fromProfile" class="profile-mark">
                  <span class="d">FROM YOUR PROFILE · <button type="button" class="profile-mark__change" @click="focusState">CHANGE FOR THIS ITEM</button></span>
                  <span class="m">FROM PROFILE</span>
                </span>
              </div>
              <div class="row__pair row__pair--loc">
                <div class="loc-field">
                  <label for="sf-state" class="loc-label">State</label>
                  <NativeSelect
                    id="sf-state"
                    v-model="form.state"
                    :options="STATE_OPTIONS"
                    placeholder="Choose a state"
                    class="field-select"
                    :class="{ 'is-error': errors.state, 'is-empty': !form.state }"
                    :aria-invalid="!!errors.state || undefined"
                    aria-describedby="sf-state-error"
                    @change="edited('state')"
                  />
                  <p id="sf-state-error" class="af-error" aria-live="polite">{{ errors.state }}</p>
                </div>
                <div class="loc-field">
                  <label for="sf-area" class="loc-label">Area or town</label>
                  <input
                    id="sf-area"
                    v-model="form.area"
                    class="af-input field"
                    :class="{ 'is-error': errors.area }"
                    type="text"
                    maxlength="60"
                    autocomplete="address-level2"
                    :aria-invalid="!!errors.area || undefined"
                    aria-describedby="sf-area-help sf-area-error"
                    @input="edited('area')"
                  />
                  <p id="sf-area-error" class="af-error" aria-live="polite">{{ errors.area }}</p>
                </div>
              </div>
              <span id="sf-area-help" class="hint">Buyers see the area, never your street address.</span>
            </div>
          </section>

          <div v-if="needsPayout" class="payout-note">
            <span class="payout-note__k">PAYOUT NEEDED</span>
            <span>You can submit now, but buyers can only pay once you’ve <RouterLink :to="ROUTES.payout">added your payout account</RouterLink>. It takes a minute.</span>
          </div>

          <div class="submit-row">
            <button type="submit" class="submit" :disabled="submitting || !!lockedReason || loadingListing">
              {{ submitting ? 'Submitting…' : 'Submit for review  →' }}
              <span v-if="submitting" class="submit__progress" :style="{ transform: `scaleX(${progress})` }" aria-hidden="true"></span>
            </button>
            <span class="submit-note">
              We check every listing before it goes live, usually within {{ REVIEW_SLA }}. You’ll get an SMS when it’s approved.
            </span>
          </div>
        </form>

        <!-- Desktop: live preview, payout and the fee table -->
        <aside v-if="!narrow" class="aside" aria-label="Your payout">
          <div class="aside__label">HOW BUYERS SEE IT</div>
          <PreviewCard
            :cover-url="coverUrl"
            :price="priceNumber"
            :title="form.title"
            :condition="form.condition"
            :place="place"
          />
          <FeeReceipt :price="priceNumber" :quote="quote" :tag="tierTag" />
          <FeeTiers v-if="schedule" :tiers="schedule.tiers" :active-key="activeTierKey" />
        </aside>
      </div>
    </main>

    <!-- Narrow screens: payout + submit, always in reach -->
    <div v-if="narrow" class="bar on-dark">
      <div class="bar__row num">
        <span class="bar__label">YOU RECEIVE</span>
        <span class="bar__amount" aria-live="polite">{{ naira(quote ? quote.payout : 0) }}</span>
      </div>
      <button type="submit" form="sell-form" class="bar__submit" :disabled="submitting || !!lockedReason || loadingListing">
        {{ submitting ? 'Submitting…' : 'Submit for review  →' }}
        <span v-if="submitting" class="submit__progress submit__progress--bar" :style="{ transform: `scaleX(${progress})` }" aria-hidden="true"></span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.m {
  display: none;
}

.sell__main {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
}

/* ---------- Title ---------- */

.top__in {
  padding-top: 56px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.top__back {
  min-height: 0;
  position: relative;
}

.top__back::after {
  content: '';
  position: absolute;
  inset: -12px -4px;
}

.top__h1 {
  margin: 0;
  font-size: 80px;
  line-height: 0.98;
  font-weight: 800;
  letter-spacing: -0.045em;
  text-wrap: balance;
}

.top__accent {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 400;
  letter-spacing: -0.01em;
  color: var(--released);
}

/* ---------- Layout ---------- */

.body {
  flex-grow: 1;
  padding-top: 48px;
  padding-bottom: 96px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 72px;
  align-items: start;
}

.form {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.form__box {
  margin-bottom: 24px;
}

/* Ledger rows: mono amber number, then the field. */
.row {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr);
  gap: 20px;
  padding: 32px 0;
  border-top: 1px solid rgba(18, 20, 16, 0.18);
}

.row--first {
  border-top: 2px solid var(--ink);
}

.row--last {
  border-bottom: 1px solid rgba(18, 20, 16, 0.18);
}

.row__n {
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 600;
  color: var(--amber-ink);
  padding-top: 4px;
}

.row__n-m {
  display: none;
}

.row__body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.row__body--field {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.row__body--price {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.row__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
}

.row__title {
  font-size: 22px;
  font-weight: 700;
}

.row__count {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--muted);
}

.row__pair {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  align-items: start;
}

.row__pair--loc {
  gap: 16px;
}

.field {
  width: 100%;
  height: 56px;
}

.field--area {
  height: auto;
  padding: 14px 16px;
  line-height: 1.55;
  resize: vertical;
}

.field-select :deep(select) {
  height: 56px;
  box-sizing: border-box;
  padding: 0 40px 0 16px;
  background: #ffffff;
  border: 1.5px solid rgba(18, 20, 16, 0.22);
  border-radius: 12px;
  font-family: var(--font-display);
  font-size: 17px;
  color: var(--ink);
  outline: none;
}

.field-select.is-empty :deep(select) {
  color: #8c8e85;
}

.field-select.is-error :deep(select) {
  border-color: var(--loss);
}

.field-select :deep(select:focus) {
  border: 2px solid var(--ink);
  box-shadow: 0 0 0 4px rgba(245, 184, 46, 0.45);
}

.hint {
  font-size: 14px;
  line-height: 1.5;
  color: var(--muted);
}

.hint--split {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.counter {
  font-family: var(--font-mono);
  font-size: 12px;
  white-space: nowrap;
  margin-left: auto;
}

.loc-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.loc-label {
  font-size: 14px;
  font-weight: 600;
}

.profile-mark {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--released);
  text-align: right;
}

.profile-mark__change {
  padding: 0;
  border: 0;
  background: none;
  font: inherit;
  letter-spacing: inherit;
  color: var(--released);
  text-decoration: underline;
  cursor: pointer;
  position: relative;
}

.profile-mark__change::after {
  content: '';
  position: absolute;
  inset: -15px -4px;
}

/* Payout line and tip */
.payout {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 17px;
  color: var(--ink-2);
  min-height: 26px;
}

.payout__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--released);
  flex-shrink: 0;
}

.payout__dot--error {
  background: var(--loss);
}

.payout__amount {
  color: var(--released);
  font-weight: 800;
}

.payout__none {
  color: #8c8e85;
  font-weight: 800;
}

.tip {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 12px 14px;
  background: var(--paper-deep);
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
  color: var(--ink-2);
  max-width: 560px;
}

.tip__label {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  color: var(--amber-ink);
  padding-top: 2px;
}

.howfee {
  margin-top: 4px;
}

.howfee summary {
  list-style: none;
  cursor: pointer;
  min-height: 44px;
  display: flex;
  align-items: center;
  font-size: 14px;
  font-weight: 700;
  color: var(--forest);
}

.howfee summary::-webkit-details-marker {
  display: none;
}

/* Submit */
.submit-row {
  display: flex;
  align-items: center;
  gap: 24px;
  padding-top: 36px;
}

.submit {
  position: relative;
  overflow: hidden;
  flex-shrink: 0;
  height: 60px;
  padding: 0 36px;
  border: 0;
  border-radius: 12px;
  background: var(--forest);
  color: var(--paper);
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  cursor: pointer;
  white-space: pre;
}

.submit:disabled {
  cursor: progress;
}

.submit__progress {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 4px;
  background: var(--lime);
  transform-origin: left;
  transition: transform 0.2s linear;
}

.submit-note {
  font-size: 15px;
  line-height: 1.5;
  color: var(--muted);
  max-width: 380px;
}

/* ---------- Aside ---------- */

.aside {
  position: sticky;
  top: 24px;
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.aside__label {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: var(--muted);
}

/* ---------- Fixed bar (below 1024px) ---------- */

.bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 40;
  background: var(--forest);
  color: var(--paper);
  padding: 14px max(20px, calc((100% - 720px) / 2)) calc(22px + env(safe-area-inset-bottom, 0px));
  display: flex;
  flex-direction: column;
  gap: 12px;
  box-shadow: 0 -12px 30px rgba(18, 20, 16, 0.18);
}

.bar__row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.bar__label {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--on-forest-muted);
}

.bar__amount {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: var(--lime);
}

.bar__submit {
  position: relative;
  overflow: hidden;
  height: 54px;
  border: 0;
  border-radius: 12px;
  background: var(--accent);
  color: var(--ink);
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
  cursor: pointer;
  white-space: pre;
}

.submit__progress--bar {
  background: var(--forest);
}

@media (max-width: 1279px) {
  .top__h1 {
    font-size: 64px;
  }

  .body {
    grid-template-columns: minmax(0, 1fr) 360px;
    gap: 48px;
  }
}

@media (max-width: 1023px) {
  .body {
    grid-template-columns: minmax(0, 1fr);
    padding-bottom: 180px; /* room for the fixed bar */
  }

  .submit-row {
    display: none;
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

  .top {
    background: var(--forest);
    color: var(--paper);
  }

  .top__in {
    padding-top: 12px;
    padding-bottom: 28px;
    gap: 16px;
  }

  .acct .top__back,
  .acct .top__back:hover {
    color: var(--paper);
    min-height: 44px;
  }

  .top__back::after {
    content: none;
  }

  .top__h1 {
    font-size: 40px;
    line-height: 1;
    letter-spacing: -0.04em;
  }

  .top__accent {
    color: var(--accent);
    letter-spacing: normal;
  }

  .body {
    padding-top: 0;
    padding-bottom: 150px;
  }

  .form__box {
    margin: 20px 0 0;
  }

  .row {
    display: block;
    padding: 24px 0;
    border-top: 0;
    border-bottom: 1px solid rgba(18, 20, 16, 0.18);
  }

  .row--first {
    border-top: 0;
  }

  .row--last {
    border-bottom: 0;
  }

  .row__n {
    display: none;
  }

  .row__n-m {
    display: inline;
    font-family: var(--font-mono);
    font-size: 12px;
    font-weight: 400;
    color: var(--amber-ink);
    margin-right: 8px;
  }

  .row__body {
    gap: 12px;
  }

  .row__body--field {
    gap: 8px;
  }

  .row__body--price {
    gap: 10px;
  }

  .row__title {
    font-size: 19px;
  }

  .row__count {
    font-size: 12px;
  }

  .row__pair {
    grid-template-columns: minmax(0, 1fr);
    gap: 14px;
  }

  .row__pair--loc {
    gap: 12px;
  }

  .loc-label {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }

  .field {
    height: 54px;
    padding: 0 14px;
  }

  .field--area {
    height: auto;
    padding: 12px 14px;
  }

  .field-select :deep(select) {
    height: 54px;
    padding-left: 14px;
  }

  .hint {
    font-size: 13px;
  }

  .profile-mark {
    font-size: 10px;
    letter-spacing: 0.1em;
  }

  .payout {
    font-size: 15px;
    gap: 8px;
    align-items: baseline;
  }

  .payout__dot {
    width: 9px;
    height: 9px;
  }

  .tip {
    gap: 10px;
    padding: 12px;
    font-size: 13px;
  }

  .tip__label {
    font-size: 10px;
  }

  .bar {
    padding: 14px 20px calc(22px + env(safe-area-inset-bottom, 0px));
  }
}

/* design/payout-1-empty-desktop: "IN THE SELL FORM, ABOVE SUBMIT FOR REVIEW". */
.payout-note {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding: 14px 16px;
  background: var(--paper-deep);
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
  color: var(--ink-2);
}

.payout-note a {
  font-weight: 700;
}

.payout-note__k {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: var(--amber-ink);
  padding-top: 3px;
  white-space: nowrap;
}
</style>
