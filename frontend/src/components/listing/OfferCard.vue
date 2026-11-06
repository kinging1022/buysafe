<script setup>
import { computed, ref } from 'vue'
import { naira } from '@/utils/format'
import { belowPercent, offerAge, timeLeft } from '@/utils/offers'
import UserAvatar from '@/components/account/UserAvatar.vue'

// One offer on the owner's page: design/detail-owner-*. `compact` is the
// mobile card. The payout comes from the API's quote, never computed here.
// Decline is undoable while `offer.undo_until` is ahead (60s); the parent
// makes the calls. Accept asks "Yes, accept ₦X" first (detail-owner-2); once
// accepted the card shows how long the buyer's price is held
// (detail-owner-3's tag). The references' "reserves the item for 24 hours"
// note is left out: accepting no longer reserves anything, first to pay gets it.
const props = defineProps({
  offer: { type: Object, required: true },
  price: { type: Number, required: true },
  compact: { type: Boolean, default: false },
  now: { type: Date, default: () => new Date() }, // ticks while an Undo is showing
  busy: { type: Boolean, default: false },
})
const emit = defineEmits(['decline', 'undo', 'accept'])

const CLOSED_LABELS = { withdrawn: 'WITHDRAWN', expired: 'EXPIRED', accepted: 'EXPIRED', closed: 'CLOSED' }

const confirming = ref(false)
function accept() {
  confirming.value = false
  emit('accept', props.offer)
}

const buyer = computed(() => props.offer.buyer)
const name = computed(() => `${buyer.value.first_name} ${buyer.value.last_initial}.`)
const open = computed(() => props.offer.status === 'pending')
const declined = computed(() => props.offer.status === 'declined')
const canUndo = computed(() => declined.value && props.offer.undo_until && new Date(props.offer.undo_until) > props.now)
// Accepted, and the buyer's price is still held: "ACCEPTED · 23:59 TO PAY".
const held = computed(
  () => props.offer.status === 'accepted' && props.offer.price_held_until && new Date(props.offer.price_held_until) > props.now,
)
const toPay = computed(() => {
  const minutes = Math.max(0, Math.floor((new Date(props.offer.price_held_until) - props.now) / 60000))
  return `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, '0')}`
})
const below = computed(() => `${belowPercent(props.offer.amount, props.price)}% below asking`)
const payout = computed(() => naira(props.offer.quote.payout))
const feeLabel = computed(() => {
  const rate = props.offer.quote.rate_label
  return rate.endsWith('fee') ? `after the ${rate}` : `after the ${rate} fee`
})
const meta = computed(() => {
  const age = offerAge(props.offer.created_at)
  if (!open.value && !declined.value) return age
  const left = timeLeft(props.offer.expires_at)
  return props.compact ? `${age} · ${left} LEFT` : `${age} · EXPIRES IN ${left}`
})
</script>

<template>
  <article
    class="oc"
    :class="{ 'oc--m': compact, 'oc--closed': !open && !held, 'oc--confirming': confirming }"
    :aria-label="`${name}, ${naira(offer.amount)}`"
  >
    <div class="oc__head">
      <UserAvatar
        :first-name="buyer.first_name"
        :last-name="buyer.last_initial"
        :color="buyer.avatar_color"
        :size="compact ? 40 : 48"
        :font-size="compact ? 14 : 17"
      />
      <div class="oc__who">
        <span class="oc__name">{{ name }}<span v-if="!compact && buyer.verified" class="oc__verified">✓ VERIFIED</span></span>
        <span class="oc__meta num">{{ meta }}</span>
      </div>
      <div v-if="!compact" class="oc__amount-col">
        <span class="oc__amount num">{{ naira(offer.amount) }}</span>
        <span class="oc__below num">{{ below }}</span>
      </div>
      <span v-else class="oc__amount num">{{ naira(offer.amount) }}</span>
    </div>

    <p v-if="offer.note" class="oc__note">“{{ offer.note }}”</p>

    <template v-if="!compact">
      <div class="oc__foot num">
        <span class="oc__receive">You’d receive <strong>{{ payout }}</strong> <span class="oc__muted">{{ feeLabel }}</span></span>
        <div v-if="open && confirming" class="oc__btns">
          <button type="button" class="oc__notyet" @click="confirming = false">Not yet</button>
          <button type="button" class="oc__yes num" :disabled="busy" @click="accept">Yes, accept {{ naira(offer.amount) }}</button>
        </div>
        <div v-else-if="open" class="oc__btns">
          <button type="button" class="oc__decline" :disabled="busy" @click="emit('decline', offer)">Decline</button>
          <button type="button" class="oc__accept" :disabled="busy" @click="confirming = true">Accept</button>
        </div>
        <span v-else-if="held" class="oc__held num">ACCEPTED · {{ toPay }} TO PAY</span>
        <span v-else-if="declined" class="oc__declined">
          <span class="oc__declined-label">DECLINED</span>
          <button v-if="canUndo" type="button" class="oc__undo" :disabled="busy" @click="emit('undo', offer)">Undo</button>
        </span>
        <span v-else class="oc__state">{{ CLOSED_LABELS[offer.status] }}</span>
      </div>
    </template>
    <template v-else>
      <span class="oc__receive-m num">{{ below }} · you’d receive <strong>{{ payout }}</strong></span>
      <div v-if="open && confirming" class="oc__btns-m">
        <button type="button" class="oc__notyet" @click="confirming = false">Not yet</button>
        <button type="button" class="oc__yes num" :disabled="busy" @click="accept">Yes, accept</button>
      </div>
      <div v-else-if="open" class="oc__btns-m">
        <button type="button" class="oc__decline" :disabled="busy" @click="emit('decline', offer)">Decline</button>
        <button type="button" class="oc__accept" :disabled="busy" @click="confirming = true">Accept</button>
      </div>
      <span v-else-if="held" class="oc__held oc__held--m num">ACCEPTED · {{ toPay }} TO PAY</span>
      <span v-else-if="declined" class="oc__declined">
        <span class="oc__declined-label">DECLINED</span>
        <button v-if="canUndo" type="button" class="oc__undo" :disabled="busy" @click="emit('undo', offer)">Undo</button>
      </span>
      <span v-else class="oc__state">{{ CLOSED_LABELS[offer.status] }}</span>
    </template>
  </article>
</template>

<style scoped>
.oc--confirming {
  border: 2px solid var(--ink);
}

.oc__notyet {
  height: 48px;
  padding: 0 18px;
  border: 0;
  background: transparent;
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 600;
  color: var(--ink-2);
  cursor: pointer;
}

.oc__yes {
  height: 48px;
  padding: 0 22px;
  border: 0;
  background: var(--forest);
  color: var(--paper);
  border-radius: 12px;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
}

.oc--m .oc__yes {
  padding: 0;
  font-size: 15px;
}

.oc__held {
  align-self: flex-start;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.1em;
  padding: 8px 12px;
  border-radius: 999px;
  background: var(--accent);
  color: var(--ink);
}

.oc__held--m {
  font-size: 11px;
  padding: 7px 11px;
}

.oc {
  background: #ffffff;
  border-radius: 18px;
  padding: 24px 26px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  border: 1.5px solid transparent;
}

.oc--m {
  border-radius: 16px;
  padding: 18px;
  gap: 12px;
}

.oc--closed {
  opacity: 0.55;
}

.oc__head {
  display: flex;
  align-items: center;
  gap: 16px;
}

.oc--m .oc__head {
  gap: 12px;
}

.oc__who {
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex-grow: 1;
  min-width: 0;
}

.oc--m .oc__who {
  gap: 2px;
}

.oc__name {
  font-size: 18px;
  font-weight: 700;
}

.oc--m .oc__name {
  font-size: 16px;
}

.oc__verified {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: var(--released);
  margin-left: 6px;
}

.oc__meta {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--muted);
}

.oc--m .oc__meta {
  font-size: 10px;
}

.oc__amount-col {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.oc__amount {
  font-size: 40px;
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 1;
}

.oc--m .oc__amount {
  font-size: 26px;
  letter-spacing: -0.03em;
  line-height: normal;
}

.oc__below {
  font-size: 13px;
  color: var(--muted);
}

.oc__note {
  margin: 0;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 22px;
  line-height: 1.35;
  color: #2a2c26;
  overflow-wrap: anywhere;
}

.oc--m .oc__note {
  font-size: 19px;
  color: var(--ink);
}

.oc__foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding-top: 14px;
  border-top: 1px dashed rgba(18, 20, 16, 0.2);
}

.oc__receive {
  font-size: 15px;
  color: var(--ink-2);
}

.oc__receive strong,
.oc__receive-m strong {
  color: var(--released);
}

.oc__muted {
  color: var(--muted);
}

.oc__receive-m {
  font-size: 13px;
  color: var(--ink-2);
}

.oc__btns {
  display: flex;
  gap: 10px;
}

.oc__btns-m {
  display: grid;
  grid-template-columns: 1fr 1.3fr;
  gap: 8px;
}

.oc__decline,
.oc__accept {
  height: 48px;
  border-radius: 12px;
  font-family: var(--font-display);
  font-size: 16px;
  cursor: pointer;
}

.oc__decline {
  padding: 0 20px;
  border: 1.5px solid rgba(18, 20, 16, 0.3);
  background: transparent;
  font-weight: 600;
  color: var(--ink-2);
}

.oc__accept {
  padding: 0 24px;
  border: 0;
  background: var(--forest);
  color: var(--paper);
  font-weight: 700;
}

.oc--m .oc__decline,
.oc--m .oc__accept {
  padding: 0;
  font-size: 15px;
}

.oc--m .oc__decline {
  color: var(--ink);
}

/* design/detail-owner-4-one-declined-*: red DECLINED + Undo for 60s. */
.oc__declined {
  display: flex;
  gap: 14px;
  align-items: center;
}

.oc--m .oc__declined {
  gap: 12px;
}

.oc__declined-label {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: #a3361f;
}

.oc--m .oc__declined-label {
  font-size: 11px;
}

.oc__undo {
  background: transparent;
  border: 0;
  padding: 0;
  min-height: 44px;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  color: var(--forest);
  text-decoration: underline;
  cursor: pointer;
}

.oc__decline:disabled,
.oc__undo:disabled {
  cursor: progress;
}

.oc__state {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: var(--muted);
}

.oc :is(button):focus-visible {
  outline: 2px solid var(--ink);
  outline-offset: 2px;
  box-shadow: 0 0 0 5px rgba(245, 184, 46, 0.45);
}
</style>
