<script setup>
import { computed, onBeforeUnmount, onMounted, ref, useTemplateRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { applyHead } from '@/router/head'
import { CONDITIONS } from '@/config/listing'
import { stateLabel } from '@/config/states'
import { monthYear, naira, relativeTime } from '@/utils/format'
import { timeLeft } from '@/utils/offers'
import { clock } from '@/utils/deals'
import { useIsMobile } from '@/composables/useMediaQuery'
import AppHeader from '@/components/account/AppHeader.vue'
import StatusPill from '@/components/account/StatusPill.vue'
import UserAvatar from '@/components/account/UserAvatar.vue'
import ListingGallery from '@/components/listing/ListingGallery.vue'
import ListingCarousel from '@/components/listing/ListingCarousel.vue'
import OfferDialog from '@/components/listing/OfferDialog.vue'
import PayFlow from '@/components/listing/PayFlow.vue'
import ListingQuestions from '@/components/questions/ListingQuestions.vue'
import QuestionsHowTo from '@/components/questions/QuestionsHowTo.vue'
import ListingOwnerView from './ListingOwnerView.vue'
import '@/styles/account.css'

// /listings/:id. One route for everyone: the owner gets ListingOwnerView
// (unless previewing with ?as=buyer), everyone else the buyer page from
// design/detail-buyer-*.reference.html, plus the payment states from
// design/pay-7-someone-* (another buyer is paying) and pay-8-accepted-* (the
// viewer's accepted offer: first to pay gets it).
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const isMobile = useIsMobile()

const listing = ref(null)
const notFound = ref(false)
const loadError = ref(false)
const offerOpen = ref(false)
const buyOpen = ref(false)
const withdrawing = ref(false)
const withdrawError = ref('')

const id = computed(() => route.params.id)

async function load() {
  const res = await api(`/listings/${id.value}/`)
  if (res.ok) {
    listing.value = res.data
    loadError.value = notFound.value = false
    applyHead({ title: res.data.title })
  } else if (res.status === 404) {
    notFound.value = true
    applyHead({ title: 'Page not found' })
  } else {
    loadError.value = true
  }
}

onMounted(() => {
  auth.ensureLoaded()
  load()
})
watch(id, () => {
  listing.value = null
  load()
})

const asOwner = computed(() => listing.value?.viewer.is_owner && route.query.as !== 'buyer')

// ---- What the page shows ----

const viewer = computed(() => listing.value.viewer)
const myOffer = computed(() => viewer.value.my_open_offer)
const seller = computed(() => listing.value.seller)
const sellerName = computed(() => `${seller.value.first_name} ${seller.value.last_initial}.`)
const condition = computed(() => CONDITIONS.find((c) => c.key === listing.value.condition) || { label: '', meaning: '' })
const place = computed(() => [listing.value.area, stateLabel(listing.value.state)].filter(Boolean).join(', '))
const posted = computed(() => relativeTime(listing.value.created_at))
const listingNo = computed(() => `BS-L-${String(listing.value.id).padStart(6, '0')}`)
const price = computed(() => naira(listing.value.price))
const offerLeft = computed(() => (myOffer.value ? timeLeft(myOffer.value.expires_at) : ''))
// After a decline (final): "Your ₦140,000 offer wasn’t accepted." Never a reason.
const declinedLine = computed(() =>
  viewer.value.declined_amount ? `Your ${naira(viewer.value.declined_amount)} offer wasn’t accepted.` : '',
)
const limitLine = computed(() =>
  viewer.value.offer_reason === 'offer_limit'
    ? `You’ve made ${listing.value.offer_rules.max_offers} offers on this item. You can still Buy now.`
    : '',
)
// OFFER ACCEPTED · FIRST TO PAY GETS IT: the price held for this buyer.
const accepted = computed(() => viewer.value.accepted_offer)
const heldUntil = computed(() => (accepted.value ? clock(accepted.value.price_held_until) : ''))
// Someone else's 30-minute transfer window.
const paying = computed(() => !!viewer.value.held_until)
const now = ref(Date.now())
const freeInMinutes = computed(() =>
  paying.value ? Math.max(1, Math.ceil((new Date(viewer.value.held_until) - now.value) / 60000)) : 0,
)
const pillLabel = computed(() => {
  if (!paying.value) return ''
  return isMobile.value ? 'SOMEONE IS PAYING' : 'LIVE · SOMEONE IS PAYING'
})
const setupLine = computed(() => (viewer.value.buy_reason === 'no_payout' ? 'The seller hasn’t finished setup yet.' : ''))

// While someone is paying: count the minutes down, and look again when the
// hold should be over (their payment went through, or the item is free).
let clockTimer = null
let freeTimer = null
watch(
  () => listing.value?.viewer?.held_until,
  (until) => {
    clearInterval(clockTimer)
    clearTimeout(freeTimer)
    if (!until) return
    now.value = Date.now()
    clockTimer = setInterval(() => (now.value = Date.now()), 30_000)
    freeTimer = setTimeout(load, Math.max(0, new Date(until) - Date.now()) + 2000)
  },
)
onBeforeUnmount(() => {
  clearInterval(clockTimer)
  clearTimeout(freeTimer)
})

// ---- Actions ----

function needsLogin() {
  if (auth.user) return false
  router.push({ path: '/login', query: { redirect: `/listings/${id.value}` } })
  return true
}

function openOffer() {
  if (!needsLogin()) offerOpen.value = true
}

// Buy now, or Pay for the accepted offer. Also resumes the viewer's own
// transfer if they closed the pay screen while it was running.
const payOffer = ref(null)
function openBuy() {
  if (needsLogin()) return
  payOffer.value = null
  buyOpen.value = true
}
function openPayOffer() {
  if (needsLogin()) return
  payOffer.value = { id: accepted.value.id, amount: accepted.value.amount }
  buyOpen.value = true
}

function onOfferSent(offer) {
  offerOpen.value = false
  listing.value.viewer = { ...viewer.value, my_open_offer: offer, can_offer: false, offer_reason: 'offer_open' }
}

async function withdraw() {
  withdrawing.value = true
  withdrawError.value = ''
  const res = await api(`/offers/${myOffer.value.id}/withdraw/`, { method: 'POST' })
  withdrawing.value = false
  if (res.ok || res.status === 409) await load()
  if (!res.ok && res.status !== 409) withdrawError.value = 'Something went wrong. Please try again.'
}

async function share() {
  const url = window.location.href.split('?')[0]
  try {
    if (navigator.share) await navigator.share({ title: listing.value.title, url })
    else await navigator.clipboard.writeText(url)
  } catch {
    // dismissed, or clipboard unavailable
  }
}

// "Ask Tolu a question": the public Q&A on this page (buyers can't message
// a seller before paying).
const questions = useTemplateRef('questions')
const askSeller = () => questions.value?.focusAsk()
</script>

<template>
  <ListingOwnerView v-if="listing && asOwner" :listing="listing" @changed="load" />

  <div v-else class="acct ld" :class="{ 'ld--m': isMobile }">
    <!-- Signed in, every size uses the app header; signed out on mobile keeps
         the listing's own bar (detail-buyer-1-page-mobile). -->
    <AppHeader v-if="!isMobile || auth.user" section="/listings" />
    <header v-else class="ld-mhead on-dark">
      <RouterLink to="/listings" class="ld-mhead__back">←  Results</RouterLink>
      <RouterLink to="/" class="ld-mhead__mark">buysafe<span>.</span></RouterLink>
      <button type="button" class="ld-mhead__share" @click="share">Share</button>
    </header>

    <main v-if="notFound || loadError" id="main" class="acct-wrap ld-empty">
      <h1 class="ld-empty__h">{{ notFound ? 'We couldn’t find this item.' : 'Something went wrong.' }}</h1>
      <RouterLink to="/listings" class="acct-btn-outline">←  Back to results</RouterLink>
    </main>

    <!-- ================= Desktop ================= -->
    <template v-else-if="listing && !isMobile">
      <nav aria-label="Breadcrumb" class="acct-wrap ld-crumbs">
        <RouterLink to="/listings" class="ld-crumbs__back">←  Back to results</RouterLink><span aria-hidden="true">/</span>
        <span>{{ listing.category.label }}</span><template v-if="listing.state"><span aria-hidden="true">/</span><span>{{ stateLabel(listing.state) }}</span></template>
      </nav>

      <main id="main" class="acct-wrap ld-main">
        <div class="ld-left">
          <ListingGallery :photos="listing.photos" :title="listing.title" />

          <section class="ld-about">
            <h2 class="ld-h2">About this item</h2>
            <p class="ld-about__text">{{ listing.description }}</p>
          </section>

          <section class="ld-details num">
            <h2 class="ld-h2 ld-details__h">Details</h2>
            <div class="ld-row"><span class="ld-row__k">CONDITION</span><span><strong>{{ condition.label }}</strong> · {{ condition.meaning }}</span></div>
            <div class="ld-row"><span class="ld-row__k">CATEGORY</span><span>{{ listing.category.label }}</span></div>
            <div class="ld-row"><span class="ld-row__k">LOCATION</span><span>{{ place }} <span class="ld-muted">· exact spot agreed in chat</span></span></div>
            <div class="ld-row"><span class="ld-row__k">POSTED</span><span>{{ posted }}</span></div>
            <div class="ld-row"><span class="ld-row__k">LISTING NO.</span><span class="ld-mono">{{ listingNo }}</span></div>
          </section>

          <ListingQuestions ref="questions" :listing="listing" />

          <section class="ld-meet">
            <span class="ld-meet__h">Before you meet</span>
            <div class="ld-meet__grid">
              <span><strong>Meet in public</strong> or bring someone along.</span>
              <span><strong>Test it there.</strong> Switch it on, open every door.</span>
              <span><strong>Only confirm</strong> once it’s in your hands.</span>
            </div>
          </section>
        </div>

        <aside class="ld-aside">
          <div class="ld-top">
            <StatusPill
              :status="paying ? 'paying' : listing.display_status"
              :detail="`${condition.label} condition`"
              :label="pillLabel"
              class="ld-pill"
            />
            <h1 class="ld-title">{{ listing.title }}</h1>
            <span class="ld-price num">{{ price }}</span>
            <span class="ld-meta">{{ place }} · Posted {{ posted }}</span>
          </div>

          <div v-if="accepted" class="ld-accepted">
            <span class="ld-accepted__label">OFFER ACCEPTED · FIRST TO PAY GETS IT</span>
            <span class="ld-accepted__amt num">{{ naira(accepted.amount) }}</span>
            <span class="ld-accepted__text">{{ seller.first_name }} accepted your offer. The price is held for you until <strong class="num">{{ heldUntil }}</strong>. Anyone else can still buy at full price, so pay soon.</span>
            <button type="button" class="ld-accepted__pay num" :disabled="!viewer.can_buy" @click="openPayOffer">Pay {{ naira(accepted.amount) }} into escrow</button>
          </div>
          <div v-else-if="myOffer" class="ld-offer">
            <div class="ld-offer__top">
              <span class="ld-offer__label">YOUR OFFER · WAITING FOR {{ seller.first_name.toUpperCase() }}</span>
              <span class="ld-offer__left num">EXPIRES IN {{ offerLeft }}</span>
            </div>
            <span class="ld-offer__amt num">{{ naira(myOffer.amount) }}</span>
            <span class="ld-offer__text">We’ll text you when {{ seller.first_name }} replies. If accepted, you’ll have 24 hours to pay into escrow.</span>
            <button type="button" class="ld-offer__withdraw" :disabled="withdrawing" @click="withdraw">Withdraw offer</button>
            <span v-if="withdrawError" class="ld-error" role="alert">{{ withdrawError }}</span>
          </div>
          <p v-else-if="declinedLine || limitLine" class="ld-note">
            {{ declinedLine }}<template v-if="declinedLine && limitLine"> </template>{{ limitLine }}
          </p>

          <div class="ld-actions">
            <template v-if="!accepted">
              <button type="button" class="ld-buy num" :class="{ 'ld-held': paying }" :disabled="!viewer.can_buy" @click="openBuy">Buy now · {{ price }}</button>
              <button v-if="!myOffer" type="button" class="ld-make" :class="{ 'ld-held': paying }" :disabled="!viewer.can_offer" @click="openOffer">Make an offer</button>
            </template>
            <div v-if="paying" role="status" class="ld-paying">
              <span class="ld-paying__dot" aria-hidden="true"></span>
              <span class="ld-paying__text">
                <span class="ld-paying__h">Someone is paying for this now.</span>
                <span class="ld-paying__p num">If their transfer doesn’t arrive, it’s available again in about {{ freeInMinutes }} min. We’ll notify you.</span>
              </span>
            </div>
            <p v-else-if="setupLine" class="ld-note">{{ setupLine }}</p>
            <a v-if="!paying" href="#questions" class="ld-ask" @click.prevent="askSeller">Ask {{ seller.first_name }} a question</a>
          </div>

          <div class="ld-how perf">
            <div class="ld-how__head"><span>HOW YOU PAY</span><span>ESCROW</span></div>
            <div class="dash"></div>
            <div class="ld-how__step"><span class="ld-how__n">1</span><span>You pay. <span class="ld-muted">buysafe holds the money, not {{ seller.first_name }}.</span></span></div>
            <div class="ld-how__step"><span class="ld-how__n">2</span><span>You meet and check it. <span class="ld-muted">Arrange it in chat.</span></span></div>
            <div class="ld-how__step"><span class="ld-how__n">3</span><span>You confirm. <span class="ld-muted">Only then is {{ seller.first_name }} paid. Not happy? Don’t confirm.</span></span></div>
          </div>

          <div class="ld-seller">
            <UserAvatar :first-name="seller.first_name" :last-name="seller.last_initial" :color="seller.avatar_color" :size="56" :font-size="20" />
            <div class="ld-seller__text">
              <span class="ld-seller__name">{{ sellerName }}</span>
              <span class="ld-seller__meta">Member since {{ monthYear(seller.member_since, { short: true }) }} · {{ seller.sold_count }} sold</span>
            </div>
            <span class="ld-stamp">VERIFIED</span>
          </div>

          <QuestionsHowTo :seller-name="seller.first_name" />
        </aside>
      </main>
    </template>

    <!-- ================= Mobile ================= -->
    <template v-else-if="listing">
      <ListingCarousel :photos="listing.photos" :title="listing.title" />

      <main id="main" class="ld-mmain">
        <div class="ld-top ld-top--m">
          <StatusPill
            :status="paying ? 'paying' : listing.display_status"
            :detail="`${condition.label} condition`"
            :label="pillLabel"
            medium
            class="ld-pill"
          />
          <h1 class="ld-title">{{ listing.title }}</h1>
          <span class="ld-price num">{{ price }}</span>
          <span class="ld-meta">{{ place }} · Posted {{ posted }}</span>
        </div>

        <div v-if="paying" role="status" class="ld-paying ld-paying--m">
          <span class="ld-paying__dot" aria-hidden="true"></span>
          <span class="ld-paying__text">
            <span class="ld-paying__h">Someone is paying for this now.</span>
            <span class="ld-paying__p">If it doesn’t go through, it’s available again in about {{ freeInMinutes }} min.</span>
          </span>
        </div>
        <p v-else-if="setupLine" class="ld-note">{{ setupLine }}</p>

        <div v-if="accepted" class="ld-accepted ld-accepted--m">
          <span class="ld-accepted__label">OFFER ACCEPTED · FIRST TO PAY GETS IT</span>
          <span class="ld-accepted__amt num">{{ naira(accepted.amount) }}</span>
          <span class="ld-accepted__text num">Price held for you until <strong>{{ heldUntil }}</strong>. Others can still pay full price.</span>
        </div>
        <div v-else-if="myOffer" class="ld-offer ld-offer--m">
          <span class="ld-offer__label">YOUR OFFER · WAITING FOR {{ seller.first_name.toUpperCase() }} · {{ offerLeft }} LEFT</span>
          <span class="ld-offer__amt num">{{ naira(myOffer.amount) }}</span>
          <button type="button" class="ld-offer__withdraw" :disabled="withdrawing" @click="withdraw">Withdraw offer</button>
          <span v-if="withdrawError" class="ld-error" role="alert">{{ withdrawError }}</span>
        </div>
        <p v-else-if="declinedLine || limitLine" class="ld-note">
          {{ declinedLine }}<template v-if="declinedLine && limitLine"> </template>{{ limitLine }}
        </p>

        <div class="ld-seller ld-seller--m">
          <UserAvatar :first-name="seller.first_name" :last-name="seller.last_initial" :color="seller.avatar_color" :size="48" :font-size="17" />
          <div class="ld-seller__text">
            <span class="ld-seller__name">{{ sellerName }}</span>
            <span class="ld-seller__meta">Since {{ monthYear(seller.member_since, { short: true }) }} · {{ seller.sold_count }} sold</span>
          </div>
          <span class="ld-stamp">VERIFIED</span>
        </div>

        <section class="ld-about">
          <h2 class="ld-h2">About this item</h2>
          <p class="ld-about__text">{{ listing.description }}</p>
        </section>

        <section class="ld-details num">
          <h2 class="ld-h2 ld-details__h">Details</h2>
          <div class="ld-row"><span class="ld-row__k">CONDITION</span><span><strong>{{ condition.label }}</strong></span></div>
          <div class="ld-row"><span class="ld-row__k">CATEGORY</span><span>{{ listing.category.label }}</span></div>
          <div class="ld-row"><span class="ld-row__k">LOCATION</span><span>{{ place }}</span></div>
          <div class="ld-row"><span class="ld-row__k">LISTING NO.</span><span class="ld-mono">{{ listingNo }}</span></div>
        </section>

        <ListingQuestions ref="questions" :listing="listing" compact />

        <section class="ld-how-m">
          <span class="ld-how-m__label">HOW YOU PAY</span>
          <span class="ld-how-m__text"><strong>1</strong> You pay, buysafe holds it. <strong>2</strong> Meet and check. <strong>3</strong> Confirm, and only then is {{ seller.first_name }} paid.</span>
        </section>
        <a href="#questions" class="ld-ask" @click.prevent="askSeller">Ask {{ seller.first_name }} a question</a>
      </main>

      <div class="ld-bar" :class="{ 'ld-bar--one': myOffer || accepted || paying }">
        <button v-if="accepted" type="button" class="ld-bar__buy num" :disabled="!viewer.can_buy" @click="openPayOffer">
          Pay {{ naira(accepted.amount) }} into escrow
        </button>
        <template v-else>
          <button v-if="!myOffer && !paying" type="button" class="ld-bar__offer" :disabled="!viewer.can_offer" @click="openOffer">Make offer</button>
          <button type="button" class="ld-bar__buy num" :class="{ 'ld-held': paying }" :disabled="!viewer.can_buy" @click="openBuy">Buy · {{ price }}</button>
        </template>
      </div>
    </template>

    <template v-if="listing">
      <OfferDialog :open="offerOpen" :sheet="isMobile" :listing="listing" @close="offerOpen = false" @sent="onOfferSent" />
      <PayFlow
        :open="buyOpen"
        :mobile="isMobile"
        :listing="listing"
        :offer="payOffer"
        :resume-id="viewer.my_payment ? viewer.my_payment.id : null"
        @close="buyOpen = false"
        @changed="load"
      />
    </template>
  </div>
</template>

<style scoped>
.ld {
  background: var(--paper);
}

.ld-muted {
  color: var(--muted);
}

.ld-mono {
  font-family: var(--font-mono);
  font-size: 15px;
}

.dash {
  border-top: 1.5px dashed rgba(18, 20, 16, 0.28);
}

.ld-empty {
  padding-top: 64px;
  padding-bottom: 96px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  align-items: flex-start;
}

.ld-empty__h {
  margin: 0;
  font-size: 40px;
  font-weight: 800;
  letter-spacing: -0.04em;
}

/* ---- Desktop ---- */

.ld-crumbs {
  padding-top: 28px;
  display: flex;
  gap: 10px;
  align-items: center;
  font-size: 15px;
  color: var(--muted);
}

.ld-crumbs__back {
  font-weight: 600;
  text-decoration: none;
  white-space: pre;
}

.ld-main {
  flex-grow: 1;
  padding-top: 28px;
  padding-bottom: 96px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 460px;
  gap: 64px;
  align-items: start;
}

.ld-left {
  display: flex;
  flex-direction: column;
  gap: 48px;
  min-width: 0;
}

.ld-h2 {
  margin: 0;
  font-size: 36px;
  font-weight: 800;
  letter-spacing: -0.03em;
  padding-bottom: 16px;
  border-bottom: 2px solid var(--ink);
}

.ld-about {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.ld-about__text {
  margin: 0;
  font-size: 19px;
  line-height: 1.65;
  color: #2a2c26;
  max-width: 720px;
  white-space: pre-line;
  overflow-wrap: anywhere;
}

.ld-details {
  display: flex;
  flex-direction: column;
}

.ld-details__h {
  margin-bottom: 4px;
}

.ld-row {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 20px;
  padding: 18px 0;
  border-bottom: 1px solid rgba(18, 20, 16, 0.15);
  font-size: 17px;
}

.ld-row__k {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.12em;
  color: var(--muted);
  padding-top: 3px;
}

.ld-meet {
  background: var(--paper-deep);
  border-radius: 16px;
  padding: 28px 32px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ld-meet__h {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.ld-meet__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 24px;
  font-size: 15px;
  line-height: 1.5;
  color: var(--ink-2);
}

.ld-meet__grid strong {
  color: var(--ink);
}

.ld-aside {
  position: sticky;
  top: 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.ld-top {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ld-pill {
  align-self: flex-start;
}

.ld-title {
  margin: 0;
  font-size: 48px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.04em;
  overflow-wrap: anywhere;
}

.ld-price {
  font-size: 64px;
  font-weight: 800;
  letter-spacing: -0.045em;
  line-height: 1;
}

.ld-meta {
  font-size: 16px;
  color: var(--muted);
}

.ld-offer {
  border: 2px solid var(--accent);
  background: rgba(245, 184, 46, 0.14);
  border-radius: 16px;
  padding: 20px 22px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ld-offer__top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.ld-offer__label {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--amber-ink);
}

.ld-offer__left {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--muted);
  white-space: nowrap;
}

.ld-offer__amt {
  font-size: 36px;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.ld-offer__text {
  font-size: 14px;
  line-height: 1.5;
  color: var(--ink-2);
}

.ld-offer__withdraw {
  align-self: flex-start;
  background: transparent;
  border: 0;
  padding: 0;
  min-height: 44px;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  color: #a3361f;
  text-decoration: underline;
  cursor: pointer;
}

/* Decline / limit line: the quiet mono style used for ON HOLD. */
.ld-note {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.5;
  color: var(--muted);
}

.ld-error {
  font-size: 14px;
  color: #a3361f;
}

.ld-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ld-buy,
.ld-make,
.ld-bar button {
  font-family: var(--font-display);
  font-weight: 700;
  cursor: pointer;
}

.ld-buy {
  height: 62px;
  border: 0;
  background: var(--forest);
  color: var(--paper);
  border-radius: 14px;
  font-size: 19px;
}

.ld-make {
  height: 58px;
  border: 1.5px solid var(--ink);
  background: transparent;
  color: var(--ink);
  border-radius: 14px;
  font-size: 18px;
}

.ld :is(.ld-buy, .ld-make, .ld-bar button):disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* Someone else is paying: the greyed buttons from design/pay-7-someone-*. */
.ld .ld-buy.ld-held:disabled,
.ld .ld-bar__buy.ld-held:disabled {
  opacity: 1;
  background: #d8d0be;
  color: #6e7068;
}

.ld .ld-make.ld-held:disabled {
  opacity: 1;
  border-color: rgba(18, 20, 16, 0.2);
  color: #8c8e85;
}

.ld-paying {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 14px 16px;
  background: var(--paper-deep);
  border-radius: 12px;
}

.ld-paying__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--accent);
  margin-top: 6px;
  flex-shrink: 0;
  box-shadow: 0 0 0 4px rgba(245, 184, 46, 0.3);
}

.ld-paying__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ld-paying__h {
  font-size: 16px;
  font-weight: 700;
}

.ld-paying__p {
  font-size: 14px;
  color: var(--ink-2);
}

.ld-paying--m {
  gap: 10px;
  padding: 14px;
}

.ld-paying--m .ld-paying__dot {
  width: 9px;
  height: 9px;
  box-shadow: none;
}

.ld-paying--m .ld-paying__h {
  font-size: 15px;
}

.ld-paying--m .ld-paying__p {
  font-size: 13px;
}

/* The buyer's accepted offer (design/pay-8-accepted-*). */
.ld-accepted {
  border: 2px solid var(--accent);
  background: rgba(245, 184, 46, 0.14);
  border-radius: 16px;
  padding: 20px 22px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ld-accepted__label {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--amber-ink);
}

.ld-accepted__amt {
  font-size: 38px;
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1;
}

.ld-accepted__text {
  font-size: 15px;
  line-height: 1.5;
  color: var(--ink-2);
}

.ld-accepted__text strong {
  color: var(--ink);
}

.ld-accepted__pay {
  height: 58px;
  border: 0;
  border-radius: 14px;
  background: var(--forest);
  color: var(--paper);
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  margin-top: 4px;
  cursor: pointer;
}

.ld-accepted__pay:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.ld-accepted--m {
  border-radius: 14px;
  padding: 14px 16px;
  gap: 4px;
}

.ld-accepted--m .ld-accepted__label {
  font-size: 10px;
  letter-spacing: 0.1em;
}

.ld-accepted--m .ld-accepted__amt {
  font-size: 28px;
  line-height: normal;
}

.ld-accepted--m .ld-accepted__text {
  font-size: 13px;
  line-height: 1.45;
}

.ld-ask {
  align-self: center;
  min-height: 44px;
  display: flex;
  align-items: center;
  font-size: 15px;
  font-weight: 600;
}

.ld-how {
  background: var(--paper);
  border: 1.5px solid rgba(18, 20, 16, 0.12);
  border-bottom: 0;
  padding: 22px 24px 28px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.perf {
  position: relative;
}

.perf::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -10px;
  height: 20px;
  background: radial-gradient(circle at 10px 0, transparent 9px, var(--paper) 10px) 0 0 / 20px 20px repeat-x;
}

.ld-how__head {
  display: flex;
  justify-content: space-between;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--muted);
}

.ld-how__step {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  font-size: 15px;
  line-height: 1.45;
}

.ld-how__n {
  font-family: var(--font-serif);
  font-size: 26px;
  line-height: 0.9;
  color: var(--amber-ink);
  width: 26px;
}

.ld-seller {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 0;
  border-top: 1px solid rgba(18, 20, 16, 0.15);
  border-bottom: 1px solid rgba(18, 20, 16, 0.15);
}

.ld-seller__text {
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex-grow: 1;
}

.ld-seller__name {
  font-size: 18px;
  font-weight: 700;
}

.ld-seller__meta {
  font-size: 14px;
  color: var(--muted);
}

.ld-stamp {
  transform: rotate(-5deg);
  border: 2px solid var(--released);
  outline: 1px solid var(--released);
  outline-offset: 2px;
  color: var(--released);
  font-family: var(--font-mono);
  font-weight: 600;
  font-size: 10px;
  letter-spacing: 0.12em;
  padding: 3px 7px;
  border-radius: 3px;
}

/* ---- Mobile ---- */

.ld-mhead {
  background: var(--forest);
  color: var(--paper);
  height: 64px;
  padding: 0 12px 0 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.ld .ld-mhead a {
  color: var(--paper);
  text-decoration: none;
}

.ld-mhead__back {
  font-size: 15px;
  font-weight: 600;
  min-height: 44px;
  min-width: 44px;
  display: flex;
  align-items: center;
  padding: 0 8px;
  white-space: pre;
}

/* Centred in the bar whatever sits on the right (bell or not). */
.ld-mhead {
  position: relative;
}

.ld-mhead__mark {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.ld-mhead__mark span {
  color: var(--accent);
}

.ld-mhead__share {
  height: 44px;
  padding: 0 12px;
  background: transparent;
  border: 1.5px solid rgba(243, 237, 224, 0.35);
  border-radius: 10px;
  color: var(--paper);
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

/* Bottom padding keeps content clear of the fixed action bar. */
.ld-mmain {
  flex-grow: 1;
  padding: 24px 20px calc(150px + env(safe-area-inset-bottom, 0px));
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.ld-top--m {
  gap: 10px;
}

.ld--m .ld-title {
  font-size: 34px;
  line-height: 1.02;
}

.ld--m .ld-price {
  font-size: 44px;
}

.ld--m .ld-meta {
  font-size: 14px;
}

.ld-offer--m {
  border-radius: 14px;
  padding: 16px;
  gap: 6px;
}

.ld-offer--m .ld-offer__label {
  font-size: 10px;
}

.ld-offer--m .ld-offer__amt {
  font-size: 30px;
}

.ld-seller--m {
  gap: 14px;
  padding: 16px 0;
}

.ld-seller--m .ld-seller__text {
  gap: 2px;
}

.ld-seller--m .ld-seller__name {
  font-size: 17px;
}

.ld-seller--m .ld-seller__meta {
  font-size: 13px;
}

.ld-seller--m .ld-stamp {
  outline: 0;
  font-size: 9px;
  padding: 3px 6px;
}

.ld--m .ld-about {
  gap: 12px;
}

.ld--m .ld-about .ld-h2 {
  font-size: 24px;
  letter-spacing: -0.02em;
  padding-bottom: 0;
  border-bottom: 0;
}

.ld--m .ld-about__text {
  font-size: 17px;
  line-height: 1.6;
}

.ld--m .ld-details__h {
  font-size: 24px;
  letter-spacing: -0.02em;
  padding-bottom: 12px;
}

.ld--m .ld-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 0;
  font-size: 15px;
}

.ld--m .ld-row__k {
  font-size: 11px;
  letter-spacing: 0.1em;
  padding-top: 0;
}

.ld--m .ld-mono {
  font-size: 13px;
}

.ld-how-m {
  background: var(--paper-deep);
  border-radius: 14px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ld-how-m__label {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--amber-ink);
}

.ld-how-m__text {
  font-size: 15px;
  line-height: 1.5;
}

.ld-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 40;
  background: var(--paper);
  border-top: 1px solid rgba(18, 20, 16, 0.15);
  padding: 12px 16px calc(22px + env(safe-area-inset-bottom, 0px));
  display: grid;
  grid-template-columns: 1fr 1.3fr;
  gap: 10px;
  box-shadow: 0 -10px 30px rgba(18, 20, 16, 0.08);
}

.ld-bar--one {
  grid-template-columns: 1fr;
}

.ld-bar__offer {
  height: 56px;
  border: 1.5px solid var(--ink);
  background: transparent;
  color: var(--ink);
  border-radius: 12px;
  font-size: 16px;
}

.ld-bar__buy {
  height: 56px;
  border: 0;
  background: var(--forest);
  color: var(--paper);
  border-radius: 12px;
  font-size: 16px;
}

/* Marigold focus rings on the page's own controls. */
.ld :is(button, a):focus-visible {
  outline: 2px solid var(--ink);
  outline-offset: 2px;
  box-shadow: 0 0 0 5px rgba(245, 184, 46, 0.45);
}

.ld .on-dark :is(a, button):focus-visible {
  outline-color: var(--accent);
  box-shadow: none;
}

@media (max-width: 1279px) {
  .ld-main {
    grid-template-columns: minmax(0, 1fr) 400px;
    gap: 40px;
  }

  .ld-title {
    font-size: 40px;
  }

  .ld-price {
    font-size: 52px;
  }
}
</style>
