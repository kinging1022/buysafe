<script setup>
// "How questions work" (design/qa-buyer-1-answered-desktop, right column).
// On mobile it sits under the Questions title, a little smaller.
defineProps({
  sellerName: { type: String, required: true },
  compact: { type: Boolean, default: false },
})
</script>

<template>
  <div class="how" :class="{ 'how--m': compact }">
    <span class="how__h">HOW QUESTIONS WORK</span>
    <div class="how__row"><span class="how__n">1</span><span>Only {{ sellerName }} can answer, once per question.</span></div>
    <div class="how__row"><span class="how__n">2</span><span>Until it’s answered, only you and {{ sellerName }} see your question.</span></div>
    <div class="how__row"><span class="how__n">3</span><span>No phone numbers, emails, links or @handles.</span></div>
    <div class="how__row how__row--last"><span class="how__n">4</span><span>Up to 3 questions per listing per day. Private chat opens after you pay.</span></div>
  </div>
</template>

<style scoped>
.how {
  display: flex;
  flex-direction: column;
}

.how__h {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: var(--muted);
  padding-bottom: 10px;
  border-bottom: 2px solid var(--ink);
}

.how__row {
  display: grid;
  grid-template-columns: 26px 1fr;
  gap: 10px;
  padding: 14px 0;
  border-bottom: 1px solid rgba(18, 20, 16, 0.15);
  font-size: 14px;
  line-height: 1.5;
}

.how__row--last {
  border-bottom: 0;
}

.how__n {
  font-family: var(--font-serif);
  font-size: 22px;
  line-height: 1;
  color: var(--amber-ink);
}

/* Mobile: no second heavy rule under the section title; tighter rows. */
.how--m .how__h {
  font-size: 10px;
  padding-bottom: 6px;
  border-bottom-width: 1px;
  border-bottom-color: rgba(18, 20, 16, 0.15);
}

.how--m .how__row {
  grid-template-columns: 22px 1fr;
  gap: 8px;
  padding: 10px 0;
  font-size: 13px;
}

.how--m .how__n {
  font-size: 19px;
}
</style>
