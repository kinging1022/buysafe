<script setup>
import { ref, watch } from 'vue'

// Whole-naira price with a ₦ prefix box. Formats with commas as you type
// ("185,000") and keeps the caret after the same digit. v-model is the digits.
const props = defineProps({
  modelValue: { type: String, default: '' },
  id: { type: String, required: true },
  invalid: { type: Boolean, default: false },
  describedby: { type: String, default: undefined },
})
const emit = defineEmits(['update:modelValue', 'blur'])

const MAX_DIGITS = 9 // up to ₦999,999,999; the API caps the real maximum

const withCommas = (digits) => (digits ? Number(digits).toLocaleString('en-NG') : '')
const text = ref(withCommas(props.modelValue))

watch(
  () => props.modelValue,
  (digits) => {
    if (text.value.replace(/\D/g, '') !== digits) text.value = withCommas(digits)
  },
)

function onInput(e) {
  const el = e.target
  const caret = el.selectionStart ?? el.value.length
  const digitsBeforeCaret = el.value.slice(0, caret).replace(/\D/g, '').replace(/^0+/, '').length
  const digits = el.value.replace(/\D/g, '').replace(/^0+/, '').slice(0, MAX_DIGITS)
  const display = withCommas(digits)
  text.value = display
  el.value = display

  // Put the caret back after the same number of digits.
  let pos = 0
  for (let seen = 0; pos < display.length && seen < Math.min(digitsBeforeCaret, digits.length); pos++) {
    if (/\d/.test(display[pos])) seen++
  }
  el.setSelectionRange(pos, pos)
  emit('update:modelValue', digits)
}
</script>

<template>
  <div class="price" :class="{ 'is-error': invalid }">
    <span class="price__prefix" aria-hidden="true">₦</span>
    <input
      :id="id"
      class="price__input num"
      type="text"
      inputmode="numeric"
      autocomplete="off"
      :value="text"
      :aria-invalid="invalid || undefined"
      :aria-describedby="describedby"
      @input="onInput"
      @blur="emit('blur')"
    />
  </div>
</template>

<style scoped>
.price {
  display: flex;
  height: 64px;
  max-width: 420px;
  box-sizing: border-box;
  background: #ffffff;
  border: 1.5px solid rgba(18, 20, 16, 0.22);
  border-radius: 12px;
  overflow: hidden;
}

.price:focus-within {
  border: 2px solid var(--ink);
  box-shadow: 0 0 0 4px rgba(245, 184, 46, 0.45);
}

.price.is-error {
  border: 1.5px solid var(--loss);
}

.price.is-error:focus-within {
  border: 2px solid var(--ink);
}

.price__prefix {
  display: flex;
  align-items: center;
  padding: 0 18px;
  font-size: 24px;
  font-weight: 800;
  background: #efe9dc;
  border-right: 1.5px solid rgba(18, 20, 16, 0.14);
}

.price__input {
  flex-grow: 1;
  min-width: 0;
  border: 0;
  padding: 0 18px;
  background: transparent;
  font-family: var(--font-display);
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--ink);
  outline: none;
}

.price__input:focus-visible {
  outline: none;
}

@media (max-width: 767px) {
  .price {
    height: 60px;
    max-width: none;
  }

  .price__prefix {
    padding: 0 16px;
    font-size: 22px;
  }

  .price__input {
    padding: 0 16px;
    font-size: 24px;
    letter-spacing: normal;
  }
}
</style>
