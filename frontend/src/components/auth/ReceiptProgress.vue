<script setup>
// A flow's progress drawn as an escrow receipt: a head (title + counter),
// one row per step and an optional rubber stamp.
defineProps({
  title: { type: String, required: true }, // 'NEW ACCOUNT'
  counter: { type: String, required: true }, // 'STEP 1 OF 2'
  // [{ label: 'Your details', state: 'done' | 'now' | 'next' }]
  rows: { type: Array, required: true },
  // Tag on rows still to come: sign-up shows NEXT, password reset a dash.
  nextTag: { type: String, default: 'NEXT' },
  // Outer size of the empty "next" dot (sign-up 15px, reset 14px).
  nextDotSize: { type: Number, default: 15 },
  // { text: 'ALMOST IN', color: 'var(--released)', top: 40 }
  stamp: { type: Object, default: null },
  label: { type: String, default: undefined }, // accessible summary
})

const TAGS = { done: 'DONE', now: 'NOW' }
</script>

<template>
  <div class="receipt perf" role="img" :aria-label="label || `${title.toLowerCase()}, ${counter.toLowerCase()}`">
    <div class="receipt__head"><span>{{ title }}</span><span>{{ counter }}</span></div>
    <div class="dash"></div>

    <div v-for="row in rows" :key="row.label" class="row" :class="`row--${row.state}`">
      <span
        class="dot"
        :class="`dot--${row.state}`"
        :style="row.state === 'next' ? { width: `${nextDotSize}px`, height: `${nextDotSize}px` } : null"
      ></span>
      <span class="row__label" :class="`row__label--${row.state}`">{{ row.label }}</span>
      <span class="row__tag" :class="`row__tag--${row.state}`">{{ TAGS[row.state] || nextTag }}</span>
    </div>

    <div
      v-if="stamp"
      class="stamp"
      :style="{ color: stamp.color, borderColor: stamp.color, outlineColor: stamp.color, top: `${stamp.top ?? 40}px` }"
    >
      {{ stamp.text }}
    </div>
  </div>
</template>

<style scoped>
.receipt {
  width: 400px;
  background: var(--paper);
  color: var(--ink);
  padding: 24px 26px 30px;
  transform: rotate(-2deg);
  box-shadow: 0 24px 50px rgba(0, 0, 0, 0.28);
  display: flex;
  flex-direction: column;
  gap: 16px;
  position: relative;
}

.receipt__head {
  display: flex;
  justify-content: space-between;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--muted);
}

.row {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 16px;
}

.row--next {
  color: var(--muted);
}

.dot {
  flex: none;
  border-radius: 50%;
}

.dot--now {
  width: 14px;
  height: 14px;
  background: var(--accent);
  box-shadow: 0 0 0 5px rgba(245, 184, 46, 0.3);
}

.dot--done {
  width: 14px;
  height: 14px;
  background: var(--released);
}

.dot--next {
  box-sizing: border-box;
  border: 1.5px solid #8c8e85;
}

.row__label {
  flex-grow: 1;
}

.row__label--now {
  font-weight: 700;
}

.row__label--done {
  font-weight: 600;
}

.row__tag {
  font-family: var(--font-mono);
  font-size: 11px;
}

.row__tag--now {
  color: var(--amber-ink);
}

.row__tag--done {
  color: var(--released);
}

.stamp {
  position: absolute;
  right: 18px;
  transform: rotate(10deg);
  border: 3px solid;
  outline: 1.5px solid;
  outline-offset: 3px;
  font-family: var(--font-mono);
  font-weight: 600;
  font-size: 15px;
  letter-spacing: 0.14em;
  padding: 5px 10px;
  border-radius: 4px;
  opacity: 0.9;
}
</style>
