<script setup>
import { computed } from 'vue'

// Label, control and helper/error line. The default slot receives the ids
// and state to put on the control: { id, describedby, invalid }.
const props = defineProps({
  id: { type: String, required: true },
  label: { type: String, required: true },
  helper: { type: String, default: '' },
  error: { type: String, default: '' },
})

const helperId = computed(() => `${props.id}-helper`)
const errorId = computed(() => `${props.id}-error`)
const describedby = computed(
  () => [props.helper && !props.error ? helperId.value : '', props.error ? errorId.value : ''].filter(Boolean).join(' ') || undefined,
)
</script>

<template>
  <div class="af-field">
    <div class="af-label-row">
      <label :for="id">{{ label }}</label>
      <slot name="label-aside" />
    </div>
    <slot :id="id" :describedby="describedby" :invalid="!!error" />
    <p v-if="helper && !error" :id="helperId" class="af-helper">{{ helper }}</p>
    <p :id="errorId" class="af-error" aria-live="polite"><slot name="error">{{ error }}</slot></p>
  </div>
</template>
