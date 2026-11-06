<script setup>
import { computed } from 'vue'
import { qrMatrix } from '@/utils/qr'

// A QR code for `value`, drawn as one SVG path (utils/qr.js, no library).
// `size` is the drawn square; the white margin is the reference's 8px border.
const props = defineProps({
  value: { type: String, required: true },
  size: { type: Number, default: 132 },
  label: { type: String, default: '' },
})

const matrix = computed(() => qrMatrix(props.value))
const path = computed(() => {
  let d = ''
  matrix.value.forEach((row, y) =>
    row.forEach((dark, x) => {
      if (dark) d += `M${x} ${y}h1v1h-1z`
    }),
  )
  return d
})
</script>

<template>
  <svg
    class="qr"
    :width="size"
    :height="size"
    :viewBox="`-2 -2 ${matrix.length + 4} ${matrix.length + 4}`"
    shape-rendering="crispEdges"
    :role="label ? 'img' : undefined"
    :aria-label="label || undefined"
    :aria-hidden="label ? undefined : 'true'"
  >
    <rect x="-2" y="-2" :width="matrix.length + 4" :height="matrix.length + 4" fill="#FFFFFF" />
    <path :d="path" fill="#121410" />
  </svg>
</template>
