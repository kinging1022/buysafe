<script setup>
import { computed } from 'vue'
import { conditionLabel } from '@/config/listing'
import { stateLabel } from '@/config/states'
import { naira, shortAgo } from '@/utils/format'
import ListingPhoto from '@/components/account/ListingPhoto.vue'
import UserAvatar from '@/components/account/UserAvatar.vue'

// A live listing in the browse grid (browse-*.reference.html). Desktop shows
// "{area}, {state}" and the seller; mobile shows "{area}" only.
const props = defineProps({
  item: { type: Object, required: true },
  index: { type: Number, default: 0 },
})

const when = computed(() => shortAgo(props.item.created_at))
const place = computed(() => [props.item.area, stateLabel(props.item.state)].filter(Boolean).join(', '))
const seller = computed(() => props.item.seller)
</script>

<template>
  <RouterLink :to="`/listings/${item.id}`" class="bcard">
    <ListingPhoto :src="item.cover_url" :index="index" class="bcard__photo">
      <span class="bcard__pill">{{ conditionLabel(item.condition).toUpperCase() }}</span>
    </ListingPhoto>
    <div class="bcard__body">
      <span class="bcard__price num">{{ naira(item.price) }}</span>
      <span class="bcard__title">{{ item.title }}</span>
      <span class="bcard__meta bcard__meta--d">{{ [place, when].filter(Boolean).join(' · ') }}</span>
      <span class="bcard__meta bcard__meta--m">{{ [item.area, when].filter(Boolean).join(' · ') }}</span>
      <div class="bcard__seller">
        <UserAvatar
          :first-name="seller.first_name"
          :last-name="seller.last_initial"
          :color="seller.avatar_color"
          :size="28"
          :font-size="11"
        />
        <span class="bcard__name">{{ seller.first_name }} {{ seller.last_initial }}.</span>
        <span class="bcard__verified">✓ VERIFIED</span>
      </div>
    </div>
  </RouterLink>
</template>

<style scoped>
.bcard {
  text-decoration: none;
  color: var(--ink);
  background: #ffffff;
  border-radius: 16px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 1px 0 rgba(18, 20, 16, 0.06);
  min-width: 0;
}

.bcard:hover {
  opacity: 1;
  color: var(--ink);
}

.bcard .bcard__photo {
  height: 240px;
}

.bcard__pill {
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
  color: var(--ink);
}

.bcard__body {
  padding: 18px 20px 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex-grow: 1;
}

.bcard__price {
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.05;
}

.bcard__title {
  font-size: 17px;
  font-weight: 600;
  overflow-wrap: anywhere;
}

.bcard__meta {
  font-size: 14px;
  color: var(--muted);
}

.bcard__meta--m {
  display: none;
}

.bcard__seller {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px dashed rgba(18, 20, 16, 0.2);
}

/* Keep the reference's 10px above the rule when cards in a row match heights. */
.bcard__meta--d {
  margin-bottom: 10px;
}

.bcard__name {
  font-size: 14px;
  font-weight: 600;
}

.bcard__verified {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: var(--released);
  white-space: nowrap;
}

@media (max-width: 767px) {
  .bcard {
    border-radius: 14px;
    box-shadow: none;
  }

  .bcard .bcard__photo {
    height: 150px;
  }

  .bcard__photo :deep(.photo__label) {
    font-size: 9px;
  }

  .bcard__pill {
    left: 8px;
    bottom: 8px;
    font-size: 9px;
    letter-spacing: 0.08em;
    padding: 4px 7px;
  }

  .bcard__body {
    padding: 12px;
    gap: 3px;
  }

  .bcard__price {
    font-size: 19px;
    letter-spacing: -0.02em;
    line-height: normal;
  }

  .bcard__title {
    font-size: 14px;
    line-height: 1.3;
  }

  .bcard__meta {
    font-size: 12px;
  }

  .bcard__meta--d,
  .bcard__seller {
    display: none;
  }

  .bcard__meta--m {
    display: inline;
  }
}
</style>
