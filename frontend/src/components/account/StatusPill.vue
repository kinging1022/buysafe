<script setup>
import { computed } from 'vue'

const PILLS = {
  live: { text: 'LIVE', bg: '#1E6B45', fg: '#F3EDE0' },
  in_escrow: { text: 'IN ESCROW', bg: '#F5B82E', fg: '#121410' },
  pending: { text: 'PENDING REVIEW', bg: '#121410', fg: '#F3EDE0' },
  rejected: { text: 'NOT APPROVED', bg: '#A3361F', fg: '#FFFFFF' },
  sold: { text: 'SOLD', bg: '#E6DDC9', fg: '#3E4139' },
  // Another buyer's 30-minute transfer window (design/pay-7-someone-*).
  paying: { text: 'SOMEONE IS PAYING', bg: '#F5B82E', fg: '#121410' },
}

const props = defineProps({
  status: { type: String, required: true },
  small: { type: Boolean, default: false }, // the 9px mobile pill
  medium: { type: Boolean, default: false }, // the 10px pill on the mobile listing page
  // Appended after a dot: "LIVE · GOOD CONDITION".
  detail: { type: String, default: '' },
  // Replaces the status's own words (e.g. "LIVE · SOMEONE IS PAYING").
  label: { type: String, default: '' },
})

const pill = computed(() => PILLS[props.status] || PILLS.pending)
const text = computed(() => {
  if (props.label) return props.label
  return props.detail ? `${pill.value.text} · ${props.detail.toUpperCase()}` : pill.value.text
})
</script>

<template>
  <span class="pill" :class="{ 'pill--small': small, 'pill--medium': medium }" :style="{ background: pill.bg, color: pill.fg }">
    {{ text }}
  </span>
</template>

<style scoped>
.pill {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  padding: 6px 10px;
  border-radius: 999px;
  white-space: nowrap;
}

.pill--medium {
  font-size: 10px;
  letter-spacing: 0.1em;
  padding: 5px 9px;
}

.pill--small {
  font-size: 9px;
  letter-spacing: 0.1em;
  padding: 4px 8px;
}
</style>
