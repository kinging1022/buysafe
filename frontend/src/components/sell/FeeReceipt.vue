<script setup>
import { naira } from '@/utils/format'

// "YOUR PAYOUT · ESTIMATE": a receipt with a perforated edge. Every number is
// the API's quote; with no price or quote yet they show ₦0.
defineProps({
  price: { type: Number, default: null }, // what the seller typed
  quote: { type: Object, default: null }, // /listings/fee-quote/ response
  tag: { type: String, default: '' }, // FLAT, 15% or 10%, from the schedule
})
</script>

<template>
  <div class="receipt perf" role="group" aria-label="Your payout, estimate">
    <div class="receipt__head"><span>YOUR PAYOUT</span><span>ESTIMATE</span></div>
    <div class="dash"></div>
    <div class="receipt__rows num">
      <div class="receipt__row">
        <span class="receipt__key">Buyer pays</span>
        <span class="receipt__strong">{{ naira(price || 0) }}</span>
      </div>
      <div class="receipt__row">
        <span class="receipt__key">buysafe fee <span v-if="tag" class="receipt__tag">{{ tag }}</span></span>
        <span class="receipt__strong receipt__fee">− {{ naira(quote ? quote.fee : 0) }}</span>
      </div>
      <div class="dash"></div>
      <div class="receipt__row receipt__row--total">
        <span class="receipt__strong">You receive</span>
        <span class="receipt__total" :class="{ 'is-empty': !quote }">{{ naira(quote ? quote.payout : 0) }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.receipt {
  background: var(--paper);
  border: 1.5px solid rgba(18, 20, 16, 0.12);
  border-bottom: 0;
  padding: 24px 24px 30px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.receipt__head {
  display: flex;
  justify-content: space-between;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--muted);
}

.receipt__rows {
  display: flex;
  flex-direction: column;
  gap: 12px;
  font-size: 16px;
}

.receipt__row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.receipt__row--total {
  align-items: baseline;
}

.receipt__key {
  color: var(--ink-2);
}

.receipt__strong {
  font-weight: 700;
}

.receipt__tag {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--amber-ink);
}

.receipt__fee {
  color: var(--amber-ink);
}

.receipt__total {
  font-size: 38px;
  font-weight: 800;
  letter-spacing: -0.04em;
  color: var(--released);
}

.receipt__total.is-empty {
  color: #8c8e85;
}
</style>
