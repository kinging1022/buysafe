<script setup>
import { CONTACT_LABELS } from '@/composables/useContactGuard'

// The red "REMOVE PHONE NUMBER" box (design/qa-buyer-3-warning-*).
defineProps({
  kind: { type: String, required: true },
  compact: { type: Boolean, default: false },
  id: { type: String, default: undefined },
})
</script>

<template>
  <div :id="id" class="cw" :class="{ 'cw--m': compact }" role="alert">
    <span class="cw__label">{{ CONTACT_LABELS[kind] }}</span>
    <span v-if="!compact">Contact details can’t be shared before payment. Keeping it on buysafe is what keeps your money protected.</span>
    <span v-else>Contact details can’t be shared before payment. It keeps your money protected.</span>
  </div>
</template>

<style scoped>
.cw {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 12px 14px;
  background: rgba(163, 54, 31, 0.08);
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
  color: var(--ink-2);
}

.cw--m {
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.45;
}

.cw__label {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: #a3361f;
  padding-top: 2px;
  white-space: nowrap;
}

.cw--m .cw__label {
  font-size: 10px;
  padding-top: 0;
}
</style>
