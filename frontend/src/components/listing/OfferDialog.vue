<script setup>
import { computed, ref, watch } from 'vue'
import { api } from '@/api/http'
import { digitsOnly, naira } from '@/utils/format'
import { belowPercent, quickPicks, shortTitle } from '@/utils/offers'
import ModalPanel from '@/components/ui/ModalPanel.vue'

// Make an offer: design/detail-buyer-2-offer-open-* and
// detail-buyer-3-offer-below-minimum-*. A dialog on desktop, a sheet on
// mobile. The limits come from the API (`offer_rules`); the API re-checks.
const props = defineProps({
  open: { type: Boolean, required: true },
  sheet: { type: Boolean, default: false },
  listing: { type: Object, required: true },
})
const emit = defineEmits(['close', 'sent'])

const GENERIC_ERROR = 'Something went wrong. Please try again.'

const text = ref('')
const note = ref('')
const sending = ref(false)
const serverError = ref('')

watch(
  () => props.open,
  (open) => {
    if (open) {
      text.value = ''
      note.value = ''
      serverError.value = ''
    }
  },
)

const price = computed(() => props.listing.price)
const rules = computed(() => props.listing.offer_rules)
const picks = computed(() => quickPicks(price.value))
const amount = computed(() => (text.value ? Number(digitsOnly(text.value)) : null))
const seller = computed(() => props.listing.seller.first_name)

// The live line under the amount.
const status = computed(() => {
  if (serverError.value) return { ok: false, text: serverError.value }
  if (!amount.value) return null
  if (amount.value < rules.value.min_amount) {
    const min = naira(rules.value.min_amount)
    return {
      ok: false,
      text: props.sheet
        ? `At least ${min} (${rules.value.min_percent}% of asking).`
        : `Offers must be at least ${min} (${rules.value.min_percent}% of the asking price).`,
    }
  }
  const declined = rules.value.last_declined_amount
  if (declined != null && amount.value <= declined) {
    return { ok: false, text: `Your new offer must be more than ${naira(declined)}.` }
  }
  if (amount.value > rules.value.max_amount) return { ok: false, text: 'That’s the full price. Just use Buy now.' }
  return { ok: true, text: `That’s ${belowPercent(amount.value, price.value)}% below asking.` }
})
const valid = computed(() => !!amount.value && status.value?.ok === true)

// Commas as you type; the caret stays with the digits.
function onInput(e) {
  const el = e.target
  const digitsBefore = digitsOnly(el.value.slice(0, el.selectionStart)).length
  const digits = digitsOnly(el.value).replace(/^0+/, '').slice(0, 9)
  text.value = digits ? Number(digits).toLocaleString('en-NG') : ''
  serverError.value = ''
  el.value = text.value
  let pos = 0
  for (let seen = 0; pos < el.value.length && seen < digitsBefore; pos++) if (/\d/.test(el.value[pos])) seen++
  el.setSelectionRange(pos, pos)
}

function pick(value) {
  text.value = value.toLocaleString('en-NG')
  serverError.value = ''
}

async function send() {
  if (!valid.value || sending.value) return
  sending.value = true
  const res = await api(`/listings/${props.listing.id}/offers/`, {
    method: 'POST',
    body: { amount: amount.value, note: note.value.trim() },
  })
  sending.value = false
  if (res.ok) emit('sent', res.data)
  else serverError.value = res.data?.detail || res.data?.amount?.[0] || res.data?.note?.[0] || GENERIC_ERROR
}
</script>

<template>
  <ModalPanel :open="open" :sheet="sheet" :labelledby="sheet ? 'm-offer-title' : 'offer-title'" @close="emit('close')">
    <form class="of" :class="{ 'of--m': sheet }" novalidate @submit.prevent="send">
      <template v-if="!sheet">
        <div class="of__head">
          <div class="of__titles">
            <span class="of__eyebrow num">{{ shortTitle(listing.title) }} · ASKING {{ naira(price) }}</span>
            <h2 id="offer-title" class="of__h">Make an offer.</h2>
          </div>
          <button type="button" class="of__close" aria-label="Close" @click="emit('close')">×</button>
        </div>
      </template>
      <template v-else>
        <div class="of__head of__head--m">
          <h2 id="m-offer-title" class="of__h">Make an offer.</h2>
          <button type="button" class="of__close" aria-label="Close" @click="emit('close')">×</button>
        </div>
        <span class="of__asking num">ASKING {{ naira(price) }}</span>
      </template>

      <div class="of__amount-group">
        <label v-if="!sheet" for="offer-amt" class="of__label">Your offer</label>
        <div class="of__field">
          <span class="of__cur" aria-hidden="true">₦</span>
          <input
            id="offer-amt"
            :value="text"
            type="text"
            inputmode="numeric"
            autocomplete="off"
            class="num"
            :aria-label="sheet ? 'Your offer' : undefined"
            aria-describedby="offer-line"
            :aria-invalid="status && !status.ok ? 'true' : undefined"
            data-autofocus
            @input="onInput"
          />
        </div>
        <div id="offer-line" class="of__line" :class="{ 'of__line--bad': status && !status.ok }" aria-live="polite">
          <template v-if="status">
            <span class="of__dot" aria-hidden="true"></span><span>{{ status.text }}</span>
          </template>
        </div>
        <div class="of__picks">
          <button
            v-for="p in picks"
            :key="p.percent"
            type="button"
            class="of__pick num"
            :class="{ 'of__pick--on': amount === p.amount }"
            :aria-pressed="amount === p.amount"
            @click="pick(p.amount)"
          >
            −{{ p.percent }}% · {{ naira(p.amount) }}
          </button>
        </div>
      </div>

      <label v-if="!sheet" class="of__note-label">
        Add a note <span class="of__optional">(optional)</span>
        <textarea v-model="note" rows="2" maxlength="280" placeholder="e.g. I can pick up Saturday morning."></textarea>
      </label>
      <textarea v-else v-model="note" rows="2" maxlength="280" aria-label="Add a note (optional)" placeholder="Add a note (optional)"></textarea>

      <div v-if="!sheet" class="of__how">
        <span class="of__how-label">HOW IT WORKS</span>
        <span>No money moves now. If {{ seller }} accepts, you’ll have <strong>24 hours</strong> to pay into escrow. Offers expire after 48 hours.</span>
      </div>
      <span v-else class="of__how-m">No money moves now. If {{ seller }} accepts, you’ll have 24 hours to pay into escrow.</span>

      <div class="of__actions">
        <button type="submit" class="of__send num" :disabled="!valid || sending" :aria-busy="sending">
          Send offer · {{ naira(amount || 0) }}
        </button>
        <button v-if="!sheet" type="button" class="of__cancel" @click="emit('close')">Cancel</button>
      </div>
    </form>
  </ModalPanel>
</template>

<style scoped>
.of {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.of--m {
  gap: 18px;
}

.of__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.of__head--m {
  align-items: center;
}

.of__titles {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.of__eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: var(--muted);
}

.of__h {
  margin: 0;
  font-size: 40px;
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 1;
}

.of--m .of__h {
  font-size: 30px;
}

.of__close {
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

.of__asking {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--muted);
  margin-top: -8px;
}

.of__amount-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.of--m .of__amount-group {
  gap: 0;
}

.of__label {
  font-size: 14px;
  font-weight: 600;
}

.of__field {
  display: flex;
  height: 68px;
  background: #ffffff;
  border: 2px solid var(--ink);
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 0 0 4px rgba(245, 184, 46, 0.45);
}

.of--m .of__field {
  height: 62px;
}

.of__cur {
  display: flex;
  align-items: center;
  padding: 0 18px;
  font-size: 26px;
  font-weight: 800;
  background: #efe9dc;
  border-right: 1.5px solid rgba(18, 20, 16, 0.14);
}

.of--m .of__cur {
  padding: 0 16px;
  font-size: 24px;
}

.of__field input {
  flex-grow: 1;
  min-width: 0;
  border: 0;
  padding: 0 18px;
  background: transparent;
  font-family: var(--font-display);
  font-size: 30px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--ink);
  outline: none;
}

.of .of__field input:focus-visible {
  outline: none;
  box-shadow: none;
}

.of--m .of__field input {
  padding: 0 16px;
  font-size: 26px;
  letter-spacing: 0;
}

.of__line {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 15px;
  color: var(--released);
  min-height: 1.3em;
}

.of--m .of__line {
  font-size: 14px;
  margin: 12px 0 18px;
}

.of__line--bad {
  color: #a3361f;
}

.of__dot {
  flex-shrink: 0;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: currentColor;
}

.of--m .of__dot {
  width: 8px;
  height: 8px;
}

.of__picks {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.of--m .of__picks {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.of__pick {
  height: 40px;
  padding: 0 14px;
  border-radius: 999px;
  border: 1.5px solid rgba(18, 20, 16, 0.25);
  background: transparent;
  color: var(--ink);
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  position: relative;
}

/* 44px hit area on the 40px chip. */
.of__pick::after {
  content: '';
  position: absolute;
  inset: -2px 0;
}

.of--m .of__pick {
  height: 48px;
  padding: 1px 6px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.2;
}

.of__pick--on {
  background: var(--paper-deep);
  border-color: var(--ink);
}

.of__note-label {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
}

.of__optional {
  font-weight: 400;
  color: var(--muted);
}

.of textarea {
  box-sizing: border-box;
  padding: 12px 14px;
  background: #ffffff;
  border: 1.5px solid rgba(18, 20, 16, 0.22);
  border-radius: 12px;
  font-family: var(--font-display);
  font-size: 17px;
  line-height: 1.5;
  color: var(--ink);
  resize: none;
  outline: none;
}

.of textarea::placeholder {
  color: #8c8e85;
}

.of__how {
  display: flex;
  gap: 12px;
  padding: 14px 16px;
  background: var(--paper-deep);
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
  color: var(--ink-2);
}

.of__how-label {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  color: var(--amber-ink);
  padding-top: 2px;
}

.of__how-m {
  font-size: 13px;
  line-height: 1.5;
  color: var(--ink-2);
}

.of__actions {
  display: flex;
  gap: 12px;
}

.of__send {
  flex-grow: 1;
  height: 58px;
  border: 0;
  border-radius: 12px;
  background: var(--forest);
  color: var(--paper);
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  cursor: pointer;
}

.of--m .of__send {
  font-size: 17px;
}

.of__send:disabled {
  background: #8c8e85;
  cursor: not-allowed;
}

.of__cancel {
  height: 58px;
  padding: 0 22px;
  border: 0;
  background: transparent;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 600;
  color: var(--ink-2);
  cursor: pointer;
}
</style>
