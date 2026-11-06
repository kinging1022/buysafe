<script setup>
import { computed, ref } from 'vue'
import { naira } from '@/utils/format'
import { hms } from '@/utils/deals'
import { banner, escrowStamp, timeline } from '@/utils/dealView'

// The deal page's escrow on mobile: a compact forest bar (amount + stamp)
// that expands to the timeline (design/deal-00-escrow-bar-expanded-mobile),
// then the turn banner.
const props = defineProps({
  deal: { type: Object, required: true },
  secondsLeft: { type: Number, default: 0 },
  picking: { type: Boolean, default: false },
})
const emit = defineEmits(['confirm'])

const open = ref(false)
const stamp = computed(() => escrowStamp(props.deal))
const steps = computed(() => timeline(props.deal, { mobile: true }))
const turn = computed(() => banner(props.deal, { mobile: true, picking: props.picking }))
</script>

<template>
  <div class="eb on-dark">
    <button type="button" class="eb__toggle" :aria-expanded="open" aria-controls="eb-steps" @click="open = !open">
      <span class="eb__money">
        <span class="eb__k">DEAL {{ deal.id }} · {{ stamp.text }}</span>
        <span class="eb__amount num">{{ naira(deal.amount) }} <span class="eb__sub">{{ stamp.short }}</span></span>
      </span>
      <span class="eb__more">{{ open ? 'Hide ▴' : 'Progress ▾' }}</span>
    </button>
    <ol v-show="open" id="eb-steps" class="eb__steps">
      <li v-for="step in steps" :key="step.label" class="eb__step" :class="`eb__step--${step.status}`">
        <span class="eb__dot"></span>
        <span class="eb__name">{{ step.label }}</span>
        <span class="eb__meta num">{{ step.meta }}</span>
      </li>
    </ol>
  </div>
  <div role="status" class="eb-banner" :class="`eb-banner--${turn.tone}`">
    <span class="eb-banner__text">
      <span class="eb-banner__k">{{ turn.eyebrow }}</span>
      <span v-if="turn.countdown && deal.seconds_left != null" class="eb-banner__left num" role="timer">{{ hms(secondsLeft) }} LEFT</span>
    </span>
    <RouterLink v-if="turn.action === 'record'" :to="`/deals/${deal.id}/record`" class="eb-banner__btn">Record</RouterLink>
    <button v-else-if="turn.action === 'confirm'" type="button" class="eb-banner__btn eb-banner__btn--forest" @click="emit('confirm')">
      Confirm
    </button>
  </div>
</template>

<style scoped>
.eb {
  flex-shrink: 0;
  background: var(--forest);
  color: var(--paper);
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.eb__toggle {
  border: 0;
  padding: 0;
  background: transparent;
  color: var(--paper);
  text-align: left;
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  font-family: var(--font-display);
  cursor: pointer;
  min-height: 44px;
}

.eb__money {
  display: flex;
  flex-direction: column;
}

.eb__k {
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.12em;
  color: var(--on-forest-muted);
}

.eb__amount {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.eb__sub {
  font-size: 13px;
  font-weight: 500;
  color: var(--on-forest);
  letter-spacing: 0;
}

.eb__more {
  font-size: 12px;
  font-weight: 600;
  color: var(--on-forest);
}

.eb__steps {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.eb__step {
  display: grid;
  grid-template-columns: 14px 1fr auto;
  gap: 10px;
  align-items: center;
}

.eb__dot {
  width: 12px;
  height: 12px;
  box-sizing: border-box;
  border-radius: 50%;
  border: 1.5px solid rgba(243, 237, 224, 0.45);
}

.eb__name {
  font-size: 14px;
  font-weight: 400;
  color: var(--on-forest-muted);
}

.eb__meta {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--on-forest-muted);
}

.eb__step--done .eb__dot {
  background: var(--lime);
  border: 0;
}

.eb__step--done .eb__name,
.eb__step--failed .eb__name,
.eb__step--refunded .eb__name {
  font-weight: 600;
  color: var(--paper);
}

.eb__step--current .eb__dot {
  background: var(--accent);
  border: 0;
  box-shadow: 0 0 0 4px rgba(245, 184, 46, 0.3);
}

.eb__step--current .eb__name {
  font-weight: 800;
  color: var(--paper);
}

.eb__step--current .eb__meta {
  color: var(--accent);
}

.eb__step--failed .eb__dot {
  background: #e5484d;
  border: 0;
}

.eb__step--refunded .eb__dot {
  background: var(--paper);
  border: 0;
}

.eb-banner {
  flex-shrink: 0;
  padding: 10px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--paper);
  min-height: 44px;
  box-sizing: border-box;
}

.eb-banner--turn {
  background: var(--accent);
  color: var(--ink);
}

.eb-banner--wait {
  background: #1b4a38;
}

.eb-banner--next {
  background: #e7f2d4;
  color: var(--ink);
}

.eb-banner--done {
  background: var(--released);
}

.eb-banner--refunded {
  background: #7a2a18;
}

.eb-banner__text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  flex-grow: 1;
  min-width: 0;
}

.eb-banner__k {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.1em;
}

.eb-banner__left {
  font-family: var(--font-mono);
  font-size: 16px;
  font-weight: 600;
}

.eb-banner__btn {
  height: 40px;
  display: flex;
  align-items: center;
  padding: 0 14px;
  text-decoration: none;
  border: 0;
  border-radius: 10px;
  background: var(--ink);
  color: var(--paper);
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
  cursor: pointer;
  position: relative;
}

.eb-banner__btn::after {
  content: '';
  position: absolute;
  inset: -2px 0;
}

.eb-banner__btn--forest {
  background: var(--forest);
}

.eb__toggle:focus-visible,
.eb-banner__btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
</style>
