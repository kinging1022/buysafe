<script setup>
import { computed, onBeforeUnmount, ref, useTemplateRef, watch } from 'vue'
import { api } from '@/api/http'
import { naira } from '@/utils/format'
import { stateLabel } from '@/config/states'
import { BANK_FEE } from '@/config/payments'
import { clock, groupAccount, mmss, shortTitle } from '@/utils/deals'
import { useModal } from '@/composables/useModal'
import { useAuthStore } from '@/stores/auth'
import ModalPanel from '@/components/ui/ModalPanel.vue'

// Pay into escrow by bank transfer: design/pay-1…6-*. The same flow for Buy
// now and for an accepted offer (`offer`). A dialog on desktop, a full
// screen with its own back bar on mobile.
//
//   summary   step 1: the amount and "Before you pay", then the buyer's email
//             (Anchor needs one on the account); once it's in, the amount and
//             email are shown again above the button that makes the account
//   transfer  step 2: the virtual account, a 30:00 countdown, polled every 5s
//   received  RECEIVED stamp, then Go to the deal
//   expired   30 minutes passed: the hold is released
//   wrong     wrong amount: refunded minus the bank fee
//   late      arrived after someone else paid (or after expiry): full refund
const props = defineProps({
  open: { type: Boolean, required: true },
  mobile: { type: Boolean, default: false },
  listing: { type: Object, required: true },
  offer: { type: Object, default: null }, // { id, amount } while its price is held
  resumeId: { type: Number, default: null }, // the buyer's own transfer in progress
})
const emit = defineEmits(['close', 'changed'])

const POLL_MS = 5000
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const auth = useAuthStore()
const email = ref('')
const emailSet = ref(false) // entered and checked: show it with the amount
const emailError = ref('')

const step = ref('summary')
const intent = ref(null)
const busy = ref(false)
const error = ref('')
const copied = ref('')
const now = ref(Date.now())

const seller = computed(() => `${props.listing.seller.first_name} ${props.listing.seller.last_initial}.`)
const placeLong = computed(() => [props.listing.area, stateLabel(props.listing.state)].filter(Boolean).join(', '))
const photo = computed(() => props.listing.photos?.[0] || props.listing.photo || null)
const item = computed(() => shortTitle(props.listing.title))
const amount = computed(() => intent.value?.amount ?? props.offer?.amount ?? props.listing.price)
const dealNo = computed(() => intent.value?.id)

const remaining = computed(() => (intent.value ? (new Date(intent.value.expires_at) - now.value) / 1000 : 0))
const total = computed(() =>
  intent.value ? (new Date(intent.value.expires_at) - new Date(intent.value.created_at)) / 1000 : 1800,
)
const progress = computed(() => `${Math.max(0, Math.min(100, (remaining.value / total.value) * 100))}%`)
const refund = computed(() => intent.value?.refund)
const received = computed(() => intent.value?.received)

const eyebrow = computed(
  () =>
    ({
      summary: 'STEP 1 OF 2 · CHECK THE AMOUNT',
      transfer: 'STEP 2 OF 2 · BANK TRANSFER',
      received: `DEAL ${dealNo.value} · PAID`,
    })[step.value] || `DEAL ${dealNo.value}`,
)

function stepFor(data) {
  if (data.status === 'awaiting') return 'transfer'
  if (data.status === 'received') return 'received'
  if (data.status === 'refunded' && data.refund?.reason === 'wrong_amount') return 'wrong'
  if (data.status === 'refunded') return 'late'
  if (data.status === 'expired') return 'expired'
  return 'summary' // cancelled
}

function apply(data) {
  const before = step.value
  intent.value = data
  step.value = stepFor(data)
  if (before !== step.value && step.value !== 'transfer') emit('changed')
}

// ---- Polling and the countdown ----

let pollTimer = null
let tickTimer = null
function stopTimers() {
  clearInterval(pollTimer)
  clearInterval(tickTimer)
  clearTimeout(copiedTimer)
  pollTimer = tickTimer = null
}
async function poll() {
  if (!intent.value) return
  const res = await api(`/payments/${intent.value.id}/`)
  if (res.ok) apply(res.data)
}
watch(
  () => props.open && step.value === 'transfer',
  (on) => {
    stopTimers()
    if (!on) return
    now.value = Date.now()
    tickTimer = setInterval(() => {
      now.value = Date.now()
      if (remaining.value <= 0) poll()
    }, 1000)
    pollTimer = setInterval(poll, POLL_MS)
  },
)
onBeforeUnmount(stopTimers)

watch(
  () => props.open,
  async (open) => {
    error.value = ''
    copied.value = ''
    emailError.value = ''
    if (!open) return
    email.value = auth.user?.email || ''
    emailSet.value = Boolean(email.value)
    if (props.resumeId) {
      const res = await api(`/payments/${props.resumeId}/`)
      if (res.ok) return apply(res.data)
    }
    if (!['transfer', 'received'].includes(step.value)) {
      step.value = 'summary'
      intent.value = null
    }
  },
  { immediate: true },
)

// ---- Actions ----

function confirmEmail() {
  const value = email.value.trim()
  if (!EMAIL_RE.test(value)) {
    emailError.value = 'Enter a valid email address.'
    return
  }
  email.value = value
  emailError.value = ''
  emailSet.value = true
}

async function getDetails() {
  busy.value = true
  error.value = ''
  const res = await api(`/listings/${props.listing.id}/pay/`, {
    method: 'POST',
    body: { email: email.value, ...(props.offer ? { offer_id: props.offer.id } : {}) },
  })
  busy.value = false
  if (res.ok) {
    if (auth.user) auth.user.email = email.value
    apply(res.data)
    emit('changed')
  } else if (['email_required', 'invalid_email'].includes(res.data?.code)) {
    emailSet.value = false
    emailError.value = res.data.detail
  } else {
    error.value = res.data?.detail || 'Something went wrong. Please try again.'
    if (res.status === 409) emit('changed')
  }
}

async function cancelHold() {
  busy.value = true
  const res = await api(`/payments/${intent.value.id}/cancel/`, { method: 'POST' })
  busy.value = false
  if (res.ok || res.status === 409) {
    step.value = 'summary'
    intent.value = null
    emit('changed')
    emit('close')
  } else {
    error.value = 'Something went wrong. Please try again.'
  }
}

function startAgain() {
  intent.value = null
  step.value = 'summary'
}

// The button reads "Copied ✓" for a moment so the buyer knows it worked.
let copiedTimer = null
async function copy(text, what) {
  clearTimeout(copiedTimer)
  try {
    await writeClipboard(text)
    copied.value = what
    copiedTimer = setTimeout(() => (copied.value = ''), 2000)
  } catch {
    copied.value = ''
  }
}
// navigator.clipboard only exists on https/localhost; a phone on the LAN
// (http://192.168…) needs the old execCommand way.
async function writeClipboard(text) {
  if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text)
  const el = document.createElement('textarea')
  el.value = text
  el.setAttribute('readonly', '')
  el.style.cssText = 'position:fixed;opacity:0'
  document.body.appendChild(el)
  el.select()
  const ok = document.execCommand('copy')
  el.remove()
  if (!ok) throw new Error('copy failed')
}

// ---- Mobile: a full screen with its own back bar ----

const screen = useTemplateRef('screen')
const { onKeydown } = useModal(screen, () => props.open && props.mobile, () => emit('close'))
</script>

<template>
  <!-- ================= Desktop dialog ================= -->
  <ModalPanel
    v-if="!mobile"
    :open="open"
    labelledby="pay-title"
    :width="652"
    padding="34px 36px"
    :top="96"
    @close="emit('close')"
  >
    <div class="pd-head">
      <div class="pd-titles">
        <span v-if="step === 'summary'" class="pd-eyebrow">STEP 1 OF 2 · CHECK THE AMOUNT</span>
        <span v-else-if="step === 'transfer'" class="pd-eyebrow">STEP 2 OF 2 · BANK TRANSFER</span>
        <span v-else-if="step === 'received'" class="pd-eyebrow pd-eyebrow--green">PAYMENT RECEIVED</span>
        <span v-else-if="step === 'expired'" class="pd-eyebrow pd-eyebrow--red">HOLD RELEASED</span>
        <span v-else-if="step === 'wrong'" class="pd-eyebrow pd-eyebrow--red">WRONG AMOUNT · REFUNDED</span>
        <span v-else class="pd-eyebrow pd-eyebrow--amber">ARRIVED TOO LATE · REFUNDED</span>
        <h2 id="pay-title" class="pd-h">
          <template v-if="step === 'summary'">Pay into escrow.</template>
          <template v-else-if="step === 'transfer'">Send the transfer.</template>
          <template v-else-if="step === 'received'">Held safely.</template>
          <template v-else-if="step === 'expired'">Time ran out.</template>
          <template v-else-if="step === 'wrong'">That wasn’t the exact amount.</template>
          <template v-else>Someone else paid first.</template>
        </h2>
      </div>
      <button type="button" class="pd-close" aria-label="Close" @click="emit('close')">×</button>
    </div>

    <!-- Step 1 -->
    <div v-if="step === 'summary'" class="pd-body pd-body--20">
      <div class="pd-receipt perf">
        <div class="pd-item">
          <span class="pd-thumb photo"><img v-if="photo" :src="photo" alt="" /></span>
          <span class="pd-item__text">
            <span class="pd-item__title">{{ listing.title }}</span>
            <span class="pd-item__meta">{{ seller }} · {{ placeLong }}</span>
          </span>
        </div>
        <div class="dash"></div>
        <div class="pd-rows num">
          <div class="pd-row">
            <span class="pd-k">Item price</span>
            <strong :class="{ 'pd-struck': offer }">{{ naira(listing.price) }}</strong>
          </div>
          <div v-if="offer" class="pd-row pd-row--amber">
            <span>Accepted offer</span><strong>{{ naira(offer.amount) }}</strong>
          </div>
          <div class="pd-row"><span class="pd-k">Buyer fee</span><strong class="pd-green">₦0</strong></div>
          <div class="dash"></div>
          <div class="pd-row pd-row--total"><strong>You pay</strong><span class="pd-total">{{ naira(amount) }}</span></div>
        </div>
      </div>
      <div class="pd-before">
        <span class="pd-before__h">BEFORE YOU PAY</span>
        <span class="pd-before__p"><span class="pd-before__n">1</span><span>You’ll pay by <strong>bank transfer</strong> to an account made just for this deal. No card, no wallet.</span></span>
        <span class="pd-before__p"><span class="pd-before__n">2</span><span>Refunds always go back to <strong>the account the money came from</strong>.</span></span>
        <span class="pd-before__p"><span class="pd-before__n">3</span><span>If a refund is caused by your mistake (like the wrong amount), <strong>bank fees are deducted</strong>.</span></span>
      </div>
      <template v-if="!emailSet">
        <div class="pd-email">
          <label for="pd-email" class="pd-label">YOUR EMAIL</label>
          <input
            id="pd-email"
            v-model="email"
            type="email"
            inputmode="email"
            autocomplete="email"
            placeholder="you@example.com"
            class="pd-input"
            :aria-invalid="Boolean(emailError)"
            @keydown.enter.prevent="confirmEmail"
          />
          <span class="pd-hint">For your payment receipt and deal updates.</span>
          <p v-if="emailError" class="pd-error pd-error--flush" role="alert">{{ emailError }}</p>
        </div>
        <button type="button" class="pd-btn" @click="confirmEmail">Continue  →</button>
      </template>
      <template v-else>
        <div class="pd-confirm">
          <div class="pd-row num"><span class="pd-k">Amount</span><strong>{{ naira(amount) }}</strong></div>
          <div class="pd-row">
            <span class="pd-k">Email</span>
            <span class="pd-confirm__email"><strong>{{ email }}</strong><button type="button" class="pd-change" @click="emailSet = false">Change</button></span>
          </div>
        </div>
        <button type="button" class="pd-btn" :disabled="busy" @click="getDetails">Get transfer details  →</button>
      </template>
      <p v-if="error" class="pd-error" role="alert">{{ error }}</p>
    </div>

    <!-- Step 2 -->
    <div v-else-if="step === 'transfer'" class="pd-body">
      <div class="pd-card">
        <div class="pd-line">
          <span class="pd-stack"><span class="pd-label">TRANSFER EXACTLY</span><span class="pd-exact num">{{ naira(amount) }}</span></span>
          <button type="button" class="pd-copy" :class="{ 'is-copied': copied === 'amount' }" @click="copy(String(amount), 'amount')">{{ copied === 'amount' ? 'Copied ✓' : 'Copy amount' }}</button>
        </div>
        <div class="dash"></div>
        <div class="pd-line">
          <span class="pd-stack pd-stack--4">
            <span class="pd-label">{{ (intent.account.bank || 'Bank').toUpperCase() }} · ACCOUNT NUMBER</span>
            <span class="pd-acct num">{{ groupAccount(intent.account.number) }}</span>
          </span>
          <button type="button" class="pd-copy-num" :class="{ 'is-copied': copied === 'account number' }" @click="copy(intent.account.number, 'account number')">{{ copied === 'account number' ? 'Copied ✓' : 'Copy number' }}</button>
        </div>
        <span class="pd-stack"><span class="pd-label">ACCOUNT NAME</span><span class="pd-name">{{ intent.account.name }}</span></span>
      </div>
      <div class="pd-wait">
        <div class="pd-wait__top">
          <span class="pd-wait__line"><span class="pd-dot" aria-hidden="true"></span>Waiting for your transfer…</span>
          <span class="pd-timer num" role="timer">{{ mmss(remaining) }}</span>
        </div>
        <div class="pd-bar"><div class="pd-bar__fill" :style="{ width: progress }"></div></div>
        <span class="pd-wait__p">This updates by itself. The {{ item }} is held for you until the timer runs out. Send the exact amount, in one transfer, from any bank app.</span>
      </div>
      <div class="pd-foot">
        <button type="button" class="pd-cancel" :disabled="busy" @click="cancelHold">Cancel and release the hold</button>
      </div>
      <p v-if="error" class="pd-error" role="alert">{{ error }}</p>
      <span class="visually-hidden" aria-live="polite">{{ copied ? `Copied ${copied}` : '' }}</span>
    </div>

    <!-- Received -->
    <div v-else-if="step === 'received'" class="pd-body">
      <div class="pd-receipt pd-receipt--paid perf">
        <span class="pd-label">DEAL {{ dealNo }} · HELD IN ESCROW</span>
        <span class="pd-held num">{{ naira(amount) }}</span>
        <span class="pd-from">From {{ received.bank }} ····{{ received.last4 }} · {{ clock(received.at) }}</span>
        <span class="pd-stamp">RECEIVED</span>
      </div>
      <span class="pd-text">The {{ item }} is yours to check. {{ listing.seller.first_name }} now has <strong>4 hours</strong> to send a live video of it. If not, you’re refunded in full automatically.</span>
      <RouterLink :to="`/deals/${intent.deal_id}`" class="pd-btn pd-btn--link">Go to the deal  →</RouterLink>
    </div>

    <!-- Expired -->
    <div v-else-if="step === 'expired'" class="pd-body">
      <span class="pd-text pd-text--17">30 minutes passed and no transfer arrived, so the {{ item }} is available to other buyers again. If you did send money, it will be refunded to the account it came from automatically.</span>
      <button type="button" class="pd-btn pd-btn--58" @click="startAgain">Start again</button>
    </div>

    <!-- Wrong amount / late -->
    <div v-else class="pd-body">
      <span v-if="step === 'wrong'" class="pd-text pd-text--17">We received {{ naira(refund.received_amount) }} but this deal needs exactly {{ naira(amount) }}. We’ve sent it back to the account it came from, minus the bank fee, and released the hold.</span>
      <span v-else class="pd-text pd-text--17">Your transfer reached us after another buyer’s payment was confirmed. It’s been refunded in full to the account it came from. No fees, since this wasn’t your fault.</span>
      <div class="pd-breakdown num">
        <div class="pd-row"><span class="pd-k">We received</span><strong>{{ naira(refund.received_amount) }}</strong></div>
        <div class="pd-row">
          <span class="pd-k">Bank fee</span>
          <strong v-if="step === 'wrong'" class="pd-amber">− {{ BANK_FEE }}</strong>
          <strong v-else class="pd-green">₦0</strong>
        </div>
        <div class="dash"></div>
        <div class="pd-row pd-row--total">
          <strong>Refunded to {{ refund.bank }} ····{{ refund.last4 }}</strong>
          <span class="pd-refunded">{{ step === 'wrong' ? `${naira(refund.received_amount)} − fee` : naira(refund.amount) }}</span>
        </div>
      </div>
      <button v-if="step === 'wrong'" type="button" class="pd-btn pd-btn--58" @click="startAgain">Start again</button>
      <RouterLink v-else to="/listings" class="pd-btn pd-btn--58 pd-btn--ghost">Browse similar items</RouterLink>
    </div>
  </ModalPanel>

  <!-- ================= Mobile full screen ================= -->
  <Teleport v-else to="body">
    <div v-if="open" ref="screen" class="pm" role="dialog" aria-modal="true" aria-labelledby="pm-title" @keydown="onKeydown">
      <header class="pm-head">
        <button type="button" class="pm-back" aria-label="Back" @click="emit('close')">←</button>
        <span class="pm-head__text">
          <span id="pm-title" class="pm-head__title">Pay into escrow</span>
          <span class="pm-head__sub">{{ eyebrow }}</span>
        </span>
      </header>

      <div class="pm-body">
        <!-- Step 1 -->
        <template v-if="step === 'summary'">
          <div class="pm-card">
            <div class="pm-item">
              <span class="pm-thumb photo"><img v-if="photo" :src="photo" alt="" /></span>
              <span class="pm-item__text">
                <span class="pm-item__title">{{ listing.title }}</span>
                <span class="pm-item__meta">{{ seller }}<template v-if="listing.area"> · {{ listing.area }}</template></span>
              </span>
            </div>
            <div class="dash"></div>
            <div class="pm-rows num">
              <div class="pd-row"><span class="pd-k">Item price</span><strong :class="{ 'pd-struck': offer }">{{ naira(listing.price) }}</strong></div>
              <div v-if="offer" class="pd-row pd-row--amber"><span>Accepted offer</span><strong>{{ naira(offer.amount) }}</strong></div>
              <div class="pd-row"><span class="pd-k">Buyer fee</span><strong class="pd-green">₦0</strong></div>
              <div class="dash"></div>
              <div class="pd-row pd-row--total"><strong>You pay</strong><span class="pm-total">{{ naira(amount) }}</span></div>
            </div>
          </div>
          <div class="pm-before">
            <span class="pm-before__h">BEFORE YOU PAY</span>
            <span><strong>Bank transfer only</strong>, to an account made for this deal.</span>
            <span>Refunds go back to <strong>the account the money came from</strong>.</span>
            <span>If a refund is your mistake (e.g. wrong amount), <strong>bank fees are deducted</strong>.</span>
          </div>
          <template v-if="!emailSet">
            <div class="pd-email">
              <label for="pm-email" class="pm-label">YOUR EMAIL</label>
              <input
                id="pm-email"
                v-model="email"
                type="email"
                inputmode="email"
                autocomplete="email"
                placeholder="you@example.com"
                class="pd-input pm-input"
                :aria-invalid="Boolean(emailError)"
                @keydown.enter.prevent="confirmEmail"
              />
              <span class="pd-hint">For your payment receipt and deal updates.</span>
              <p v-if="emailError" class="pd-error pd-error--flush" role="alert">{{ emailError }}</p>
            </div>
            <button type="button" class="pm-btn" @click="confirmEmail">Continue  →</button>
          </template>
          <template v-else>
            <div class="pd-confirm pm-confirm">
              <div class="pd-row num"><span class="pd-k">Amount</span><strong>{{ naira(amount) }}</strong></div>
              <div class="pd-row">
                <span class="pd-k">Email</span>
                <span class="pd-confirm__email"><strong>{{ email }}</strong><button type="button" class="pd-change" @click="emailSet = false">Change</button></span>
              </div>
            </div>
            <p v-if="error" class="pd-error" role="alert">{{ error }}</p>
            <button type="button" class="pm-btn" :disabled="busy" @click="getDetails">Get transfer details  →</button>
          </template>
        </template>

        <!-- Step 2 -->
        <template v-else-if="step === 'transfer'">
          <div class="pm-card pm-card--transfer">
            <span class="pd-stack">
              <span class="pm-label">TRANSFER EXACTLY</span>
              <span class="pm-line">
                <span class="pm-exact num">{{ naira(amount) }}</span>
                <button type="button" class="pm-copy" :class="{ 'is-copied': copied === 'amount' }" @click="copy(String(amount), 'amount')">{{ copied === 'amount' ? 'Copied ✓' : 'Copy' }}</button>
              </span>
            </span>
            <div class="dash"></div>
            <span class="pd-stack pd-stack--4">
              <span class="pm-label">{{ (intent.account.bank || 'Bank').toUpperCase() }} · ACCOUNT NUMBER</span>
              <span class="pm-acct num">{{ groupAccount(intent.account.number) }}</span>
            </span>
            <button type="button" class="pm-copy-num" :class="{ 'is-copied': copied === 'account number' }" @click="copy(intent.account.number, 'account number')">{{ copied === 'account number' ? 'Copied ✓' : 'Copy account number' }}</button>
            <span class="pd-stack"><span class="pm-label">ACCOUNT NAME</span><span class="pm-name">{{ intent.account.name }}</span></span>
          </div>
          <div class="pd-wait__top">
            <span class="pd-wait__line pm-wait__line"><span class="pd-dot pm-dot" aria-hidden="true"></span>Waiting for your transfer…</span>
            <span class="pd-timer pm-timer num" role="timer">{{ mmss(remaining) }}</span>
          </div>
          <div class="pd-bar"><div class="pd-bar__fill" :style="{ width: progress }"></div></div>
          <span class="pm-wait__p">Updates by itself. The {{ item }} is held for you until the timer ends. Exact amount, one transfer, any bank app.</span>
          <p v-if="error" class="pd-error" role="alert">{{ error }}</p>
          <div class="pm-foot">
            <button type="button" class="pd-cancel" :disabled="busy" @click="cancelHold">Cancel and release the hold</button>
          </div>
          <span class="visually-hidden" aria-live="polite">{{ copied ? `Copied ${copied}` : '' }}</span>
        </template>

        <!-- Received -->
        <template v-else-if="step === 'received'">
          <div class="pm-card pm-card--paid">
            <span class="pm-label">DEAL {{ dealNo }} · HELD IN ESCROW</span>
            <span class="pm-held num">{{ naira(amount) }}</span>
            <span class="pm-from">From {{ received.bank }} ····{{ received.last4 }} · {{ clock(received.at) }}</span>
            <span class="pm-stamp">RECEIVED</span>
          </div>
          <span class="pm-text">{{ listing.seller.first_name }} now has <strong>4 hours</strong> to send a live video of the {{ item }}. If not, you’re refunded in full automatically.</span>
          <RouterLink :to="`/deals/${intent.deal_id}`" class="pm-btn pd-btn--link">Go to the deal  →</RouterLink>
        </template>

        <!-- Expired / wrong / late -->
        <template v-else>
          <span v-if="step === 'expired'" class="pm-eyebrow pd-eyebrow--red">HOLD RELEASED</span>
          <span v-else-if="step === 'wrong'" class="pm-eyebrow pd-eyebrow--red">WRONG AMOUNT · REFUNDED</span>
          <span v-else class="pm-eyebrow pd-eyebrow--amber">ARRIVED TOO LATE · REFUNDED</span>
          <h2 class="pm-h">
            <template v-if="step === 'expired'">Time ran out.</template>
            <template v-else-if="step === 'wrong'">That wasn’t the exact amount.</template>
            <template v-else>Someone else paid first.</template>
          </h2>
          <span v-if="step === 'expired'" class="pm-text">30 minutes passed with no transfer, so the {{ item }} is available again. If you did send money, it’s refunded to the account it came from automatically.</span>
          <span v-else-if="step === 'wrong'" class="pm-text">We received {{ naira(refund.received_amount) }}; this deal needs exactly {{ naira(amount) }}. Sent back to the account it came from, minus the bank fee.</span>
          <span v-else class="pm-text">Your transfer arrived after another buyer’s payment. Refunded in full to the account it came from. No fees.</span>
          <div v-if="step !== 'expired'" class="pm-breakdown num">
            <div class="pd-row"><span class="pd-k">We received</span><strong>{{ naira(refund.received_amount) }}</strong></div>
            <div class="pd-row">
              <span class="pd-k">Bank fee</span>
              <strong v-if="step === 'wrong'" class="pd-amber">− {{ BANK_FEE }}</strong>
              <strong v-else class="pd-green">₦0</strong>
            </div>
            <div class="dash"></div>
            <div class="pd-row pd-row--total">
              <strong>Refunded to {{ refund.bank }} ····{{ refund.last4 }}</strong>
              <span class="pm-refunded">{{ step === 'wrong' ? `${naira(refund.received_amount)} − fee` : naira(refund.amount) }}</span>
            </div>
          </div>
          <RouterLink v-if="step === 'late'" to="/listings" class="pm-btn pm-btn--ghost">Browse similar items</RouterLink>
          <button v-else type="button" class="pm-btn" @click="startAgain">Start again</button>
        </template>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.photo {
  background-color: #e4dbc6;
  background-image: repeating-linear-gradient(135deg, rgba(18, 20, 16, 0.035) 0 10px, rgba(18, 20, 16, 0) 10px 20px);
  overflow: hidden;
}

.photo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.dash {
  border-top: 1.5px dashed rgba(18, 20, 16, 0.28);
}

/* Perforated bottom edge, cut into the paper behind. */
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

/* ---- Desktop dialog ---- */

.pd-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.pd-titles {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.pd-eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: var(--muted);
}

.pd-eyebrow--green {
  color: var(--released);
}

.pd-eyebrow--red {
  color: #a3361f;
}

.pd-eyebrow--amber {
  color: var(--amber-ink);
}

.pd-h {
  margin: 0;
  font-size: 40px;
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 1;
}

.pd-close {
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 1.5px solid rgba(18, 20, 16, 0.25);
  background: transparent;
  color: var(--ink);
  font-family: var(--font-display);
  font-size: 20px;
  cursor: pointer;
}

.pd-body {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.pd-body--20 {
  gap: 20px;
}

.pd-receipt {
  background: #ffffff;
  padding: 20px 22px 26px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.pd-item {
  display: flex;
  gap: 14px;
  align-items: center;
}

.pd-thumb {
  width: 56px;
  height: 56px;
  border-radius: 10px;
  flex-shrink: 0;
}

.pd-item__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.pd-item__title {
  font-size: 17px;
  font-weight: 700;
}

.pd-item__meta {
  font-size: 14px;
  color: var(--muted);
}

.pd-rows {
  display: flex;
  flex-direction: column;
  gap: 10px;
  font-size: 16px;
}

.pd-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.pd-row strong {
  font-weight: 700;
}

.pd-row--total {
  align-items: baseline;
}

.pd-row--amber span {
  color: var(--amber-ink);
  font-weight: 600;
}

.pd-row--amber strong {
  color: var(--amber-ink);
}

.pd-k {
  color: var(--ink-2);
}

.pd-struck {
  text-decoration: line-through;
  color: #8c8e85;
}

.pd-green {
  color: var(--released);
}

.pd-amber {
  color: var(--amber-ink);
}

.pd-total {
  font-size: 40px;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.pd-before {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px 18px;
  background: var(--paper-deep);
  border-radius: 14px;
}

.pd-before__h,
.pm-before__h {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--amber-ink);
}

.pd-before__p {
  display: grid;
  grid-template-columns: 18px 1fr;
  gap: 8px;
  font-size: 15px;
  line-height: 1.5;
}

.pd-before__n {
  font-weight: 800;
}

.pd-btn {
  height: 60px;
  border: 0;
  border-radius: 14px;
  background: var(--forest);
  color: var(--paper);
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  white-space: pre;
  cursor: pointer;
}

.pd-btn--58 {
  height: 58px;
  font-size: 17px;
}

.pd-btn--link {
  display: flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
}

.mp .pd-btn--link,
.pm .pd-btn--link {
  color: var(--paper);
}

.pd-btn--ghost {
  display: flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  background: transparent;
  color: var(--ink);
}

.mp .pd-btn--ghost {
  color: var(--ink);
}

.pd-btn:disabled,
.pm-btn:disabled {
  opacity: 0.6;
  cursor: progress;
}

.pd-error {
  margin: -6px 0 0;
  font-size: 14px;
  color: #a3361f;
}

.pd-error--flush {
  margin: 0;
}

/* ---- Email, then the amount and email before the button ---- */

.pd-email {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pd-input {
  height: 56px;
  padding: 0 16px;
  background: #ffffff;
  border: 2px solid var(--ink);
  border-radius: 14px;
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 600;
  color: var(--ink);
  outline: none;
}

.pd-input:focus-visible {
  box-shadow: 0 0 0 4px rgba(245, 184, 46, 0.45);
}

.pd-input[aria-invalid='true'] {
  border-color: #a3361f;
}

.pm-input {
  height: 52px;
  font-size: 16px; /* 16px stops iOS zooming in on focus */
}

.pd-hint {
  font-size: 13px;
  color: var(--muted);
}

.pd-confirm {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px 18px;
  background: #ffffff;
  border-radius: 14px;
  font-size: 16px;
}

.pm-confirm {
  padding: 14px 16px;
  font-size: 15px;
}

.pd-confirm__email {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}

.pd-confirm__email strong {
  overflow-wrap: anywhere;
  text-align: right;
}

.pd-change {
  flex-shrink: 0;
  background: transparent;
  border: 0;
  padding: 0;
  min-height: 32px;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  color: var(--ink);
  text-decoration: underline;
  cursor: pointer;
}

.pd-card {
  background: #ffffff;
  border-radius: 18px;
  padding: 22px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.pd-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.pd-stack {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.pd-stack--4 {
  gap: 4px;
}

.pd-label {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--muted);
}

.pd-exact {
  font-size: 44px;
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 1;
}

.pd-copy {
  height: 40px;
  padding: 0 14px;
  border: 1.5px solid rgba(18, 20, 16, 0.25);
  background: transparent;
  border-radius: 10px;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  color: var(--ink);
  cursor: pointer;
  white-space: nowrap;
}

.pd-acct {
  font-family: var(--font-mono);
  font-size: 34px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.pd-copy-num {
  height: 48px;
  padding: 0 20px;
  border: 0;
  background: var(--forest);
  color: var(--paper);
  border-radius: 12px;
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
}

/* Copied state: the success green. min-width stops the label swap from jumping. */
.pd-copy,
.pm-copy {
  min-width: 96px;
  transition: background-color 0.15s, border-color 0.15s, color 0.15s;
}
.pd-copy-num {
  min-width: 150px;
  transition: background-color 0.15s;
}
.pd-copy.is-copied,
.pm-copy.is-copied {
  border-color: var(--released);
  color: var(--released);
}
.pd-copy-num.is-copied,
.pm-copy-num.is-copied {
  background: var(--released);
}

.pd-name {
  font-size: 18px;
  font-weight: 700;
}

.pd-wait {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pd-wait__top {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.pd-wait__line {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 700;
}

.pd-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 0 4px rgba(245, 184, 46, 0.3);
  flex-shrink: 0;
}

.pd-timer {
  font-family: var(--font-mono);
  font-size: 22px;
  font-weight: 600;
}

.pd-bar {
  height: 6px;
  border-radius: 3px;
  background: var(--paper-deep);
  overflow: hidden;
}

.pd-bar__fill {
  height: 100%;
  background: var(--accent);
  transition: width 1s linear;
}

.pd-wait__p {
  font-size: 14px;
  line-height: 1.5;
  color: var(--ink-2);
}

.pd-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pd-cancel {
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

.pd-receipt--paid {
  padding: 22px 24px 28px;
  gap: 10px;
}

.pd-held {
  font-size: 52px;
  font-weight: 800;
  letter-spacing: -0.045em;
  line-height: 1;
}

.pd-from {
  font-size: 15px;
  color: var(--ink-2);
}

.pd-stamp {
  position: absolute;
  right: 24px;
  top: 30px;
  transform: rotate(9deg);
  border: 3px solid var(--released);
  outline: 1.5px solid var(--released);
  outline-offset: 3px;
  color: var(--released);
  font-family: var(--font-mono);
  font-weight: 600;
  font-size: 15px;
  letter-spacing: 0.14em;
  padding: 5px 10px;
  border-radius: 4px;
}

.pd-text {
  font-size: 16px;
  line-height: 1.55;
  color: var(--ink-2);
}

.pd-text strong {
  color: var(--ink);
}

.pd-text--17 {
  font-size: 17px;
}

.pd-breakdown {
  background: #ffffff;
  border-radius: 16px;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  font-size: 15px;
}

.pd-refunded {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: var(--released);
  white-space: nowrap;
}

/* ---- Mobile full screen ---- */

.pm {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: var(--paper);
  color: var(--ink);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.pm-head {
  flex-shrink: 0;
  height: 64px;
  background: var(--forest);
  color: var(--paper);
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 12px 0 4px;
}

.pm-back {
  width: 44px;
  height: 44px;
  border: 0;
  background: transparent;
  color: var(--paper);
  font-family: var(--font-display);
  font-size: 20px;
  cursor: pointer;
}

.pm-head__text {
  display: flex;
  flex-direction: column;
  flex-grow: 1;
}

.pm-head__title {
  font-size: 17px;
  font-weight: 700;
}

.pm-head__sub {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  color: var(--on-forest-muted);
}

.pm-body {
  flex-grow: 1;
  padding: 20px 20px calc(20px + env(safe-area-inset-bottom, 0px));
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.pm-card {
  background: #ffffff;
  border-radius: 16px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.pm-item {
  display: flex;
  gap: 12px;
  align-items: center;
}

.pm-thumb {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  flex-shrink: 0;
}

.pm-item__text {
  display: flex;
  flex-direction: column;
}

.pm-item__title {
  font-size: 15px;
  font-weight: 700;
}

.pm-item__meta {
  font-size: 13px;
  color: var(--muted);
}

.pm-rows {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 15px;
}

.pm-total {
  font-size: 32px;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.pm-before {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  background: var(--paper-deep);
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.5;
}

.pm-before__h {
  font-size: 10px;
}

.pm-btn {
  margin-top: auto;
  height: 58px;
  border: 0;
  border-radius: 14px;
  background: var(--forest);
  color: var(--paper);
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
  white-space: pre;
  cursor: pointer;
  flex-shrink: 0;
}

.pm-btn--ghost {
  display: flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  border: 1.5px solid var(--ink);
  background: transparent;
}

.pm .pm-btn--ghost {
  color: var(--ink);
}

.pm-card--transfer {
  padding: 18px;
  gap: 14px;
}

.pm-label {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.12em;
  color: var(--muted);
}

.pm-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pm-exact {
  font-size: 36px;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.pm-copy {
  height: 36px;
  padding: 0 12px;
  border: 1.5px solid rgba(18, 20, 16, 0.25);
  background: transparent;
  border-radius: 10px;
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 700;
  color: var(--ink);
  cursor: pointer;
  position: relative;
}

/* 44px touch target on the 36px button. */
.pm-copy::after {
  content: '';
  position: absolute;
  inset: -4px 0;
}

.pm-acct {
  font-family: var(--font-mono);
  font-size: 28px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.pm-copy-num {
  height: 50px;
  border: 0;
  background: var(--forest);
  color: var(--paper);
  border-radius: 12px;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
}

.pm-name {
  font-size: 16px;
  font-weight: 700;
}

.pm-wait__line {
  gap: 8px;
  font-size: 15px;
}

.pm-dot {
  width: 9px;
  height: 9px;
}

.pm-timer {
  font-size: 20px;
}

.pm-wait__p {
  font-size: 13px;
  line-height: 1.5;
  color: var(--ink-2);
}

.pm-foot {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: center;
}

.pm-card--paid {
  padding: 20px;
  gap: 8px;
  position: relative;
}

.pm-held {
  font-size: 42px;
  font-weight: 800;
  letter-spacing: -0.045em;
  line-height: 1;
}

.pm-from {
  font-size: 13px;
  color: var(--ink-2);
}

.pm-stamp {
  position: absolute;
  right: 16px;
  top: 18px;
  transform: rotate(9deg);
  border: 2.5px solid var(--released);
  color: var(--released);
  font-family: var(--font-mono);
  font-weight: 600;
  font-size: 12px;
  letter-spacing: 0.12em;
  padding: 4px 8px;
  border-radius: 3px;
}

.pm-text {
  font-size: 15px;
  line-height: 1.55;
  color: var(--ink-2);
}

.pm-text strong {
  color: var(--ink);
}

.pm-eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
}

.pm-h {
  margin: -8px 0 0;
  font-size: 30px;
  line-height: 1.05;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.pm-breakdown {
  background: #ffffff;
  border-radius: 14px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 14px;
}

.pm-refunded {
  font-size: 20px;
  font-weight: 800;
  color: var(--released);
  white-space: nowrap;
}

.pm :is(button, a):focus-visible {
  outline: 2px solid var(--ink);
  outline-offset: 2px;
  box-shadow: 0 0 0 5px rgba(245, 184, 46, 0.45);
}

.pm-head :is(button, a):focus-visible {
  outline-color: var(--accent);
  box-shadow: none;
}
</style>
