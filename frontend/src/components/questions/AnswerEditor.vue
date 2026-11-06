<script setup>
import { computed, onMounted, ref, useId, useTemplateRef } from 'vue'
import { useContactGuard } from '@/composables/useContactGuard'
import ContactWarning from './ContactWarning.vue'

// The owner's inline answer box (design/qa-owner-1-answering-*). Used to post
// an answer and to edit one. Focus moves into it when it opens.
const MIN = 2
const MAX = 500

const props = defineProps({
  initial: { type: String, default: '' },
  submitLabel: { type: String, default: 'Post answer' }, // or "Save answer"
  compact: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
  serverKind: { type: String, default: null }, // contact kind the backend refused
  error: { type: String, default: '' },
})
const emit = defineEmits(['submit', 'cancel'])

const id = useId()
const text = ref(props.initial)
const box = useTemplateRef('box')
const { kind } = useContactGuard(text)
// The text last sent: the server's refusal shows until it's changed.
const submitted = ref(null)
const shownKind = computed(() => kind.value || (text.value === submitted.value ? props.serverKind : null))
const length = computed(() => text.value.trim().length)
const valid = computed(() => length.value >= MIN && length.value <= MAX && !shownKind.value && !props.busy)

function submit() {
  if (!valid.value) return
  submitted.value = text.value
  emit('submit', text.value.trim())
}

onMounted(() => {
  box.value?.focus()
  box.value?.setSelectionRange(text.value.length, text.value.length)
})
</script>

<template>
  <div class="ae" :class="{ 'ae--m': compact }">
    <label class="ae__label" :for="id">YOUR ANSWER · PUBLIC</label>
    <textarea
      :id="id"
      ref="box"
      v-model="text"
      rows="3"
      :maxlength="MAX + 20"
      class="ae__box"
      :class="{ 'ae__box--bad': shownKind }"
      :aria-describedby="`${id}-count${shownKind ? ` ${id}-warn` : ''}`"
      :aria-invalid="shownKind ? 'true' : undefined"
      @keydown.esc.stop="emit('cancel')"
    ></textarea>
    <ContactWarning v-if="shownKind" :id="`${id}-warn`" :kind="shownKind" :compact="compact" />
    <p v-if="error" class="ae__error" role="alert">{{ error }}</p>

    <template v-if="!compact">
      <div class="ae__row">
        <span :id="`${id}-count`" class="ae__count num" aria-live="polite">{{ length }} / {{ MAX }} · YOU CAN EDIT IT LATER</span>
        <div class="ae__btns">
          <button type="button" class="ae__cancel" @click="emit('cancel')">Cancel</button>
          <button type="button" class="ae__submit" :aria-disabled="!valid" @click="submit">{{ submitLabel }}</button>
        </div>
      </div>
    </template>
    <template v-else>
      <span :id="`${id}-count`" class="ae__count num" aria-live="polite">{{ length }} / {{ MAX }}</span>
      <div class="ae__btns-m">
        <button type="button" class="ae__cancel" @click="emit('cancel')">Cancel</button>
        <button type="button" class="ae__submit" :aria-disabled="!valid" @click="submit">{{ submitLabel }}</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.ae {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-left: 36px;
  padding-left: 18px;
  border-left: 2px solid var(--released);
}

.ae--m {
  gap: 8px;
  margin-left: 0;
  padding-left: 0;
  border-left: 0;
}

.ae__label {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--released);
}

.ae--m .ae__label {
  font-size: 10px;
  letter-spacing: 0.1em;
}

.ae__box {
  box-sizing: border-box;
  padding: 14px 16px;
  background: #f7f3ea;
  border: 1.5px solid rgba(18, 20, 16, 0.18);
  border-radius: 12px;
  font-family: var(--font-display);
  font-size: 17px;
  line-height: 1.55;
  color: var(--ink);
  resize: none;
  outline: none;
}

.ae--m .ae__box {
  padding: 12px 14px;
  line-height: 1.5;
}

.ae__box:focus-visible {
  border-color: var(--ink);
  box-shadow: 0 0 0 4px rgba(245, 184, 46, 0.45);
}

.ae__box--bad,
.ae__box--bad:focus-visible {
  border: 2px solid #a3361f;
  box-shadow: 0 0 0 4px rgba(163, 54, 31, 0.12);
}

.ae__row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.ae__count {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--muted);
}

.ae--m .ae__count {
  font-size: 10px;
}

.ae__btns {
  display: flex;
  gap: 8px;
}

.ae__btns-m {
  display: grid;
  grid-template-columns: 1fr 1.3fr;
  gap: 8px;
}

.ae__cancel,
.ae__submit {
  height: 44px;
  border: 0;
  font-family: var(--font-display);
  font-size: 15px;
  cursor: pointer;
}

.ae__cancel {
  padding: 0 16px;
  background: transparent;
  font-weight: 600;
  color: var(--ink-2);
}

.ae__submit {
  padding: 0 20px;
  border-radius: 12px;
  background: var(--forest);
  color: var(--paper);
  font-weight: 700;
}

.ae--m .ae__cancel,
.ae--m .ae__submit {
  height: 46px;
  padding: 0;
}

.ae--m .ae__cancel {
  color: var(--ink);
}

.ae__submit[aria-disabled='true'] {
  background: #8c8e85;
  cursor: not-allowed;
}

.ae__error {
  margin: 0;
  font-size: 14px;
  color: #a3361f;
}
</style>
