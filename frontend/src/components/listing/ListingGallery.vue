<script setup>
import { onBeforeUnmount, onMounted, ref, useTemplateRef } from 'vue'
import { useModal } from '@/composables/useModal'

// Desktop gallery (detail-buyer-1-page-desktop): 580px main photo with
// prev/next and "1 / 5", a 5-column thumbnail row, ←/→ keys, and a plain
// full-screen viewer when the main photo is clicked.
const props = defineProps({
  photos: { type: Array, required: true }, // urls, cover first
  title: { type: String, required: true },
})

const index = ref(0)
const viewerOpen = ref(false)
const viewer = useTemplateRef('viewer')
const { onKeydown: onViewerKeydown } = useModal(viewer, () => viewerOpen.value, () => (viewerOpen.value = false))

const count = () => props.photos.length
const go = (step) => (index.value = (index.value + step + count()) % count())

function onKeydown(e) {
  if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
  // Not while typing, and not behind another dialog (the viewer handles its own).
  if (e.target.closest?.('input, textarea, select, [contenteditable]')) return
  if (!viewerOpen.value && document.querySelector('[aria-modal="true"]')) return
  e.preventDefault()
  go(e.key === 'ArrowLeft' ? -1 : 1)
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="gal">
    <div class="gal__main photo">
      <button type="button" class="gal__open" :aria-label="`View photo ${index + 1} full screen`" @click="viewerOpen = true">
        <img :src="photos[index]" :alt="`${title}, photo ${index + 1} of ${photos.length}`" />
      </button>
      <span class="gal__count num" aria-hidden="true">{{ index + 1 }} / {{ photos.length }}</span>
      <template v-if="photos.length > 1">
        <button type="button" class="gal__nav gal__nav--prev" aria-label="Previous photo" @click="go(-1)">←</button>
        <button type="button" class="gal__nav gal__nav--next" aria-label="Next photo" @click="go(1)">→</button>
      </template>
    </div>
    <div class="gal__thumbs">
      <button
        v-for="(url, i) in photos"
        :key="url"
        type="button"
        class="gal__thumb photo"
        :class="{ 'gal__thumb--on': i === index }"
        :aria-label="`Photo ${i + 1}`"
        :aria-current="i === index ? 'true' : undefined"
        @click="index = i"
      >
        <img :src="url" alt="" loading="lazy" />
      </button>
    </div>

    <Teleport to="body">
      <div v-if="viewerOpen" class="viewer" @keydown="onViewerKeydown">
        <div ref="viewer" class="viewer__in" role="dialog" aria-modal="true" :aria-label="`${title} photos`" @click.self="viewerOpen = false">
          <img :src="photos[index]" :alt="`${title}, photo ${index + 1} of ${photos.length}`" />
          <button type="button" class="viewer__close" aria-label="Close" data-autofocus @click="viewerOpen = false">×</button>
          <template v-if="photos.length > 1">
            <button type="button" class="gal__nav gal__nav--prev" aria-label="Previous photo" @click="go(-1)">←</button>
            <button type="button" class="gal__nav gal__nav--next" aria-label="Next photo" @click="go(1)">→</button>
          </template>
          <span class="gal__count num" aria-live="polite">{{ index + 1 }} / {{ photos.length }}</span>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.gal {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.photo {
  background-color: #e4dbc6;
  background-image: repeating-linear-gradient(135deg, rgba(18, 20, 16, 0.035) 0 12px, rgba(18, 20, 16, 0) 12px 24px);
}

.gal__main {
  height: 580px;
  border-radius: 20px;
  position: relative;
  overflow: hidden;
}

.gal__open {
  display: block;
  width: 100%;
  height: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: zoom-in;
  border-radius: 20px;
}

.gal img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.gal__count {
  position: absolute;
  right: 18px;
  bottom: 18px;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(18, 20, 16, 0.75);
  color: var(--paper);
}

.gal__nav {
  position: absolute;
  top: 50%;
  margin-top: -24px;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--font-display);
  font-size: 20px;
  cursor: pointer;
}

.gal__nav--prev {
  left: 18px;
}

.gal__nav--next {
  right: 18px;
}

.gal__thumbs {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.gal__thumb {
  height: 104px;
  border-radius: 12px;
  border: 0;
  padding: 0;
  overflow: hidden;
  cursor: pointer;
}

.gal__thumb--on {
  border: 2.5px solid var(--ink);
}

.viewer {
  position: fixed;
  inset: 0;
  z-index: 110;
  background: rgba(13, 20, 16, 0.94);
}

.viewer__in {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 72px 96px;
  box-sizing: border-box;
}

.viewer__in img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.viewer__close {
  position: absolute;
  top: 18px;
  right: 18px;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: 1.5px solid rgba(243, 237, 224, 0.5);
  background: transparent;
  color: var(--paper);
  font-family: var(--font-display);
  font-size: 24px;
  cursor: pointer;
}

.gal :is(button):focus-visible,
.viewer :is(button):focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 3px;
}
</style>
