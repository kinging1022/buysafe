<script setup>
import {
  SOFA_EXAMPLE,
  VENDOR_COMMISSION_PERCENT,
  naira,
} from '@/config/landing'

const points = [
  'No more chasing transfers',
  'No more buyers wasting your trip',
  'Your commission, split and paid automatically',
  'Every client’s listings in one place',
]
</script>

<template>
  <section id="vendors" class="vendors" aria-labelledby="vendors-title">
    <div class="l-wrap vendors__in">
      <div class="vendors__copy">
        <div class="eyebrow vendors__eyebrow">FOR DECLUTTER VENDORS</div>
        <h2 id="vendors-title">
          Run a declutter page? <span class="serif-accent">Bring it here.</span>
        </h2>
        <ol class="points">
          <li v-for="(point, i) in points" :key="point">
            <span>{{ point }}</span>
            <span class="points__num" aria-hidden="true">{{ String(i + 1).padStart(2, '0') }}</span>
          </li>
        </ol>
        <RouterLink to="/vendors/apply" class="apply">Apply as a vendor →</RouterLink>
      </div>

      <figure class="payout" aria-label="Example payout split for a vendor sale">
        <div class="payout__head"><span>PAYOUT SPLIT</span><span>EXAMPLE</span></div>
        <div class="payout__item">3-seater sofa, grey</div>
        <div class="payout__rows num">
          <div class="payout__row">
            <span class="payout__key">Sold for</span>
            <span class="payout__strong">{{ naira(SOFA_EXAMPLE.sale) }}</span>
          </div>
          <div class="payout__row">
            <span class="payout__key">buysafe fee ({{ SOFA_EXAMPLE.rate }})</span>
            <span>− {{ naira(SOFA_EXAMPLE.fee) }}</span>
          </div>
          <div class="payout__row payout__row--held">
            <span>Your commission ({{ VENDOR_COMMISSION_PERCENT }}%)</span>
            <span class="payout__strong">{{ naira(SOFA_EXAMPLE.commission) }}</span>
          </div>
          <div class="payout__dash"></div>
          <div class="payout__row payout__row--total">
            <span class="payout__key">Seller receives</span>
            <span class="payout__total">{{ naira(SOFA_EXAMPLE.sellerReceives) }}</span>
          </div>
        </div>
        <figcaption class="payout__foot">ALL THREE PAID THE MOMENT THE BUYER CONFIRMS</figcaption>
      </figure>
    </div>
  </section>
</template>

<style scoped>
.vendors {
  background: var(--accent);
  color: var(--ink);
}

.vendors__in {
  padding-block: 140px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 500px;
  gap: 96px;
  align-items: center;
}

.vendors__copy {
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.vendors__eyebrow {
  font-weight: 600;
}

h2 {
  margin: 0;
  font-size: clamp(42px, 5.8334vw, 84px);
  line-height: 0.98;
  font-weight: 800;
  letter-spacing: -0.045em;
}

.points {
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
}

.points li {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 0;
  border-top: 1.5px solid rgba(18, 20, 16, 0.35);
  font-size: 21px;
  font-weight: 600;
}

.points li:last-child {
  border-bottom: 1.5px solid rgba(18, 20, 16, 0.35);
}

.points__num {
  font-family: var(--font-mono);
  font-size: 14px;
}

.apply {
  align-self: flex-start;
  text-decoration: none;
  background: var(--ink);
  color: var(--paper);
  font-size: 18px;
  font-weight: 700;
  padding: 18px 28px;
  border-radius: 12px;
  margin-top: 8px;
}

/* ---------- Payout card ---------- */

.payout {
  margin: 0;
  background: var(--ink);
  color: var(--paper);
  border-radius: 20px;
  padding: 36px;
  display: flex;
  flex-direction: column;
  gap: 22px;
  transform: rotate(1.5deg);
}

.payout__head {
  display: flex;
  justify-content: space-between;
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.12em;
  color: #a9a99c;
}

.payout__item {
  font-size: 20px;
  font-weight: 700;
}

.payout__rows {
  display: flex;
  flex-direction: column;
  gap: 14px;
  font-size: 18px;
}

.payout__row {
  display: flex;
  justify-content: space-between;
}

.payout__key {
  color: #c8c8bc;
}

.payout__strong {
  font-weight: 700;
}

.payout__row--held {
  color: var(--accent);
}

.payout__dash {
  border-top: 1.5px dashed rgba(243, 237, 224, 0.3);
}

.payout__row--total {
  align-items: baseline;
}

.payout__total {
  font-size: 36px;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: var(--lime);
}

.payout__foot {
  font-family: var(--font-mono);
  font-size: 12px;
  color: #a9a99c;
}

/* Below 1280 the card no longer fits beside the copy. */
@media (max-width: 1279px) {
  .vendors__in {
    grid-template-columns: minmax(0, 1fr);
    gap: 64px;
  }

  .payout {
    max-width: 500px;
  }
}

@media (max-width: 767px) {
  .vendors__in {
    padding-block: 72px;
    gap: 48px;
  }

  .vendors__copy {
    gap: 20px;
  }

  h2 {
    font-size: 42px;
  }

  .points {
    margin-top: 4px;
  }

  .points li {
    font-size: 18px;
    padding: 16px 0;
  }

  .apply {
    align-self: stretch;
    text-align: center;
    font-size: 17px;
    padding: 17px 20px;
  }

  .payout {
    padding: 24px;
    gap: 18px;
    transform: rotate(0.75deg);
  }

  .payout__rows {
    font-size: 16px;
  }

  .payout__total {
    font-size: 30px;
  }
}
</style>
