<script setup>
import { FRIDGE_EXAMPLE, naira } from '@/config/landing'
</script>

<template>
  <section id="how" class="how on-dark" aria-labelledby="how-title">
    <div class="l-wrap how__in">
      <div class="guilloche how__ring d-only" aria-hidden="true"></div>

      <div class="how__head">
        <div class="eyebrow how__eyebrow">HOW IT WORKS</div>
        <h2 id="how-title">
          Nobody pays first. The money waits <span class="serif-accent accent">in the middle.</span>
        </h2>
      </div>

      <div class="track">
        <div class="track__end d-only">
          <span class="track__label">BUYER</span>
          <span class="track__text">Pays into escrow</span>
        </div>
        <div class="track__mid">
          <div class="track__line d-only"></div>
          <div class="track__pill num">{{ naira(FRIDGE_EXAMPLE.price) }} · held</div>
          <div class="track__line d-only"></div>
        </div>
        <div class="track__end track__end--right d-only">
          <span class="track__label">SELLER</span>
          <span class="track__text">Paid on your “yes”</span>
        </div>
      </div>

      <ol class="steps">
        <li class="step">
          <div class="step__num" aria-hidden="true">01</div>
          <div class="step__body">
            <h3>Seller posts it</h3>
            <p>
              Real photos, a fair price, the area it’s in.
              <span class="d-only">We check every listing before it goes live.</span>
              <span class="m-only">Every listing is checked before it goes live.</span>
            </p>
            <div class="frag frag--listing d-only">
              <span class="frag__title">Samsung fridge, 2 doors</span>
              <span class="frag__meta">Surulere · Used 3 yrs</span>
              <span class="frag__price num">{{ naira(FRIDGE_EXAMPLE.price) }}</span>
            </div>
          </div>
        </li>

        <li class="step">
          <div class="step__num" aria-hidden="true">02</div>
          <div class="step__body">
            <h3>Buyer pays us, not them</h3>
            <p>
              <span class="d-only">The money leaves your wallet and sits locked.</span>
              <span class="m-only">The money sits locked.</span>
              The seller can see it’s there. Nobody can touch it.
            </p>
            <div class="frag frag--escrow d-only">
              <span class="frag__escrow-label">IN ESCROW</span>
              <span class="frag__price num">{{ naira(FRIDGE_EXAMPLE.price) }}</span>
            </div>
          </div>
        </li>

        <li class="step">
          <div class="step__num" aria-hidden="true">03</div>
          <div class="step__body">
            <h3>Chat, then meet</h3>
            <p>
              <span class="d-only">Arrange everything in the app. No numbers swapped, and every message is on record.</span>
              <span class="m-only">Arrange it in the app. No numbers swapped, every message on record.</span>
            </p>
            <div class="frag frag--chat d-only">
              <div class="bubble bubble--in">Shoprite Surulere, 4pm?</div>
              <div class="bubble bubble--out">Perfect. See you there</div>
            </div>
          </div>
        </li>

        <li class="step step--last">
          <div class="step__num" aria-hidden="true">04</div>
          <div class="step__body">
            <h3>Check it. Confirm it.</h3>
            <p>
              <span class="d-only">Switch it on, look it over. When you tap confirm, the seller is paid instantly.</span>
              <span class="m-only">Tap confirm with the item in hand and the seller is paid instantly.</span>
            </p>
            <div class="frag frag--release">
              <!-- Illustration of the in-app button, not a control on this page. -->
              <div class="release-btn">Item is good. Release payment</div>
              <span class="frag__receives num d-only">SELLER RECEIVES {{ naira(FRIDGE_EXAMPLE.payout) }}</span>
            </div>
          </div>
        </li>
      </ol>
    </div>
  </section>
</template>

<style scoped>
.how {
  background: var(--forest);
  color: var(--paper);
  overflow: hidden;
}

.how__in {
  padding-block: 140px;
  display: flex;
  flex-direction: column;
  gap: 72px;
  position: relative;
}

.how__ring {
  position: absolute;
  width: 900px;
  height: 900px;
  border-radius: 50%;
  right: -380px;
  top: -380px;
}

.how__head {
  display: flex;
  flex-direction: column;
  gap: 24px;
  max-width: 980px;
  position: relative;
}

.how__eyebrow,
.accent {
  color: var(--accent);
}

h2 {
  margin: 0;
  font-size: clamp(42px, 5.5556vw, 80px);
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.04em;
}

/* ---------- Track ---------- */

.track {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 1.2fr 1fr;
  align-items: center;
  border: 1px solid rgba(243, 237, 224, 0.18);
  border-radius: 20px;
  padding: 36px 48px;
}

.track__end {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.track__end--right {
  align-items: flex-end;
  text-align: right;
}

.track__label {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.14em;
  color: var(--on-forest-muted);
}

.track__text {
  font-size: clamp(20px, 1.9445vw, 28px);
  font-weight: 700;
}

.track__mid {
  display: flex;
  align-items: center;
  gap: 16px;
}

.track__line {
  flex-grow: 1;
  border-top: 2px dashed rgba(243, 237, 224, 0.4);
}

.track__pill {
  background: var(--accent);
  color: var(--ink);
  padding: 16px 24px;
  border-radius: 999px;
  font-size: clamp(18px, 1.8056vw, 26px);
  font-weight: 800;
  letter-spacing: -0.02em;
  white-space: nowrap;
}

/* ---------- Steps ---------- */

.steps {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 32px;
  position: relative;
}

.step,
.step__body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.step {
  border-top: 1px solid rgba(243, 237, 224, 0.25);
  padding-top: 24px;
}

.step__num {
  font-family: var(--font-serif);
  font-size: 96px;
  line-height: 0.8;
  color: var(--accent);
}

h3 {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.step p {
  margin: 0;
  font-size: 17px;
  line-height: 1.55;
  color: var(--on-forest-2);
}

.frag {
  margin-top: 8px;
}

.frag--listing {
  background: var(--paper);
  color: var(--ink);
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.frag__title {
  font-weight: 700;
  font-size: 15px;
}

.frag__meta {
  font-size: 13px;
  color: var(--muted);
}

.frag__price {
  font-weight: 800;
  font-size: 20px;
}

.frag--escrow {
  background: rgba(245, 184, 46, 0.14);
  border: 1.5px solid var(--accent);
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.frag__escrow-label {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.1em;
  color: var(--accent);
}

.frag--chat,
.frag--release {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bubble {
  color: var(--ink);
  padding: 10px 14px;
  font-size: 14px;
}

.bubble--in {
  align-self: flex-start;
  background: var(--paper);
  border-radius: 14px 14px 14px 4px;
}

.bubble--out {
  align-self: flex-end;
  background: var(--accent);
  border-radius: 14px 14px 4px 14px;
  font-weight: 600;
}

.release-btn {
  background: var(--lime);
  color: var(--ink);
  border-radius: 12px;
  padding: 14px 16px;
  font-size: 15px;
  font-weight: 700;
  text-align: left;
}

.frag__receives {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--on-forest-muted);
}

/* 768–1279: steps go 2×2. */
@media (max-width: 1279px) {
  .steps {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    row-gap: 56px;
  }
}

@media (max-width: 1023px) {
  .track {
    padding: 28px 32px;
  }
}

@media (max-width: 767px) {
  .how__in {
    padding-block: 72px;
    gap: 40px;
  }

  .how__head {
    gap: 16px;
  }

  h2 {
    font-size: 42px;
  }

  /* The mobile reference's accent inherits the headline's tracking. */
  .accent {
    letter-spacing: inherit;
  }

  /* Mobile shows only the held pill from the track. */
  .track {
    display: block;
    border: 0;
    border-radius: 0;
    padding: 0;
  }

  .track__mid {
    display: block;
  }

  .track__pill {
    display: inline-block;
    padding: 12px 18px;
    font-size: 20px;
  }

  .steps {
    grid-template-columns: minmax(0, 1fr);
    gap: 28px;
  }

  .step {
    display: grid;
    grid-template-columns: 64px 1fr;
    gap: 12px;
    padding-top: 20px;
  }

  .step__num {
    font-size: 56px;
  }

  .step__body {
    gap: 6px;
  }

  .step--last .step__body {
    gap: 10px;
  }

  h3 {
    font-size: 21px;
    letter-spacing: 0;
  }

  .step p {
    font-size: 16px;
    line-height: 1.5;
  }

  .frag {
    margin-top: 0;
  }

  .release-btn {
    min-height: 48px;
    box-sizing: border-box;
    display: flex;
    align-items: center;
  }
}
</style>
