<script setup>
import { computed, useAttrs } from 'vue'

// A native <select> drawn like the references: our own chevron, no library.
// `class` styles the wrapper (style the select with `.your-class :deep(select)`);
// every other attribute (id, aria-*) goes on the <select> itself.
defineOptions({ inheritAttrs: false })

const attrs = useAttrs()
const selectAttrs = computed(() => {
  const { class: _class, style: _style, ...rest } = attrs
  return rest
})

defineProps({
  modelValue: { type: String, default: '' },
  // [{ value, label }]
  options: { type: Array, required: true },
  // Shown for the empty value. `placeholderSelectable` keeps it choosable
  // (e.g. "All of Nigeria"); otherwise it's a disabled prompt.
  placeholder: { type: String, default: '' },
  placeholderSelectable: { type: Boolean, default: false },
  chevronSize: { type: Number, default: 14 },
})
const emit = defineEmits(['update:modelValue', 'change'])

function onChange(e) {
  emit('update:modelValue', e.target.value)
  emit('change', e.target.value)
}
</script>

<template>
  <span class="nsel" :class="attrs.class" :style="attrs.style">
    <select v-bind="selectAttrs" class="nsel__el" :value="modelValue" @change="onChange">
      <option v-if="placeholder" value="" :disabled="!placeholderSelectable">{{ placeholder }}</option>
      <option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option>
    </select>
    <svg
      class="nsel__chevron"
      :width="chevronSize"
      :height="chevronSize"
      viewBox="0 0 14 14"
      fill="none"
      stroke="#121410"
      stroke-width="1.8"
      aria-hidden="true"
    >
      <path d="M3 5l4 4 4-4"></path>
    </svg>
  </span>
</template>

<style scoped>
.nsel {
  position: relative;
  display: block;
}

.nsel__el {
  appearance: none;
  -webkit-appearance: none;
  width: 100%;
  cursor: pointer;
  padding-right: 40px;
}

.nsel__el option {
  color: var(--ink);
}

.nsel__chevron {
  position: absolute;
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
}
</style>
