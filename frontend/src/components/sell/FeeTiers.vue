<script setup>
// "How the fee works", from /listings/fee-schedule/. The seller's tier (the
// quote's tier_key) is highlighted. `compact` is the phone version inside
// a <details>.
defineProps({
  tiers: { type: Array, default: () => [] },
  activeKey: { type: String, default: '' },
  compact: { type: Boolean, default: false },
})
</script>

<template>
  <div v-if="compact" class="ctiers num">
    <div v-for="t in tiers" :key="t.key" class="ctiers__row" :class="{ 'is-active': t.key === activeKey }">
      <span>{{ t.label }}</span><span>{{ t.short_label }}</span>
    </div>
  </div>

  <div v-else class="tiers">
    <span id="fee-tiers-title" class="tiers__label">HOW THE FEE WORKS</span>
    <ul class="tiers__list" aria-labelledby="fee-tiers-title">
      <li v-for="t in tiers" :key="t.key" class="tier num" :class="{ 'is-active': t.key === activeKey }">
        <span class="tier__dot" aria-hidden="true"></span>
        <span class="tier__name">
          <span class="tier__label">{{ t.label }}</span>
          <span v-if="t.key === activeKey" class="tier__here">YOUR PRICE IS HERE</span>
        </span>
        <span class="tier__rate">{{ t.short_label }}</span>
      </li>
    </ul>
    <span class="tiers__note">The fee comes off only when the buyer confirms. Nothing to pay to post.</span>
  </div>
</template>

<style scoped>
.tiers {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tiers__label {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: var(--muted);
  padding-bottom: 10px;
  border-bottom: 2px solid var(--ink);
}

.tiers__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tier {
  display: grid;
  grid-template-columns: 14px 1fr auto;
  gap: 12px;
  align-items: center;
  padding: 14px 12px;
  margin: 0 -12px;
  border-radius: 10px;
}

.tier.is-active {
  background: rgba(245, 184, 46, 0.22);
}

.tier__dot {
  width: 12px;
  height: 12px;
  box-sizing: border-box;
  border-radius: 50%;
  border: 1.5px solid #8c8e85;
}

.tier.is-active .tier__dot {
  background: var(--accent);
  border: 0;
}

.tier__name {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.tier__label {
  font-size: 16px;
}

.tier.is-active .tier__label {
  font-weight: 700;
}

.tier__here {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--amber-ink);
}

.tier__rate {
  font-size: 16px;
  font-weight: 800;
}

.tiers__note {
  font-size: 13px;
  line-height: 1.5;
  color: var(--muted);
  margin-top: 10px;
}

.ctiers {
  display: flex;
  flex-direction: column;
  font-size: 14px;
}

.ctiers__row {
  display: flex;
  justify-content: space-between;
  padding: 10px 8px;
  border-radius: 8px;
}

.ctiers__row.is-active {
  background: rgba(245, 184, 46, 0.25);
  font-weight: 700;
}
</style>
