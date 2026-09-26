<script setup>
import { nextTick, ref, useTemplateRef } from 'vue'

const LENGTH = 6

defineProps({
  invalid: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  describedby: { type: String, default: undefined },
})
const emit = defineEmits(['update:modelValue', 'complete'])

const digits = ref(Array(LENGTH).fill(''))
const boxes = useTemplateRef('boxes')

function focusBox(i) {
  boxes.value?.[Math.max(0, Math.min(LENGTH - 1, i))]?.focus()
}

function publish() {
  const code = digits.value.join('')
  emit('update:modelValue', code)
  if (/^\d{6}$/.test(code)) emit('complete', code)
}

// Fill from box `start` with a run of digits (typed over, pasted or autofilled).
function fill(start, text) {
  const incoming = text.replace(/\D/g, '').split('')
  if (!incoming.length) return
  // A full code always starts at the first box.
  const from = incoming.length >= LENGTH ? 0 : start
  incoming.slice(0, LENGTH - from).forEach((d, k) => (digits.value[from + k] = d))
  focusBox(Math.min(from + incoming.length, LENGTH - 1))
  publish()
}

function onInput(i, e) {
  const value = e.target.value.replace(/\D/g, '')
  if (value.length > 1) {
    fill(i, value)
  } else {
    digits.value[i] = value
    if (value) focusBox(i + 1)
    publish()
  }
  e.target.value = digits.value[i] // keep digits only, one per box
}

function onKeydown(i, e) {
  if (e.key === 'Backspace') {
    e.preventDefault()
    if (digits.value[i]) {
      digits.value[i] = ''
    } else if (i > 0) {
      digits.value[i - 1] = ''
      focusBox(i - 1)
    }
    publish()
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault()
    focusBox(i - 1)
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    focusBox(i + 1)
  }
}

function onPaste(i, e) {
  e.preventDefault()
  fill(i, e.clipboardData?.getData('text') ?? '')
}

async function clear() {
  digits.value = Array(LENGTH).fill('')
  emit('update:modelValue', '')
  await nextTick()
  focusBox(0)
}

defineExpose({ clear, focus: () => focusBox(digits.value.findIndex((d) => !d)) })
</script>

<template>
  <div class="otp">
    <input
      v-for="(digit, i) in digits"
      ref="boxes"
      :key="i"
      class="otp__box"
      :class="{ 'is-filled': digit, 'is-error': invalid }"
      type="text"
      inputmode="numeric"
      pattern="[0-9]*"
      :autocomplete="i === 0 ? 'one-time-code' : 'off'"
      :aria-label="`Digit ${i + 1}`"
      :aria-invalid="invalid || undefined"
      :aria-describedby="describedby"
      :value="digit"
      :disabled="disabled"
      @input="onInput(i, $event)"
      @keydown="onKeydown(i, $event)"
      @paste="onPaste(i, $event)"
      @focus="$event.target.select()"
    />
  </div>
</template>

<style scoped>
.otp {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
}

.otp__box {
  height: 72px;
  width: 100%;
  box-sizing: border-box;
  text-align: center;
  font-family: var(--font-mono);
  font-size: 30px;
  font-weight: 600;
  color: var(--ink);
  background: #ffffff;
  border: 1.5px solid rgba(18, 20, 16, 0.22);
  border-radius: 12px;
  outline: none;
  padding: 0;
}

.otp__box.is-filled {
  border: 1.5px solid var(--ink);
}

.otp__box.is-error {
  border: 1.5px solid var(--loss);
}

.otp__box:focus {
  border: 2px solid var(--ink);
  box-shadow: 0 0 0 4px rgba(245, 184, 46, 0.45);
}

.otp__box:focus-visible {
  outline: none;
}

.otp__box:disabled {
  opacity: 1;
  color: var(--ink);
}

@media (max-width: 899px) {
  .otp {
    gap: 8px;
  }

  .otp__box {
    height: 62px;
    font-size: 26px;
    border-radius: 10px;
  }
}
</style>
