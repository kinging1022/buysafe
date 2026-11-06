<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from '@/api/http'
import { conditionLabel } from '@/config/listing'
import { stateLabel } from '@/config/states'
import { ROUTES, listingLinks } from '@/config/account'
import { naira, relativeTime } from '@/utils/format'
import { useIsMobile } from '@/composables/useMediaQuery'
import AppHeader from '@/components/account/AppHeader.vue'
import StatusPill from '@/components/account/StatusPill.vue'
import OfferCard from '@/components/listing/OfferCard.vue'
import ListingQuestions from '@/components/questions/ListingQuestions.vue'
import '@/styles/account.css'

// The owner's listing page: design/detail-owner-*. Rendered by
// ListingDetailView when the viewer owns the listing. Offers refresh every
// 20s while the tab is visible.
const props = defineProps({
  listing: { type: Object, required: true }, // GET /api/listings/:id/ (with `owner`)
})

const POLL_MS = 20_000

const isMobile = useIsMobile()
const offers = ref({ count: 0, best: null, results: [] })
const loaded = ref(false)
const now = ref(new Date())

const links = computed(() => listingLinks(props.listing.id))
const cover = computed(() => props.listing.photos[0])
const price = computed(() => naira(props.listing.price))
const payout = computed(() => naira(props.listing.owner.fee.payout))
const place = computed(() => [props.listing.area, stateLabel(props.listing.state)].filter(Boolean).join(', '))
const meta = computed(() =>
  [`${conditionLabel(props.listing.condition)} condition`, props.listing.category.label, place.value, `Posted ${relativeTime(props.listing.created_at)}`]
    .filter(Boolean)
    .join(' · '),
)
const best = computed(() => (offers.value.best ? naira(offers.value.best) : '—'))

async function loadOffers() {
  const res = await api(`/listings/${props.listing.id}/offers/`)
  if (res.ok) offers.value = res.data
  loaded.value = true
  now.value = new Date() // accepted offers' "TO PAY" time
}

// ---- Decline, with Undo for 60s ----

const busyId = ref(null)
const actionError = ref('')
let clock = null
let undoEndTimer = null

// While a decline is undoable: tick every second (hides Undo on time), and
// reload when the window ends so the card leaves the list.
watch(offers, (value) => {
  clearInterval(clock)
  clearTimeout(undoEndTimer)
  const ends = value.results.filter((o) => o.undo_until).map((o) => new Date(o.undo_until).getTime())
  if (!ends.length) return
  now.value = new Date()
  clock = setInterval(() => (now.value = new Date()), 1000)
  undoEndTimer = setTimeout(loadOffers, Math.max(...ends) - Date.now() + 500)
})

async function act(offer, action) {
  busyId.value = offer.id
  actionError.value = ''
  const res = await api(`/offers/${offer.id}/${action}/`, { method: 'POST' })
  busyId.value = null
  if (!res.ok) actionError.value = res.data?.detail || 'Something went wrong. Please try again.'
  await loadOffers()
}
const decline = (offer) => act(offer, 'decline')
const undo = (offer) => act(offer, 'undo-decline')
const accept = (offer) => act(offer, 'accept')

// No payout account: buyers can't pay (design/payout-*-desktop, owner banner).
const needsPayout = computed(() => props.listing.owner.payout_ready === false)

let timer = null
function startPolling() {
  stopPolling()
  timer = setInterval(loadOffers, POLL_MS)
}
function stopPolling() {
  clearInterval(timer)
  timer = null
}
function onVisibility() {
  if (document.visibilityState === 'visible') {
    loadOffers()
    startPolling()
  } else {
    stopPolling()
  }
}

onMounted(() => {
  loadOffers()
  if (document.visibilityState === 'visible') startPolling()
  document.addEventListener('visibilitychange', onVisibility)
})
onBeforeUnmount(() => {
  stopPolling()
  clearInterval(clock)
  clearTimeout(undoEndTimer)
  document.removeEventListener('visibilitychange', onVisibility)
})
</script>

<template>
  <div class="acct lo" :class="{ 'lo--m': isMobile }">
    <!-- ================= Desktop ================= -->
    <template v-if="!isMobile">
      <AppHeader />
      <section class="lo-bar on-dark" aria-label="Your listing">
        <div class="acct-wrap lo-bar__in">
          <div class="guilloche lo-bar__g" aria-hidden="true"></div>
          <div class="lo-bar__text">
            <span class="lo-bar__label">YOUR LISTING</span>
            <span class="lo-bar__note">This is what you see. Buyers see Buy now and Make an offer instead.</span>
          </div>
          <div class="lo-bar__links">
            <RouterLink :to="links.edit" class="lo-bar__edit">Edit listing</RouterLink>
            <RouterLink :to="{ path: links.view, query: { as: 'buyer' } }" class="lo-bar__view">View as buyer</RouterLink>
          </div>
        </div>
      </section>

      <div v-if="needsPayout" class="acct-wrap lo-alert-wrap">
        <div role="alert" class="lo-alert">
          <span class="lo-alert__text">
            <span class="lo-alert__h">Buyers can’t pay for this yet.</span>
            <span class="lo-alert__p">Add a payout account so we know where to send your money.</span>
          </span>
          <RouterLink :to="ROUTES.payout" class="lo-alert__btn">Add account</RouterLink>
        </div>
      </div>

      <main id="main" class="acct-wrap lo-main">
        <div class="lo-left">
          <div class="lo-cover photo">
            <img v-if="cover" :src="cover" alt="" />
            <span class="lo-cover__count num">{{ listing.photos.length }} PHOTOS</span>
          </div>
          <div class="lo-summary">
            <StatusPill :status="listing.display_status" class="lo-pill" />
            <h1 class="lo-title">{{ listing.title }}</h1>
            <span class="lo-price num">{{ price }}</span>
            <span class="lo-receive num">At full price you receive {{ payout }}</span>
            <span class="lo-meta">{{ meta }}</span>
          </div>
          <div class="lo-stats num">
            <div class="lo-stat"><span class="lo-stat__k">VIEWS</span><span class="lo-stat__v">{{ listing.owner.view_count }}</span></div>
            <div class="lo-stat"><span class="lo-stat__k lo-stat__k--amber">OFFERS</span><span class="lo-stat__v">{{ offers.count }}</span></div>
            <div class="lo-stat"><span class="lo-stat__k">BEST</span><span class="lo-stat__v">{{ best }}</span></div>
          </div>
          <details class="lo-desc">
            <summary><span>Your description</span><span class="lo-desc__sign" aria-hidden="true"></span></summary>
            <p>{{ listing.description }}</p>
          </details>
          <!-- design/qa-owner-*-desktop: the tip beside the owner's Questions. -->
          <div class="lo-tip">
            <span class="lo-tip__h">ANSWERING WELL</span>
            <span>Be specific: “Left door, lower corner” beats “small dent”. If a question reveals something missing, add it to your description too.</span>
            <span>Each question gets one answer. You can edit it any time; buyers see “edited”.</span>
          </div>
        </div>

        <section class="lo-offers" aria-labelledby="offers-h">
          <div class="lo-offers__head">
            <h2 id="offers-h" class="lo-offers__h">
              Offers <span class="lo-offers__n num" aria-live="polite">{{ offers.count }}</span>
            </h2>
            <span class="lo-offers__sub">Highest first · each expires 48h after it’s sent</span>
          </div>

          <p v-if="actionError" class="lo-error" role="alert">{{ actionError }}</p>
          <div v-if="offers.results.length" class="lo-list">
            <OfferCard
              v-for="offer in offers.results"
              :key="offer.id"
              :offer="offer"
              :price="listing.price"
              :now="now"
              :busy="busyId === offer.id"
              @decline="decline"
              @undo="undo"
              @accept="accept"
            />
          </div>
          <div v-else-if="loaded" class="lo-none">
            <span class="lo-none__h">No offers yet.</span>
            <span class="lo-none__p">Buyers can also pay your full price with Buy now. You’ll get an SMS the moment an offer or payment comes in.</span>
          </div>

          <p class="lo-foot">Offers below 60% of your price are blocked automatically. Declining is private: the buyer is told the offer wasn’t accepted.</p>

          <ListingQuestions :listing="listing" owner class="lo-questions" />
        </section>
      </main>
    </template>

    <!-- ================= Mobile ================= -->
    <template v-else>
      <AppHeader />
      <section class="lo-mhead on-dark" aria-label="Your listing">
        <div class="guilloche lo-mhead__g" aria-hidden="true"></div>
        <div class="lo-mhead__top">
          <RouterLink to="/profile" class="lo-mhead__back">←  Profile</RouterLink>
          <RouterLink :to="links.edit" class="lo-mhead__edit">Edit</RouterLink>
        </div>
        <div class="lo-mhead__item">
          <span class="lo-mhead__thumb photo"><img v-if="cover" :src="cover" alt="" /></span>
          <div class="lo-mhead__text">
            <StatusPill :status="listing.display_status" small class="lo-pill" />
            <span class="lo-mhead__title">{{ listing.title }}</span>
            <span class="lo-mhead__price num">{{ price }}</span>
          </div>
        </div>
      </section>

      <div class="lo-stats lo-stats--m num">
        <div class="lo-stat"><span class="lo-stat__k">VIEWS</span><span class="lo-stat__v">{{ listing.owner.view_count }}</span></div>
        <div class="lo-stat"><span class="lo-stat__k lo-stat__k--amber">OFFERS</span><span class="lo-stat__v">{{ offers.count }}</span></div>
        <div class="lo-stat"><span class="lo-stat__k">BEST</span><span class="lo-stat__v lo-stat__v--best">{{ best }}</span></div>
      </div>

      <main id="main" class="lo-mmain">
        <div v-if="needsPayout" role="alert" class="lo-alert lo-alert--m">
          <span class="lo-alert__text">
            <span class="lo-alert__h">Buyers can’t pay for this yet.</span>
            <span class="lo-alert__p">Add a payout account so we know where to send your money.</span>
          </span>
          <RouterLink :to="ROUTES.payout" class="lo-alert__btn">Add account</RouterLink>
        </div>
        <h1 class="lo-mh1">Offers <span class="lo-offers__n num" aria-live="polite">{{ offers.count }}</span></h1>
        <p v-if="actionError" class="lo-error" role="alert">{{ actionError }}</p>
        <OfferCard
          v-for="offer in offers.results"
          :key="offer.id"
          :offer="offer"
          :price="listing.price"
          :now="now"
          :busy="busyId === offer.id"
          compact
          @decline="decline"
          @undo="undo"
          @accept="accept"
        />
        <!-- No mobile reference for this state: detail-owner-5-no-offers-desktop at phone sizes. -->
        <div v-if="loaded && !offers.results.length" class="lo-none lo-none--m">
          <span class="lo-none__h">No offers yet.</span>
          <span class="lo-none__p">Buyers can also pay your full price with Buy now. You’ll get an SMS the moment an offer or payment comes in.</span>
        </div>

        <ListingQuestions :listing="listing" owner compact class="lo-questions-m" />
      </main>
    </template>
  </div>
</template>

<style scoped>
.photo {
  background-color: #e4dbc6;
  background-image: repeating-linear-gradient(135deg, rgba(18, 20, 16, 0.035) 0 12px, rgba(18, 20, 16, 0) 12px 24px);
}

.guilloche {
  position: absolute;
  border-radius: 50%;
  background: repeating-radial-gradient(circle at 50% 50%, rgba(243, 237, 224, 0) 0 9px, rgba(243, 237, 224, 0.1) 9px 10px);
  pointer-events: none;
}

.lo-pill {
  align-self: flex-start;
}

/* design/payout-1-empty-desktop: "ON YOUR LISTING PAGE (OWNER VIEW)". */
.lo-alert-wrap {
  padding-top: 24px;
}

.lo-alert {
  display: flex;
  gap: 14px;
  align-items: center;
  padding: 16px 18px;
  background: rgba(163, 54, 31, 0.07);
  border: 1.5px solid #a3361f;
  border-radius: 14px;
}

.lo-alert__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex-grow: 1;
}

.lo-alert__h {
  font-size: 16px;
  font-weight: 700;
}

.lo-alert__p {
  font-size: 14px;
  line-height: 1.45;
  color: var(--ink-2);
}

.acct .lo-alert__btn {
  height: 44px;
  display: flex;
  align-items: center;
  padding: 0 16px;
  text-decoration: none;
  background: var(--ink);
  color: var(--paper);
  border-radius: 10px;
  font-size: 14px;
  font-weight: 700;
  white-space: nowrap;
}

.lo-alert--m {
  align-items: flex-start;
  flex-direction: column;
}

/* ---- Owner bar ---- */

.lo-bar {
  background: var(--forest);
  color: var(--paper);
  position: relative;
  overflow: hidden;
}

.lo-bar__in {
  padding-top: 22px;
  padding-bottom: 22px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  position: relative;
}

.lo-bar__g {
  width: 520px;
  height: 520px;
  right: -120px;
  top: -300px;
}

.lo-bar__text {
  position: relative;
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 16px;
}

.lo-bar__label {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: var(--accent);
  white-space: nowrap;
}

.lo-bar__note {
  color: var(--on-forest-2);
}

.lo-bar__links {
  position: relative;
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

.lo .lo-bar a {
  height: 44px;
  display: flex;
  align-items: center;
  padding: 0 18px;
  text-decoration: none;
  color: var(--paper);
  font-size: 15px;
  font-weight: 600;
  box-sizing: border-box;
}

.lo .lo-bar .lo-bar__edit {
  border: 1.5px solid rgba(243, 237, 224, 0.5);
  border-radius: 10px;
}

/* ---- Desktop ---- */

.lo-main {
  flex-grow: 1;
  padding-top: 48px;
  padding-bottom: 96px;
  display: grid;
  grid-template-columns: 440px minmax(0, 1fr);
  gap: 64px;
  align-items: start;
}

.lo-left {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.lo-cover {
  height: 340px;
  border-radius: 20px;
  position: relative;
  overflow: hidden;
}

.lo-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.lo-cover__count {
  position: absolute;
  right: 14px;
  bottom: 14px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(18, 20, 16, 0.75);
  color: var(--paper);
}

.lo-summary {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.lo-title {
  margin: 0;
  font-size: 44px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.04em;
  overflow-wrap: anywhere;
}

.lo-price {
  font-size: 52px;
  font-weight: 800;
  letter-spacing: -0.045em;
  line-height: 1;
}

.lo-receive {
  font-size: 15px;
  color: var(--released);
  font-weight: 600;
}

.lo-meta {
  font-size: 15px;
  color: var(--muted);
}

.lo-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  background: var(--paper-deep);
  border-radius: 14px;
}

.lo-stat {
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.lo-stat + .lo-stat {
  border-left: 1px solid rgba(18, 20, 16, 0.12);
}

.lo-stat__k {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.12em;
  color: var(--muted);
}

.lo-stat__k--amber {
  color: var(--amber-ink);
}

.lo-stat__v {
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.lo-desc {
  border-top: 2px solid var(--ink);
  padding-top: 16px;
}

.lo-desc summary {
  list-style: none;
  cursor: pointer;
  min-height: 44px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 20px;
  font-weight: 700;
}

.lo-desc summary::-webkit-details-marker {
  display: none;
}

.lo-desc__sign {
  font-family: var(--font-mono);
  font-weight: 400;
}

.lo-desc__sign::before {
  content: '+';
}

.lo-desc[open] .lo-desc__sign::before {
  content: '−';
}

.lo-desc p {
  margin: 8px 0 0;
  font-size: 16px;
  line-height: 1.6;
  color: var(--ink-2);
  white-space: pre-line;
  overflow-wrap: anywhere;
}

.lo-offers {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.lo-offers__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  padding-bottom: 16px;
  border-bottom: 2px solid var(--ink);
}

.lo-offers__h {
  margin: 0;
  font-size: 56px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.lo-offers__n {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 400;
  color: var(--amber-ink);
}

.lo-offers__sub {
  font-size: 15px;
  color: var(--muted);
}

.lo-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.lo-none {
  border: 1.5px dashed rgba(18, 20, 16, 0.3);
  border-radius: 18px;
  padding: 48px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.lo-none__h {
  font-size: 30px;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.lo-none__p {
  font-size: 17px;
  line-height: 1.55;
  color: var(--ink-2);
  max-width: 560px;
}

.lo-questions {
  margin-top: 40px;
}

.lo-questions-m {
  margin-top: 28px;
}

.lo-tip {
  background: var(--paper-deep);
  border-radius: 18px;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  font-size: 15px;
  line-height: 1.55;
  color: var(--ink-2);
}

.lo-tip__h {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: var(--amber-ink);
}

.lo-error {
  margin: 0;
  font-size: 15px;
  color: #a3361f;
}

.lo-foot {
  margin: 8px 0 0;
  font-size: 14px;
  line-height: 1.5;
  color: var(--muted);
}

/* ---- Mobile ---- */

.lo-mhead {
  background: var(--forest);
  color: var(--paper);
  padding: 8px 12px 24px 8px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  position: relative;
  overflow: hidden;
}

.lo-mhead__g {
  width: 380px;
  height: 380px;
  right: -200px;
  top: -200px;
  background: repeating-radial-gradient(circle at 50% 50%, rgba(243, 237, 224, 0) 0 8px, rgba(243, 237, 224, 0.1) 8px 9px);
}

.lo-mhead__top {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.lo .lo-mhead a {
  color: var(--paper);
  text-decoration: none;
}

.lo-mhead__back {
  font-size: 15px;
  font-weight: 600;
  min-height: 44px;
  display: flex;
  align-items: center;
  padding: 0 8px;
  white-space: pre;
}

.lo .lo-mhead .lo-mhead__edit {
  height: 40px;
  display: flex;
  align-items: center;
  padding: 0 14px;
  border: 1.5px solid rgba(243, 237, 224, 0.5);
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  position: relative;
}

.lo-mhead__edit::after {
  content: '';
  position: absolute;
  inset: -3px 0;
}

.lo-mhead__item {
  position: relative;
  display: flex;
  gap: 14px;
  align-items: center;
  padding-left: 8px;
}

.lo-mhead__thumb {
  width: 76px;
  height: 76px;
  border-radius: 12px;
  flex-shrink: 0;
  overflow: hidden;
}

.lo-mhead__thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.lo-mhead__text {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.lo-mhead__title {
  font-size: 19px;
  font-weight: 700;
  line-height: 1.15;
}

.lo-mhead__price {
  font-size: 24px;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.lo-stats--m {
  border-radius: 0;
}

.lo-stats--m .lo-stat {
  padding: 14px 16px;
  gap: 2px;
}

.lo-stats--m .lo-stat__k {
  font-size: 9px;
  letter-spacing: 0.1em;
}

.lo-stats--m .lo-stat__v {
  font-size: 24px;
  letter-spacing: 0;
}

.lo-stats--m .lo-stat__v--best {
  font-size: 20px;
}

.lo-mmain {
  flex-grow: 1;
  padding: 28px 20px 40px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.lo-mh1 {
  margin: 0;
  font-size: 38px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.04em;
  padding-bottom: 12px;
  border-bottom: 2px solid var(--ink);
}

.lo-none--m {
  border-radius: 16px;
  padding: 24px 20px;
  gap: 8px;
}

.lo-none--m .lo-none__h {
  font-size: 24px;
}

.lo-none--m .lo-none__p {
  font-size: 15px;
}

.lo :is(button, a, summary):focus-visible {
  outline: 2px solid var(--ink);
  outline-offset: 2px;
  box-shadow: 0 0 0 5px rgba(245, 184, 46, 0.45);
}

.lo .on-dark :is(a, button):focus-visible {
  outline-color: var(--accent);
  box-shadow: none;
}

@media (max-width: 1279px) {
  .lo-main {
    grid-template-columns: 360px minmax(0, 1fr);
    gap: 40px;
  }

  .lo-offers__h {
    font-size: 44px;
  }
}
</style>
