<script setup>
import { computed } from 'vue'
import { avatarHex } from '@/config/avatar'

// Initials on the chosen colour. Kept in one place so photo uploads can
// replace the initials later.
const props = defineProps({
  firstName: { type: String, default: '' },
  lastName: { type: String, default: '' },
  color: { type: String, default: 'marigold' }, // AVATAR_COLORS key
  size: { type: Number, default: 44 },
  fontSize: { type: Number, default: null }, // defaults to ~41% of size
  // Double ring: `ring` px of forest, then `ringWidth` px of paper at `ringOpacity`.
  ring: { type: Number, default: 0 },
  ringWidth: { type: Number, default: 1.5 },
  ringOpacity: { type: Number, default: 0.45 },
})

const initials = computed(() =>
  [props.firstName, props.lastName].map((n) => (n || '').trim().charAt(0).toUpperCase()).join(''),
)

const style = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
  fontSize: `${props.fontSize ?? Math.round(props.size * 0.41)}px`,
  background: avatarHex(props.color),
  boxShadow: props.ring
    ? `0 0 0 ${props.ring}px var(--forest), 0 0 0 ${props.ring + props.ringWidth}px rgba(243, 237, 224, ${props.ringOpacity})`
    : undefined,
}))
</script>

<template>
  <span class="avatar" :style="style" aria-hidden="true">{{ initials }}</span>
</template>

<style scoped>
.avatar {
  flex-shrink: 0;
  border-radius: 50%;
  color: var(--ink);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display);
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 1;
  user-select: none;
}
</style>
