<script setup>
import { computed } from 'vue'

const PILLS = {
  live: { text: 'LIVE', bg: '#1E6B45', fg: '#F3EDE0' },
  in_escrow: { text: 'IN ESCROW', bg: '#F5B82E', fg: '#121410' },
  pending: { text: 'PENDING REVIEW', bg: '#121410', fg: '#F3EDE0' },
  rejected: { text: 'NOT APPROVED', bg: '#A3361F', fg: '#FFFFFF' },
  sold: { text: 'SOLD', bg: '#E6DDC9', fg: '#3E4139' },
}

const props = defineProps({
  status: { type: String, required: true },
  small: { type: Boolean, default: false }, // the 9px mobile pill
})

const pill = computed(() => PILLS[props.status] || PILLS.pending)
</script>

<template>
  <span class="pill" :class="{ 'pill--small': small }" :style="{ background: pill.bg, color: pill.fg }">
    {{ pill.text }}
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

.pill--small {
  font-size: 9px;
  letter-spacing: 0.1em;
  padding: 4px 8px;
}
</style>
