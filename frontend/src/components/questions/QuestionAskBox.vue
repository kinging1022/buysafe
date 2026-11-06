<script setup>
import { computed, ref, useTemplateRef } from 'vue'
import { useContactGuard } from '@/composables/useContactGuard'
import ContactWarning from './ContactWarning.vue'

// "Ask Tolu a question" (design/qa-buyer-1-answered-*, -3-warning-*).
const MIN = 5
const MAX = 280

const props = defineProps({
  sellerName: { type: String, required: true },
  left: { type: Number, default: 3 }, // questions left today
  compact: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
  serverKind: { type: String, default: null },
  error: { type: String, default: '' },
})
const emit = defineEmits(['ask'])

const text = ref('')
const submitted = ref(null)
const box = useTemplateRef('box')
const { kind } = useContactGuard(text)
const shownKind = computed(() => kind.value || (text.value === submitted.value ? props.serverKind : null))
const length = computed(() => text.value.trim().length)
const valid = computed(() => length.value >= MIN && length.value <= MAX && !shownKind.value && !props.busy)

const leftText = computed(() =>
  props.compact
    ? `${props.left} LEFT TODAY`
    : `${props.left} QUESTION${props.left === 1 ? '' : 'S'} LEFT TODAY`,
)

function submit() {
  if (!valid.value) return
  submitted.value = text.value
  emit('ask', text.value.trim())
}

/** Called by the parent once the question is accepted. */
function clear() {
  text.value = ''
  submitted.value = null
}

defineExpose({ focus: () => box.value?.focus(), clear })
</script>

<template>
  <div class="ab" :class="{ 'ab--m': compact, 'ab--bad': shownKind }">
    <label :for="compact ? 'qm' : 'q-text'" class="ab__label">Ask {{ sellerName }} a question</label>
    <textarea
      :id="compact ? 'qm' : 'q-text'"
      ref="box"
      v-model="text"
      rows="3"
      maxlength="320"
      :placeholder="compact ? 'e.g. Does the freezer still get cold?' : 'e.g. Does the freezer still get properly cold?'"
      :aria-describedby="shownKind ? 'q-help q-warn' : 'q-help'"
      :aria-invalid="shownKind ? 'true' : undefined"
      class="ab__box"
    ></textarea>
    <ContactWarning v-if="shownKind" id="q-warn" :kind="shownKind" :compact="compact" />
    <p v-if="error" class="ab__error" role="alert">{{ error }}</p>

    <div v-if="!compact" class="ab__row">
      <span id="q-help" class="ab__help num" aria-live="polite">{{ length }} / {{ MAX }} · PUBLIC ONCE ANSWERED · {{ leftText }}</span>
      <button type="button" class="ab__go" :aria-disabled="!valid" @click="submit">Ask {{ sellerName }}</button>
    </div>
    <template v-else>
      <span id="q-help" class="ab__help num" aria-live="polite">{{ length }} / {{ MAX }} · {{ leftText }} · PUBLIC ONCE ANSWERED</span>
      <button type="button" class="ab__go" :aria-disabled="!valid" @click="submit">Ask {{ sellerName }}</button>
    </template>
  </div>
</template>

<style scoped>
.ab {
  background: #ffffff;
  border-radius: 18px;
  padding: 22px 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  border: 1.5px solid transparent;
  box-shadow: 0 1px 0 rgba(18, 20, 16, 0.06);
}

.ab--m {
  border-radius: 16px;
  padding: 16px;
  gap: 10px;
  box-shadow: none;
}

.ab--bad {
  border: 2px solid #a3361f;
  box-shadow: 0 0 0 4px rgba(163, 54, 31, 0.12);
}

.ab__label {
  font-size: 18px;
  font-weight: 700;
}

.ab--m .ab__label {
  font-size: 16px;
}

.ab__box {
  box-sizing: border-box;
  padding: 14px 16px;
  background: #f7f3ea;
  border: 0;
  border-radius: 12px;
  font-family: var(--font-display);
  font-size: 17px;
  line-height: 1.5;
  color: var(--ink);
  resize: none;
  outline: none;
}

.ab__box::placeholder {
  color: #8c8e85;
}

.ab--m .ab__box {
  padding: 12px 14px;
}

.ab__box:focus-visible {
  box-shadow: 0 0 0 2px var(--ink), 0 0 0 5px rgba(245, 184, 46, 0.45);
}

.ab__row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.ab__help {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.06em;
  color: var(--muted);
}

.ab--m .ab__help {
  font-size: 10px;
  letter-spacing: 0.04em;
}

.ab__go {
  height: 48px;
  padding: 0 24px;
  border: 0;
  border-radius: 12px;
  background: var(--forest);
  color: var(--paper);
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
  white-space: nowrap;
  cursor: pointer;
}

.ab--m .ab__go {
  padding: 0;
}

.ab__go[aria-disabled='true'] {
  background: #8c8e85;
  cursor: not-allowed;
}

.ab__error {
  margin: 0;
  font-size: 14px;
  color: #a3361f;
}
</style>
