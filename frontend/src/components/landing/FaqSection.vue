<script setup>
import { PAYMENT_PARTNER } from '@/config/landing'

const faqs = [
  {
    q: 'Does it work outside Lagos?',
    a: 'Yes, anywhere in Nigeria. Abuja, PH, Ibadan, Enugu, Kano, Benin, anywhere. You meet locally, wherever the item is.',
    open: true,
  },
  { q: 'How do I put money in my wallet?', a: '[FUNDING METHODS: transfer, card, USSD]' },
  { q: 'How fast does the seller get paid?', a: '[PAYOUT TIMING]' },
  {
    q: 'Is my money actually safe with you?',
    a: `Funds are held through ${PAYMENT_PARTNER}, a licensed processor, not in a personal account.`,
  },
  { q: 'What can’t I sell?', a: '[PROHIBITED ITEMS LIST]' },
]
</script>

<template>
  <section class="faq" aria-labelledby="faq-title">
    <div class="l-wrap faq__in">
      <h2 id="faq-title">Questions people ask.</h2>
      <div class="faq__list">
        <details v-for="item in faqs" :key="item.q" :open="item.open">
          <summary>
            <span>{{ item.q }}</span>
            <span class="sign" aria-hidden="true"></span>
          </summary>
          <p>{{ item.a }}</p>
        </details>
      </div>
    </div>
  </section>
</template>

<style scoped>
.faq__in {
  padding-block: 140px;
  display: grid;
  grid-template-columns: 420px minmax(0, 1fr);
  gap: 96px;
}

h2 {
  margin: 0;
  font-size: clamp(42px, 4.4445vw, 64px);
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.faq__list {
  display: flex;
  flex-direction: column;
}

details {
  border-top: 1px solid rgba(18, 20, 16, 0.2);
  padding: 26px 0;
}

details:first-child {
  border-top: 2px solid var(--ink);
}

details:last-child {
  border-bottom: 1px solid rgba(18, 20, 16, 0.2);
}

summary {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  font-size: 24px;
  font-weight: 700;
  /* 44px touch target without moving anything */
  padding-block: 7px;
  margin-block: -7px;
}

/* Sign follows the open state: − when open, + when closed. */
.sign {
  font-family: var(--font-mono);
  font-weight: 400;
}

.sign::before {
  content: '+';
}

details[open] .sign::before {
  content: '−';
}

details p {
  margin: 14px 0 0;
  font-size: 18px;
  line-height: 1.6;
  color: var(--ink-2);
  max-width: 680px;
}

@media (max-width: 1279px) {
  .faq__in {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.6fr);
    gap: 48px;
  }
}

@media (max-width: 1023px) {
  .faq__in {
    grid-template-columns: minmax(0, 1fr);
    gap: 40px;
  }
}

@media (max-width: 767px) {
  .faq__in {
    padding-block: 72px;
    gap: 32px;
  }

  h2 {
    font-size: 42px;
  }

  details {
    padding: 20px 0;
  }

  summary {
    font-size: 19px;
    gap: 16px;
  }

  details p {
    font-size: 16px;
    line-height: 1.55;
  }
}
</style>
