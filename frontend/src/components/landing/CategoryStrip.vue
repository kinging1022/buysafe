<script setup>
const categories = [
  'Phones',
  'Fridges',
  'Sofas',
  'Laptops',
  'Generators',
  'Baby things',
  'Wardrobes',
  'Consoles',
  'Bikes',
  'Standing fans',
  'TVs',
]
// The mobile reference shows the first five only.
const MOBILE_COUNT = 5
</script>

<template>
  <div class="strip">
    <p class="l-wrap strip__in">
      <template v-for="(cat, i) in categories" :key="cat">
        <span v-if="i > 0" class="slash" :class="{ 'd-only': i >= MOBILE_COUNT }" aria-hidden="true">/</span>
        <span :class="{ 'd-only': i >= MOBILE_COUNT }">{{ cat }}</span>
      </template>
    </p>
  </div>
</template>

<style scoped>
.strip {
  background: var(--accent);
  color: var(--ink);
}

.strip__in {
  margin-block: 0;
  height: 72px;
  display: flex;
  align-items: center;
  gap: 28px;
  white-space: nowrap;
  overflow: hidden;
  padding-right: 0;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.slash {
  opacity: 0.45;
}

@media (max-width: 767px) {
  .strip__in {
    height: 56px;
    gap: 18px;
    font-size: 21px;
  }
}
</style>
