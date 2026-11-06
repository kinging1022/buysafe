<script setup>
import { onBeforeUnmount, onMounted, ref, useTemplateRef } from 'vue'

// Mobile gallery (detail-buyer-1-page-mobile): a full-width swipeable
// carousel (CSS scroll-snap) with dots and a "1 / 5" counter.
defineProps({
  photos: { type: Array, required: true },
  title: { type: String, required: true },
})

const track = useTemplateRef('track')
const index = ref(0)

let frame = 0
function onScroll() {
  cancelAnimationFrame(frame)
  frame = requestAnimationFrame(() => {
    const el = track.value
    if (el) index.value = Math.round(el.scrollLeft / el.clientWidth)
  })
}

function goTo(i) {
  const el = track.value
  el?.scrollTo({ left: i * el.clientWidth, behavior: 'smooth' })
}

onMounted(() => track.value?.addEventListener('scroll', onScroll, { passive: true }))
onBeforeUnmount(() => {
  track.value?.removeEventListener('scroll', onScroll)
  cancelAnimationFrame(frame)
})
</script>

<template>
  <div class="car" role="region" aria-roledescription="carousel" :aria-label="`${title} photos`">
    <div ref="track" class="car__track" tabindex="0">
      <div v-for="(url, i) in photos" :key="url" class="car__slide" :aria-label="`Photo ${i + 1} of ${photos.length}`" role="group">
        <img :src="url" :alt="`${title}, photo ${i + 1} of ${photos.length}`" :loading="i ? 'lazy' : 'eager'" />
      </div>
    </div>
    <div class="car__dots">
      <button
        v-for="(url, i) in photos"
        :key="url"
        type="button"
        class="car__dot"
        :class="{ 'car__dot--on': i === index }"
        :aria-label="`Photo ${i + 1}`"
        :aria-current="i === index ? 'true' : undefined"
        @click="goTo(i)"
      ></button>
    </div>
    <span class="car__count num" aria-live="polite">{{ index + 1 }} / {{ photos.length }}</span>
  </div>
</template>

<style scoped>
.car {
  position: relative;
  height: 330px;
  background-color: #e4dbc6;
  background-image: repeating-linear-gradient(135deg, rgba(18, 20, 16, 0.035) 0 10px, rgba(18, 20, 16, 0) 10px 20px);
}

.car__track {
  display: flex;
  height: 100%;
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  scrollbar-width: none;
  overscroll-behavior-x: contain;
}

.car__track::-webkit-scrollbar {
  display: none;
}

.car__slide {
  flex: 0 0 100%;
  scroll-snap-align: start;
  scroll-snap-stop: always;
}

.car__slide img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.car__dots {
  position: absolute;
  bottom: 14px;
  left: 0;
  right: 0;
  display: flex;
  justify-content: center;
  gap: 6px;
  pointer-events: none;
}

/* 6px dots with a 44px-tall hit area. */
.car__dot {
  pointer-events: auto;
  position: relative;
  width: 6px;
  height: 6px;
  padding: 0;
  border: 0;
  border-radius: 3px;
  background: rgba(18, 20, 16, 0.3);
  cursor: pointer;
}

.car__dot::after {
  content: '';
  position: absolute;
  inset: -19px -3px;
}

.car__dot--on {
  width: 18px;
  background: var(--ink);
}

.car__count {
  position: absolute;
  right: 12px;
  top: 12px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  padding: 5px 9px;
  border-radius: 999px;
  background: rgba(18, 20, 16, 0.75);
  color: var(--paper);
}

.car :is(button, [tabindex]):focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
</style>
