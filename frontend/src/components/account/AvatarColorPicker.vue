<script setup>
import { nextTick, useTemplateRef } from 'vue'
import { AVATAR_COLORS } from '@/config/avatar'

// The avatar colour swatches: an ARIA radiogroup (arrow keys move the choice).
const props = defineProps({
  modelValue: { type: String, required: true },
  // Paper ring around the chosen swatch: 5.5px on desktop, 5px on mobile.
  ring: { type: Number, default: 5.5 },
  labelledby: { type: String, default: undefined },
})
const emit = defineEmits(['update:modelValue'])

const swatches = useTemplateRef('swatches')

async function onKeydown(e) {
  const i = AVATAR_COLORS.findIndex((c) => c.key === props.modelValue)
  const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key]
  if (!step) return
  e.preventDefault()
  const next = (i + step + AVATAR_COLORS.length) % AVATAR_COLORS.length
  emit('update:modelValue', AVATAR_COLORS[next].key)
  await nextTick()
  swatches.value?.[next]?.focus()
}
</script>

<template>
  <div role="radiogroup" :aria-labelledby="labelledby" class="swatches" @keydown="onKeydown">
    <button
      v-for="c in AVATAR_COLORS"
      ref="swatches"
      :key="c.key"
      type="button"
      role="radio"
      class="swatch"
      :aria-checked="modelValue === c.key"
      :aria-label="c.label"
      :tabindex="modelValue === c.key ? 0 : -1"
      :style="{
        background: c.hex,
        boxShadow: modelValue === c.key ? `0 0 0 3px var(--forest), 0 0 0 ${ring}px var(--paper)` : undefined,
      }"
      @click="emit('update:modelValue', c.key)"
    ></button>
  </div>
</template>

<style scoped>
.swatches {
  display: flex;
  gap: 12px;
}

.swatch {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  border-radius: 50%;
  border: 0;
  padding: 0;
  cursor: pointer;
  box-shadow: inset 0 0 0 1px rgba(18, 20, 16, 0.15);
}

.swatch:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 8px;
}

/* The mobile reference's 8px gap overflows its own 390px frame by 8px;
   6px fits beside the 88px avatar. */
@media (max-width: 767px) {
  .swatches {
    gap: 6px;
  }
}
</style>
