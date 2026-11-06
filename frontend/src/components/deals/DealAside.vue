<script setup>
import { computed } from 'vue'
import { naira } from '@/utils/format'
import UserAvatar from '@/components/account/UserAvatar.vue'

// The deal page's right column on desktop (design/deal-*-desktop): the item,
// the other person, the MONEY ledger for your side of the deal, and Report a
// problem.
const props = defineProps({
  deal: { type: Object, required: true },
})
defineEmits(['report'])

const other = computed(() => props.deal.other)
const closed = computed(() => props.deal.state === 'released' || props.deal.state === 'refunded')
const rows = computed(() => {
  const d = props.deal
  if (d.role === 'seller') {
    const acct = d.payout_account
    return [
      ['Buyer paid', naira(d.amount)],
      [`buysafe fee (${d.fee_rate_label})`, `− ${naira(d.fee)}`],
      ['You receive', naira(d.payout)],
      ['Paid out to', acct ? `${acct.bank_short} ····${acct.last4}` : '—'],
    ]
  }
  return [
    ['You paid', naira(d.amount)],
    ['Held in escrow', naira(closed.value ? 0 : d.amount)],
    ['Refunds go to', `${d.source.bank} ····${d.source.last4}`],
  ]
})
</script>

<template>
  <aside class="da">
    <div class="da-card">
      <div class="da-item">
        <span class="da-photo photo"><img v-if="deal.listing.photo" :src="deal.listing.photo" alt="" /></span>
        <span class="da-item__text">
          <span class="da-item__title">{{ deal.listing.title }}</span>
          <RouterLink :to="`/listings/${deal.listing.id}`" class="da-link">View listing</RouterLink>
        </span>
      </div>
      <div class="dash"></div>
      <div class="da-person">
        <UserAvatar :first-name="other.first_name" :last-name="other.last_initial" :color="other.avatar_color" :size="40" :font-size="14" />
        <span class="da-person__text">
          <span class="da-person__name">{{ other.first_name }} {{ other.last_initial }}.</span>
          <span v-if="other.verified" class="da-person__k">✓ PHONE VERIFIED · {{ other.role.toUpperCase() }}</span>
        </span>
      </div>
    </div>

    <div class="da-money num">
      <span class="da-money__h">MONEY</span>
      <div v-for="[label, value] in rows" :key="label" class="da-money__row">
        <span>{{ label }}</span><strong>{{ value }}</strong>
      </div>
    </div>

    <button type="button" class="da-report" @click="$emit('report')">Report a problem</button>
  </aside>
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

.dash {
  border-top: 1.5px dashed rgba(18, 20, 16, 0.28);
}

.da {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.da-card {
  background: #ffffff;
  border-radius: 18px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.da-item {
  display: flex;
  gap: 14px;
  align-items: center;
}

.da-photo {
  width: 64px;
  height: 64px;
  border-radius: 12px;
}

.da-item__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.da-item__title {
  font-size: 16px;
  font-weight: 700;
}

.da-link {
  align-self: flex-start;
  font-size: 13px;
  font-weight: 600;
}

.da-person {
  display: flex;
  align-items: center;
  gap: 12px;
}

.da-person__text {
  display: flex;
  flex-direction: column;
}

.da-person__name {
  font-size: 15px;
  font-weight: 700;
}

.da-person__k {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  color: var(--released);
}

.da-money {
  display: flex;
  flex-direction: column;
}

.da-money__h {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: var(--muted);
  padding-bottom: 10px;
  border-bottom: 2px solid var(--ink);
}

.da-money__row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid rgba(18, 20, 16, 0.14);
  font-size: 14px;
}

.da-money__row span {
  color: var(--ink-2);
}

.da-money__row strong {
  font-weight: 700;
}

.da-report {
  align-self: flex-start;
  background: transparent;
  border: 0;
  padding: 0;
  min-height: 44px;
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
  color: #a3361f;
  text-decoration: underline;
  cursor: pointer;
}

.da :is(a, button):focus-visible {
  outline: 2px solid var(--ink);
  outline-offset: 2px;
  box-shadow: 0 0 0 5px rgba(245, 184, 46, 0.45);
}
</style>
