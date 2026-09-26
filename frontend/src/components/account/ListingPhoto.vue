<script setup>
// A listing's cover photo, or the striped PHOTO placeholder from the references.
defineProps({
  src: { type: String, default: null },
  // Placeholder tint; the references cycle through four.
  index: { type: Number, default: 0 },
  small: { type: Boolean, default: false }, // 96px mobile thumbnail
})

const TINTS = ['#E4DBC6', '#DCD3BF', '#E9E1CF', '#DFD6C2']
</script>

<template>
  <div class="photo" :class="{ 'photo--small': small, 'photo--empty': !src }" :style="src ? null : { backgroundColor: TINTS[index % 4] }">
    <img v-if="src" :src="src" alt="" loading="lazy" />
    <span v-else class="photo__label">PHOTO</span>
    <slot />
  </div>
</template>

<style scoped>
.photo {
  position: relative;
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.photo--empty {
  background-image: repeating-linear-gradient(135deg, rgba(18, 20, 16, 0.035) 0 12px, rgba(18, 20, 16, 0) 12px 24px);
}

.photo img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.photo__label {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  color: rgba(18, 20, 16, 0.4);
}

.photo--small {
  height: 96px;
  border-radius: 10px;
}

.photo--small.photo--empty {
  background-image: repeating-linear-gradient(135deg, rgba(18, 20, 16, 0.035) 0 10px, rgba(18, 20, 16, 0) 10px 20px);
}

.photo--small .photo__label {
  font-size: 9px;
}
</style>
