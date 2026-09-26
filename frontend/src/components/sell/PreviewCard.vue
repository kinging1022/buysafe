<script setup>
import { conditionLabel } from '@/config/listing'
import { naira } from '@/utils/format'

// "HOW BUYERS SEE IT": the listing as a browse card, updated as they type.
defineProps({
  coverUrl: { type: String, default: null },
  price: { type: Number, default: null },
  title: { type: String, default: '' },
  condition: { type: String, default: '' },
  place: { type: String, default: '' },
})
</script>

<template>
  <div class="preview" aria-label="Preview of your listing" role="group">
    <div class="preview__photo" :class="{ 'is-empty': !coverUrl }">
      <img v-if="coverUrl" :src="coverUrl" alt="" />
      <span v-else class="preview__ph">COVER</span>
      <span v-if="condition" class="preview__pill">{{ conditionLabel(condition).toUpperCase() }}</span>
    </div>
    <div class="preview__body">
      <span class="preview__price num">{{ naira(price || 0) }}</span>
      <span class="preview__title">{{ title }}</span>
      <span class="preview__meta">{{ [place, 'Just now'].filter(Boolean).join(' · ') }}</span>
    </div>
  </div>
</template>

<style scoped>
.preview {
  background: #ffffff;
  border-radius: 16px;
  overflow: hidden;
  box-shadow:
    0 1px 0 rgba(18, 20, 16, 0.06),
    0 20px 50px rgba(18, 20, 16, 0.06);
}

.preview__photo {
  height: 220px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #e4dbc6;
}

.preview__photo.is-empty {
  background-image: repeating-linear-gradient(135deg, rgba(18, 20, 16, 0.035) 0 12px, rgba(18, 20, 16, 0) 12px 24px);
}

.preview__photo img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.preview__ph {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  color: rgba(18, 20, 16, 0.4);
}

.preview__pill {
  position: absolute;
  left: 14px;
  bottom: 14px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.1em;
  padding: 6px 10px;
  border-radius: 999px;
  background: var(--paper);
}

.preview__body {
  padding: 18px 20px 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.preview__price {
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.preview__title {
  font-size: 17px;
  font-weight: 600;
  min-height: 1.3em;
  overflow-wrap: anywhere;
}

.preview__meta {
  font-size: 14px;
  color: var(--muted);
}
</style>
