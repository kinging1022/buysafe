<script setup>
import { computed } from 'vue'
import { naira } from '@/utils/format'
import { hms } from '@/utils/deals'
import { banner, cardLabel, escrowStamp, timeline } from '@/utils/dealView'

// The deal's escrow card on desktop (design/deal-01…11-desktop): the amount
// and stamp, the 5-step timeline, and the turn banner with its countdown and
// action.
const props = defineProps({
  deal: { type: Object, required: true },
  secondsLeft: { type: Number, default: 0 },
  picking: { type: Boolean, default: false }, // the buyer is choosing what to ask for
})
const emit = defineEmits(['record', 'confirm'])

const stamp = computed(() => escrowStamp(props.deal))
const steps = computed(() => timeline(props.deal))
const turn = computed(() => banner(props.deal, { picking: props.picking }))
</script>

<template>
  <section class="ec on-dark" aria-label="Escrow">
    <div class="ec__g" aria-hidden="true"></div>
    <div class="ec__top">
      <div class="ec__money">
        <span class="ec__label">{{ cardLabel(deal) }}</span>
        <span class="ec__amount num">{{ naira(deal.amount) }}</span>
        <span class="ec__sub">{{ stamp.sub }}</span>
        <span class="ec__stamp" :style="{ borderColor: stamp.color, outlineColor: stamp.color, color: stamp.color }">{{ stamp.text }}</span>
      </div>
      <ol class="ec__steps">
        <li v-for="(step, i) in steps" :key="step.label" class="ec__step" :class="`ec__step--${step.status}`">
          <span class="ec__track">
            <span class="ec__dot"></span>
            <span class="ec__line" :class="{ 'ec__line--last': i === steps.length - 1 }"></span>
          </span>
          <span class="ec__name">{{ step.label }}</span>
          <span class="ec__meta num">{{ step.meta }}</span>
        </li>
      </ol>
    </div>
    <div role="status" class="ec__banner" :class="`ec__banner--${turn.tone}`">
      <span class="ec__turn">
        <span class="ec__eyebrow">{{ turn.eyebrow }}</span>
        <span class="ec__text">{{ turn.text }}</span>
      </span>
      <span v-if="turn.countdown && deal.seconds_left != null" class="ec__left num" role="timer">{{ hms(secondsLeft) }} LEFT</span>
      <button v-if="turn.action === 'record'" type="button" class="ec__btn" @click="emit('record')">Record on your phone</button>
      <button v-else-if="turn.action === 'confirm'" type="button" class="ec__btn ec__btn--lime" @click="emit('confirm')">
        Confirm I have the item
      </button>
    </div>
  </section>
</template>

<style scoped>
.ec {
  background: var(--forest);
  color: var(--paper);
  border-radius: 22px;
  overflow: hidden;
  position: relative;
}

.ec__g {
  position: absolute;
  width: 520px;
  height: 520px;
  border-radius: 50%;
  right: -140px;
  top: -280px;
  background: repeating-radial-gradient(circle at 50% 50%, rgba(243, 237, 224, 0) 0 9px, rgba(243, 237, 224, 0.1) 9px 10px);
  pointer-events: none;
}

.ec__top {
  position: relative;
  padding: 28px 36px 24px;
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: 48px;
  align-items: center;
}

.ec__money {
  display: flex;
  flex-direction: column;
  gap: 8px;
  position: relative;
}

.ec__label {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--on-forest-muted);
}

.ec__amount {
  font-size: 60px;
  font-weight: 800;
  letter-spacing: -0.045em;
  line-height: 1;
}

.ec__sub {
  font-size: 17px;
  color: var(--on-forest);
}

.ec__stamp {
  position: absolute;
  right: 0;
  top: 18px;
  transform: rotate(9deg);
  border: 3px solid;
  outline: 1.5px solid;
  outline-offset: 3px;
  font-family: var(--font-mono);
  font-weight: 600;
  font-size: 14px;
  letter-spacing: 0.14em;
  padding: 5px 10px;
  border-radius: 4px;
}

.ec__steps {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.ec__step {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ec__track {
  display: flex;
  align-items: center;
}

.ec__dot {
  width: 18px;
  height: 18px;
  box-sizing: border-box;
  border-radius: 50%;
  flex-shrink: 0;
  position: relative;
  z-index: 1;
  background: transparent;
  border: 1.5px solid rgba(243, 237, 224, 0.45);
}

.ec__line {
  flex-grow: 1;
  height: 2px;
  background: rgba(243, 237, 224, 0.25);
  margin-left: -1px;
}

.ec__line--last {
  background: transparent;
}

.ec__name {
  font-size: 15px;
  font-weight: 400;
  color: var(--on-forest-muted);
  padding-right: 12px;
}

.ec__meta {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  color: var(--on-forest-muted);
}

.ec__step--done .ec__dot {
  background: var(--lime);
  border: 0;
}

.ec__step--done .ec__line:not(.ec__line--last) {
  background: var(--lime);
}

.ec__step--done .ec__name {
  font-weight: 600;
  color: var(--paper);
}

.ec__step--current .ec__dot {
  background: var(--accent);
  border: 0;
  box-shadow: 0 0 0 5px rgba(245, 184, 46, 0.3);
}

.ec__step--current .ec__name {
  font-weight: 800;
  color: var(--paper);
}

.ec__step--current .ec__meta {
  color: var(--accent);
}

.ec__step--failed .ec__dot {
  background: #e5484d;
  border: 0;
}

.ec__step--failed .ec__name {
  font-weight: 600;
  color: var(--paper);
}

.ec__step--refunded .ec__dot {
  background: var(--paper);
  border: 0;
}

.ec__step--refunded .ec__name {
  font-weight: 600;
  color: var(--paper);
}

.ec__banner {
  position: relative;
  padding: 16px 36px;
  display: flex;
  align-items: center;
  gap: 24px;
  color: var(--paper);
}

.ec__banner--turn {
  background: var(--accent);
  color: var(--ink);
}

.ec__banner--wait {
  background: rgba(243, 237, 224, 0.1);
}

.ec__banner--next {
  background: rgba(182, 227, 107, 0.16);
}

.ec__banner--done {
  background: var(--released);
}

.ec__banner--refunded {
  background: #7a2a18;
}

.ec__turn {
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex-grow: 1;
}

.ec__eyebrow {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.12em;
}

.ec__text {
  font-size: 15px;
  line-height: 1.45;
  opacity: 0.9;
}

.ec__left {
  font-family: var(--font-mono);
  font-size: 26px;
  font-weight: 600;
  letter-spacing: 0.02em;
  white-space: nowrap;
}

.ec__btn {
  height: 48px;
  padding: 0 22px;
  border: 0;
  border-radius: 12px;
  background: var(--ink);
  color: var(--paper);
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
  white-space: nowrap;
  cursor: pointer;
}

.ec__btn--lime {
  background: var(--lime);
  color: var(--ink);
}

.ec__btn:focus-visible {
  outline: 2px solid var(--paper);
  outline-offset: 2px;
}

@media (max-width: 1279px) {
  .ec__top {
    grid-template-columns: 1fr;
    gap: 28px;
  }

  .ec__money {
    max-width: 420px;
  }
}
</style>
