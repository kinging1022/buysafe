<script setup>
import { ref } from 'vue'

defineProps({
  modelValue: { type: String, default: '' },
  id: { type: String, required: true },
  placeholder: { type: String, default: undefined },
  autocomplete: { type: String, default: 'current-password' },
  // Sign-up fields space the dots out (.1em); the login field doesn't.
  spaced: { type: Boolean, default: false },
  // Optional live checklist: [{ label: '8+ characters', met: true }, …]
  rules: { type: Array, default: null },
  invalid: { type: Boolean, default: false },
  describedby: { type: String, default: undefined },
})
const emit = defineEmits(['update:modelValue', 'blur'])

const shown = ref(false)
</script>

<template>
  <div class="af-combo pw" :class="{ 'is-error': invalid }">
    <input
      :id="id"
      :type="shown ? 'text' : 'password'"
      :class="{ 'pw--spaced': spaced }"
      :value="modelValue"
      :placeholder="placeholder"
      :autocomplete="autocomplete"
      :aria-invalid="invalid || undefined"
      :aria-describedby="[describedby, rules ? `${id}-rules` : ''].filter(Boolean).join(' ') || undefined"
      autocapitalize="off"
      spellcheck="false"
      @input="emit('update:modelValue', $event.target.value)"
      @blur="emit('blur')"
    />
    <button
      type="button"
      class="pw__toggle"
      :aria-pressed="shown"
      :aria-label="shown ? 'Hide password' : 'Show password'"
      @click="shown = !shown"
    >
      {{ shown ? 'HIDE' : 'SHOW' }}
    </button>
  </div>
  <ul v-if="rules" :id="`${id}-rules`" class="pw__rules">
    <li v-for="rule in rules" :key="rule.label" :class="{ 'is-met': rule.met }">
      <span aria-hidden="true">{{ rule.met ? '✓' : '○' }}</span> {{ rule.label }}
      <span class="visually-hidden">{{ rule.met ? '(done)' : '(not yet)' }}</span>
    </li>
  </ul>
</template>

<style scoped>
.pw--spaced {
  letter-spacing: 0.1em;
}

.pw__toggle {
  height: 100%;
  padding: 0 16px;
  border: 0;
  background: transparent;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: var(--ink-2);
  cursor: pointer;
}

.pw__toggle:focus-visible {
  outline-offset: -4px;
}

.pw__rules {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 500;
  color: #8c8e85;
}

.pw__rules .is-met {
  color: var(--released);
}

@media (max-width: 899px) {
  .pw__rules {
    gap: 6px 14px;
  }
}
</style>
