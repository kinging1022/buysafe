<script setup>
import { FEE_EXAMPLE, FEE_TIERS, naira } from '@/config/landing'
</script>

<template>
  <section id="fees" class="fees" aria-labelledby="fees-title">
    <div class="l-wrap fees__in">
      <div class="fees__copy">
        <div class="eyebrow fees__eyebrow">FEES</div>
        <h2 id="fees-title">One fee. <span class="serif-accent released">Only when it sells.</span></h2>
        <p>
          We take a fee from the seller when a deal completes, set by the price. Buyers pay nothing
          extra. If the deal doesn’t happen, we don’t earn.
        </p>

        <div class="tiers-block">
          <div id="fees-tiers" class="tiers__label">FEE BY SELLING PRICE</div>
          <dl class="tiers num" aria-labelledby="fees-tiers">
            <div v-for="tier in FEE_TIERS" :key="tier.key" class="tiers__row">
              <dt>{{ tier.label }}</dt>
              <dd>{{ tier.short_label }}</dd>
            </div>
          </dl>
        </div>
      </div>

      <dl class="maths num">
        <div class="maths__row maths__row--first">
          <dt>Item sells for</dt>
          <dd class="maths__amount">{{ naira(FEE_EXAMPLE.price) }}</dd>
        </div>
        <div class="maths__row">
          <dt>buysafe fee ({{ FEE_EXAMPLE.rate_label }})</dt>
          <dd class="maths__amount maths__amount--fee">− {{ naira(FEE_EXAMPLE.fee) }}</dd>
        </div>
        <div class="maths__row maths__row--total">
          <dt>Seller gets</dt>
          <dd class="maths__total">{{ naira(FEE_EXAMPLE.payout) }}</dd>
        </div>
      </dl>
    </div>
  </section>
</template>

<style scoped>
.fees__in {
  padding-block: 140px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 96px;
  /* Both columns end on the same line: the tier list and "Seller gets". */
  align-items: end;
}

.fees__copy {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.fees__eyebrow {
  color: var(--muted);
}

h2 {
  margin: 0;
  font-size: clamp(42px, 5.8334vw, 84px);
  line-height: 0.98;
  font-weight: 800;
  letter-spacing: -0.045em;
}

.released {
  color: var(--released);
}

.fees__copy p {
  margin: 0;
  font-size: 20px;
  line-height: 1.55;
  color: var(--ink-2);
  max-width: 520px;
}

/* Fee by price: the maths rows' rules at body size, so both columns read as one system. */
.tiers-block {
  margin-top: 8px;
  max-width: 520px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tiers__label {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.14em;
  color: var(--muted);
}

.tiers {
  margin: 0;
  display: flex;
  flex-direction: column;
  border-top: 2px solid var(--ink);
  border-bottom: 1px solid rgba(18, 20, 16, 0.2);
}

.tiers__row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 16px;
  padding: 14px 0;
  font-size: 18px;
}

.tiers__row + .tiers__row {
  border-top: 1px solid rgba(18, 20, 16, 0.2);
}

.tiers dt {
  color: var(--ink-2);
}

.tiers dd {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--amber-ink);
  white-space: nowrap;
}

.maths {
  margin: 0;
  display: flex;
  flex-direction: column;
  font-size: 22px;
}

.maths__row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 16px;
  padding: 22px 0;
  border-top: 1px solid rgba(18, 20, 16, 0.2);
}

.maths__row--first {
  border-top: 2px solid var(--ink);
}

.maths__row--total {
  padding: 26px 0 0;
  border-top: 2px solid var(--ink);
}

dt {
  color: var(--ink-2);
}

.maths__row--total dt {
  color: var(--ink);
  font-weight: 700;
}

dd {
  margin: 0;
}

.maths__amount {
  font-size: 40px;
  font-weight: 700;
  letter-spacing: -0.03em;
}

.maths__amount--fee {
  color: var(--amber-ink);
}

.maths__total {
  font-size: clamp(64px, 7.2223vw, 104px);
  font-weight: 800;
  letter-spacing: -0.05em;
  line-height: 1;
  color: var(--released);
}

@media (max-width: 1023px) {
  .fees__in {
    grid-template-columns: minmax(0, 1fr);
    gap: 56px;
  }

  /* Stacked: the tier list spans the same width as the example below it. */
  .tiers-block {
    max-width: none;
  }
}

@media (max-width: 767px) {
  .fees__in {
    padding-block: 72px;
    gap: 40px;
  }

  .fees__copy {
    gap: 20px;
  }

  h2 {
    font-size: 42px;
  }

  .fees__copy p {
    font-size: 17px;
  }

  .tiers-block {
    margin-top: 4px;
    gap: 10px;
  }

  .tiers__label {
    font-size: 11px;
    letter-spacing: 0.12em;
  }

  .tiers__row {
    padding: 12px 0;
    font-size: 16px;
  }

  .tiers dd {
    font-size: 19px;
  }

  .maths {
    font-size: 17px;
  }

  .maths__row {
    padding: 18px 0;
  }

  .maths__amount {
    font-size: 28px;
  }

  .maths__row--total {
    padding: 22px 0 0;
  }

  .maths__total {
    font-size: 56px;
  }
}
</style>
