<script setup>
const rules = [
  ['Meet in public.', 'A mall, a bank, a busy junction. Daylight if you can.'],
  ['Bring someone.', 'A friend, a sibling, anybody. Two is safer than one.'],
  ['Test it right there.', 'Switch it on. Check the IMEI. Open the fridge.'],
  ['Never confirm unseen.', 'Confirm releases the money. Only tap it with the item in hand.'],
  ['Keep the chat in-app.', 'It’s your evidence if anything goes sideways.'],
]
</script>

<template>
  <section id="meet" class="meet" aria-labelledby="meet-title">
    <div class="l-wrap meet__in">
      <div class="meet__head">
        <h2 id="meet-title">Meet like you mean it.</h2>
        <span class="meet__verified">EVERY USER IS PHONE-VERIFIED</span>
      </div>
      <ol class="rules">
        <li v-for="([title, body], i) in rules" :key="title" class="rule">
          <span class="rule__label">RULE {{ i + 1 }}</span>
          <span class="rule__title">{{ title }}</span>
          <span class="rule__body">{{ body }}</span>
        </li>
      </ol>
    </div>
  </section>
</template>

<style scoped>
.meet {
  background: var(--paper-deep);
}

.meet__in {
  padding-block: 100px;
  display: flex;
  flex-direction: column;
  gap: 48px;
}

.meet__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

h2 {
  margin: 0;
  font-size: clamp(40px, 3.8889vw, 56px);
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.meet__verified {
  font-family: var(--font-mono);
  font-size: 13px;
  letter-spacing: 0.1em;
  color: var(--muted);
}

.rules {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 28px;
}

.rule {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.rule__label {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--amber-ink);
  font-weight: 600;
}

.rule__title {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.25;
}

.rule__body {
  font-size: 16px;
  line-height: 1.5;
  color: var(--ink-2);
}

/* 768–1279: 3 + 2 */
@media (max-width: 1279px) {
  .rules {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    row-gap: 40px;
  }
}

@media (max-width: 767px) {
  .meet__in {
    padding-block: 72px;
    gap: 36px;
  }

  .meet__head {
    flex-direction: column;
    align-items: flex-start;
    gap: 14px;
  }

  h2 {
    font-size: 42px;
  }

  .meet__verified {
    font-size: 11px;
  }

  .rules {
    grid-template-columns: minmax(0, 1fr);
    gap: 28px;
  }
}
</style>
