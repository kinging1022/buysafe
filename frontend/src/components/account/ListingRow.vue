<script setup>
import { computed } from 'vue'
import { naira } from '@/utils/format'
import { rowDisplay } from './listingDisplay'
import ListingPhoto from './ListingPhoto.vue'
import StatusPill from './StatusPill.vue'

// Mobile row, from design/profile-tab-all-mobile.reference.html: the whole row is one link.
const props = defineProps({
  item: { type: Object, required: true },
  index: { type: Number, default: 0 },
})

const shown = computed(() => rowDisplay(props.item))
</script>

<template>
  <RouterLink :to="shown.to" class="row" :class="{ 'row--sold': item.display_status === 'sold' }">
    <ListingPhoto :src="item.first_image_url" :index="index" small />
    <div class="row__text">
      <StatusPill :status="item.display_status" small class="row__pill" />
      <span class="row__title">{{ item.title }}</span>
      <span class="row__price num">{{ naira(item.price) }}</span>
      <span class="row__line" :style="{ color: shown.color }">{{ shown.line }}</span>
    </div>
  </RouterLink>
</template>

<style scoped>
.row {
  text-decoration: none;
  color: var(--ink);
  background: #ffffff;
  border-radius: 14px;
  padding: 12px;
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 14px;
}

.row:hover {
  opacity: 1;
}

.row--sold,
.row--sold:hover {
  opacity: 0.72;
}

.row__text {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.row__pill {
  align-self: flex-start;
}

.row__title {
  font-size: 16px;
  font-weight: 700;
  margin-top: 2px;
  overflow-wrap: anywhere;
}

.row__price {
  font-size: 19px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.row__line {
  font-size: 12px;
  line-height: 1.4;
}
</style>
