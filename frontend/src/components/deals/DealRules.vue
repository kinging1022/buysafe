<script setup>
import { ref } from 'vue'

// The chat's pinned rules and disclaimer (design/deal-*): open on desktop
// (Hide ▴), a one-line bar on mobile (View ▾). The mobile expanded state
// isn't designed; it shows the same list in one column.
const props = defineProps({
  buyer: { type: String, required: true },
  seller: { type: String, required: true },
  mobile: { type: Boolean, default: false },
})

const open = ref(!props.mobile)
</script>

<template>
  <section class="dr" :class="{ 'dr--m': mobile }" aria-label="Deal rules and disclaimer">
    <button type="button" class="dr__head" :aria-expanded="open" aria-controls="deal-rules" @click="open = !open">
      <span class="dr__k">{{ mobile ? 'PINNED · RULES & DISCLAIMER' : 'PINNED · DEAL RULES & DISCLAIMER' }}</span>
      <span class="dr__toggle">{{ open ? 'Hide ▴' : mobile ? 'View ▾' : 'Show ▾' }}</span>
    </button>
    <div v-show="open" id="deal-rules">
      <ol class="dr__list num">
        <li><span class="dr__n">1</span><span><strong>{{ seller }}’s first message is a live video</strong>, camera only. {{ buyer }} rates it. Up to 3 videos.</span></li>
        <li><span class="dr__n">2</span><span><strong>{{ seller }} can type after a Good rating.</strong> Contact details can be shared from then.</span></li>
        <li><span class="dr__n">3</span><span><strong>Meet in public</strong> and check it before confirming.</span></li>
        <li><span class="dr__n">4</span><span><strong>Money is released only when {{ buyer }} confirms.</strong> Refunds go back to the paying account.</span></li>
      </ol>
      <p class="dr__p">buysafe holds the money but doesn’t inspect items. Deadlines pause 10 PM – 7 AM.</p>
    </div>
  </section>
</template>

<style scoped>
.dr {
  background: var(--paper);
  border-bottom: 1px solid rgba(18, 20, 16, 0.14);
  padding: 16px 24px;
}

.dr__head {
  width: 100%;
  border: 0;
  padding: 0;
  background: transparent;
  color: var(--ink);
  font-family: var(--font-display);
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 32px;
}

.dr__k {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--amber-ink);
}

.dr__toggle {
  font-size: 13px;
  font-weight: 600;
}

.dr__list {
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 28px;
  font-size: 13px;
  line-height: 1.45;
}

.dr__list li {
  display: grid;
  grid-template-columns: 18px 1fr;
  gap: 6px;
}

.dr__n {
  font-family: var(--font-serif);
  font-size: 18px;
  line-height: 1;
  color: var(--amber-ink);
}

.dr__p {
  margin: 10px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--muted);
}

.dr--m {
  flex-shrink: 0;
  padding: 8px 16px;
}

.dr--m .dr__head {
  min-height: 28px;
}

.dr--m .dr__k {
  font-size: 9px;
  letter-spacing: 0.1em;
}

.dr--m .dr__toggle {
  font-size: 12px;
}

.dr--m .dr__list {
  grid-template-columns: 1fr;
  margin-top: 8px;
}

.dr__head:focus-visible {
  outline: 2px solid var(--ink);
  outline-offset: 2px;
}
</style>
