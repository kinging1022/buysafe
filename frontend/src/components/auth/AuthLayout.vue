<script setup>
import { PAYMENT_PARTNER } from '@/config/landing'
import '@/styles/auth.css'

// Shared shell for sign up, verify, log in and password reset.
// ≥900px: green 600px panel (wordmark, headline, receipt, trust line) + paper form side.
// <900px: green header band (wordmark or Back link, step label, headline, progress bars).
const props = defineProps({
  // Shows the mobile progress bars and step label; null hides them (login).
  // A step past the last one fills every bar (a flow's done screen).
  step: { type: Number, default: null },
  steps: { type: Number, default: 2 },
  // Replaces "STEP n OF m" on mobile, e.g. 'DONE'.
  stepLabel: { type: String, default: '' },
  // Login's headline is larger (72px desktop / 44px mobile).
  large: { type: Boolean, default: false },
})

const barClass = (n) => (n < props.step ? 'bar--done' : n === props.step ? 'bar--now' : 'bar--todo')
</script>

<template>
  <div class="auth" :class="{ 'auth--large': large, 'auth--steps': step }">
    <header class="panel on-dark">
      <div class="guilloche panel__ring" aria-hidden="true"></div>

      <div class="panel__top">
        <!-- Mobile can swap the wordmark for a Back link; desktop always shows it. -->
        <RouterLink to="/" class="wordmark" :class="{ 'auth-d': $slots['mobile-left'] }">
          buysafe<span class="wordmark__dot">.</span>
        </RouterLink>
        <span v-if="$slots['mobile-left']" class="auth-m"><slot name="mobile-left" /></span>
        <span v-if="step" class="panel__step auth-m">{{ stepLabel || `STEP ${step} OF ${steps}` }}</span>
      </div>

      <div class="panel__mid">
        <h1 class="panel__h1"><slot name="headline" /></h1>
        <div class="panel__receipt auth-d"><slot name="receipt" /></div>
      </div>

      <p class="panel__trust auth-d">✓ Phone-verified users only · Payments by {{ PAYMENT_PARTNER }}</p>

      <div
        v-if="step"
        class="panel__progress auth-m"
        :style="{ gridTemplateColumns: `repeat(${steps}, minmax(0, 1fr))` }"
        aria-hidden="true"
      >
        <span v-for="n in steps" :key="n" class="bar" :class="barClass(n)"></span>
      </div>
    </header>

    <main id="main" class="side">
      <div class="side__top auth-d"><slot name="top" /></div>
      <div class="side__body"><slot /></div>
    </main>
  </div>
</template>

<style scoped>
.auth {
  display: grid;
  /* 600px at 1440 (as designed), narrower on smaller desktops. */
  grid-template-columns: clamp(420px, 41.7vw, 600px) minmax(0, 1fr);
  min-height: 100vh;
  min-height: 100dvh;
  background: var(--paper);
}

/* ---------- Panel ---------- */

.panel {
  background: var(--forest);
  color: var(--paper);
  padding: 48px 64px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  position: relative;
  overflow: hidden;
}

.panel__ring {
  position: absolute;
  width: 760px;
  height: 760px;
  border-radius: 50%;
  left: -180px;
  bottom: -300px;
}

.panel__top {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.auth .wordmark {
  color: var(--paper);
  text-decoration: none;
  font-size: 30px;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.wordmark__dot {
  color: var(--accent);
}

.panel__step {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--accent);
}

.panel__mid {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 40px;
}

.panel__h1 {
  margin: 0;
  font-size: clamp(40px, 4.4445vw, 64px);
  line-height: 0.98;
  font-weight: 800;
  letter-spacing: -0.045em;
}

.auth--large .panel__h1 {
  font-size: clamp(44px, 5vw, 72px);
  line-height: 0.96;
}

.panel__h1 :deep(.accent) {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 400;
  letter-spacing: -0.01em;
  color: var(--accent);
}

.panel__trust {
  position: relative;
  margin: 0;
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.04em;
  color: var(--on-forest-muted);
}

.panel__progress {
  position: relative;
  display: grid;
  gap: 8px;
}

.bar {
  height: 4px;
  border-radius: 2px;
}

.bar--now {
  background: var(--accent);
}

.bar--done {
  background: var(--lime);
}

.bar--todo {
  background: rgba(243, 237, 224, 0.25);
}

/* ---------- Form side ---------- */

.side {
  display: flex;
  flex-direction: column;
  padding: 40px 64px;
  min-width: 0;
}

.side__top {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  font-size: 15px;
  color: var(--ink-2);
}

.side__body {
  flex-grow: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Smaller desktops: tighter padding; receipts scale down to fit the panel. */
@media (min-width: 900px) and (max-width: 1399px) {
  .panel__receipt {
    zoom: 0.8;
  }
}

@media (min-width: 900px) and (max-width: 1199px) {
  .panel {
    padding: 40px;
  }

  .side {
    padding: 40px;
  }

  .panel__receipt {
    zoom: 0.75;
  }
}

/* ---------- Mobile (<900px): header band + form below ---------- */

@media (max-width: 899px) {
  .auth {
    display: flex;
    flex-direction: column;
  }

  .panel {
    /* Content column is max 520px wide on tablets, full width on phones. */
    padding: 20px max(20px, calc((100% - 520px) / 2)) 36px;
    gap: 28px;
    justify-content: flex-start;
  }

  .auth--large .panel {
    padding-bottom: 40px;
    gap: 32px;
  }

  .panel__ring {
    width: 420px;
    height: 420px;
    left: auto;
    bottom: auto;
    right: -200px;
    top: -160px;
    background: repeating-radial-gradient(
      circle at 50% 50%,
      rgba(243, 237, 224, 0) 0 8px,
      rgba(243, 237, 224, 0.1) 8px 9px
    );
  }

  .auth .wordmark {
    font-size: 24px;
  }

  .panel__mid {
    gap: 0;
  }

  .panel__h1 {
    font-size: 40px;
    line-height: 1;
    letter-spacing: -0.04em;
  }

  .auth--large .panel__h1 {
    font-size: 44px;
    line-height: 0.98;
    letter-spacing: -0.045em;
  }

  .panel__h1 :deep(.accent) {
    letter-spacing: inherit;
  }

  .side {
    flex-grow: 1;
    padding: 0 max(20px, calc((100% - 520px) / 2));
  }

  .side__body {
    display: flex;
    align-items: stretch;
    justify-content: flex-start;
  }

  .side__body > :deep(*) {
    flex-grow: 1;
  }
}
</style>

<style>
/* Links in the green band keep their paper colour (auth.css makes links forest). */
.auth .panel a,
.auth .panel a:hover {
  color: var(--paper);
}
</style>
