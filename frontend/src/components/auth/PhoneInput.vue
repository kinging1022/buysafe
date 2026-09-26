<script setup>
import { ref, watch } from 'vue'
import { formatNational, toNationalDigits } from '@/utils/phone'

// v-model is the national digits ('8031234567'). Use toE164() from
// utils/phone for the E.164 value (+2348031234567) sent to the API.
const props = defineProps({
  modelValue: { type: String, default: '' },
  id: { type: String, required: true },
  invalid: { type: Boolean, default: false },
  describedby: { type: String, default: undefined },
  placeholder: { type: String, default: '803 123 4567' },
})
const emit = defineEmits(['update:modelValue', 'blur'])

const text = ref(formatNational(props.modelValue))
watch(
  () => props.modelValue,
  (digits) => {
    if (toNationalDigits(text.value) !== digits) text.value = formatNational(digits)
  },
)

// Formats as you type into "803 123 4567" and accepts pasted 0803…, 803…,
// +234803… or 234803…, keeping the caret after the same digit.
function onInput(e) {
  const el = e.target
  const raw = el.value
  const caret = el.selectionStart ?? raw.length
  const rawDigits = raw.replace(/\D/g, '')
  const digits = toNationalDigits(raw)
  // Digits dropped from the front: the 234 country code or the 0 trunk prefix.
  const prefix = rawDigits.startsWith('234') ? 3 : rawDigits.startsWith('0') ? 1 : 0

  // While only a prefix (+, 0, 2, 23, +234) is typed, show it as typed.
  const display = digits ? formatNational(digits) : raw.replace(/[^\d+]/g, '').slice(0, 4)
  text.value = display
  el.value = display

  if (digits) {
    const typedBefore = raw.slice(0, caret).replace(/\D/g, '').length
    const digitsBefore = Math.min(digits.length, Math.max(0, typedBefore - prefix))
    let pos = 0
    for (let seen = 0; pos < display.length && seen < digitsBefore; pos++) {
      if (/\d/.test(display[pos])) seen++
    }
    el.setSelectionRange(pos, pos)
  }
  emit('update:modelValue', digits)
}
</script>

<template>
  <div class="af-combo phone" :class="{ 'is-error': invalid }">
    <span class="phone__prefix" aria-hidden="true">+234</span>
    <input
      :id="id"
      type="tel"
      inputmode="numeric"
      autocomplete="tel-national"
      :placeholder="placeholder"
      :value="text"
      :aria-invalid="invalid || undefined"
      :aria-describedby="describedby"
      @input="onInput"
      @blur="emit('blur')"
    />
  </div>
</template>

<style scoped>
.phone__prefix {
  display: flex;
  align-items: center;
  align-self: stretch;
  padding: 0 16px;
  font-family: var(--font-mono);
  font-size: 15px;
  font-weight: 500;
  background: #efe9dc;
  border-right: 1.5px solid rgba(18, 20, 16, 0.14);
}

.phone input {
  font-variant-numeric: tabular-nums;
}

@media (max-width: 899px) {
  .phone__prefix,
  .phone input {
    padding: 0 14px;
  }

  .phone input {
    font-variant-numeric: normal;
  }
}
</style>
