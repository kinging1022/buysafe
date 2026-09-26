<script setup>
import { computed } from 'vue'
import { listingLinks } from '@/config/account'
import { naira } from '@/utils/format'
import { cardDisplay } from './listingDisplay'
import ListingPhoto from './ListingPhoto.vue'
import StatusPill from './StatusPill.vue'

// Desktop/tablet grid card, from design/profile-tab-all-desktop.reference.html.
const props = defineProps({
  item: { type: Object, required: true },
  index: { type: Number, default: 0 },
})

const shown = computed(() => cardDisplay(props.item))
</script>

<template>
  <article class="card" :class="{ 'card--sold': item.display_status === 'sold' }">
    <ListingPhoto :src="item.first_image_url" :index="index">
      <StatusPill :status="item.display_status" class="card__pill" />
    </ListingPhoto>
    <div class="card__body">
      <h3 class="card__title">{{ item.title }}</h3>
      <span class="card__meta">{{ shown.meta }}</span>
      <span class="card__price num">{{ naira(item.price) }}</span>
      <span class="card__note" :style="{ color: shown.noteColor }">{{ shown.note }}</span>
      <div class="card__actions">
        <RouterLink :to="shown.action.to" class="card__primary">{{ shown.action.label }}</RouterLink>
        <RouterLink :to="listingLinks(item.id).view" class="card__view">View</RouterLink>
      </div>
    </div>
  </article>
</template>

<style scoped>
.card {
  background: #ffffff;
  border-radius: 16px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 1px 0 rgba(18, 20, 16, 0.06);
  min-width: 0;
}

.card--sold {
  opacity: 0.72;
}

.card__pill {
  position: absolute;
  left: 14px;
  top: 14px;
}

.card__body {
  padding: 18px 20px 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex-grow: 1;
}

.card__title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.01em;
  overflow-wrap: anywhere;
}

.card__meta {
  font-size: 14px;
  color: var(--muted);
}

.card__price {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.03em;
  margin-top: 4px;
}

/* Grows so the actions line up across a row when titles wrap. */
.card__note {
  font-size: 13px;
  line-height: 1.45;
  min-height: 19px;
  flex-grow: 1;
}

.card__actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  padding-top: 14px;
  border-top: 1px dashed rgba(18, 20, 16, 0.2);
}

.card__primary,
.card__view {
  flex-grow: 1;
  flex-basis: 0;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  font-size: 14px;
  color: var(--ink-2);
  font-weight: 600;
  position: relative;
}

.card__primary {
  font-weight: 700;
  color: var(--ink);
  border: 1.5px solid rgba(18, 20, 16, 0.25);
  border-radius: 10px;
}

/* 44px touch target on 40px buttons. */
.card__primary::after,
.card__view::after {
  content: '';
  position: absolute;
  inset: -2px 0;
}
</style>
