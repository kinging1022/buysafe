<script setup>
import { PAYMENT_PARTNER } from '@/config/landing'
import EscrowReceipt from './EscrowReceipt.vue'
</script>

<template>
  <section class="hero on-dark" aria-labelledby="hero-title">
    <div class="l-wrap hero__in">
      <div class="hero__copy">
        <div class="eyebrow hero__eyebrow">
          <span class="d-only">THE PRE-OWNED MARKETPLACE · ALL 36 STATES + FCT</span>
          <span class="m-only">PRE-OWNED MARKETPLACE · ALL OF NIGERIA</span>
        </div>
        <h1 id="hero-title">
          <!-- Kept on one line: the spaces between spans matter on mobile. -->
          Buy and <span class="line">sell used</span> <span class="line">items <span class="serif-accent safely">safely.</span></span>
        </h1>
        <p class="hero__sub">
          Buy and sell used things anywhere in Nigeria without the “send money first” wahala.
          <span class="d-only">You meet, check the item and say it’s good before the seller gets paid.</span>
          <span class="m-only">The seller gets paid only after you meet, check and confirm.</span>
        </p>
        <div class="hero__ctas">
          <RouterLink to="/listings" class="btn btn--accent">Browse items →</RouterLink>
          <RouterLink to="/sell" class="btn btn--outline">Sell something</RouterLink>
        </div>
        <ul class="hero__trust">
          <li>✓ Phone-verified users</li>
          <li>✓ Chat stays in-app</li>
          <li>✓ Payments held by {{ PAYMENT_PARTNER }}</li>
        </ul>
      </div>

      <div class="hero__art">
        <div class="guilloche ring ring--1" aria-hidden="true"></div>
        <div class="guilloche2 ring ring--2 d-only" aria-hidden="true"></div>
        <EscrowReceipt />
      </div>
    </div>
  </section>
</template>

<style scoped>
.hero {
  background: var(--forest);
  color: var(--paper);
  position: relative;
}

.hero__in {
  padding-top: 72px;
  padding-bottom: 120px;
  display: grid;
  /* 780px / 420px at 1440, scaling proportionally below. */
  grid-template-columns: minmax(0, 780fr) minmax(0, 420fr);
  gap: 48px;
  position: relative;
}

.hero__copy {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.hero__eyebrow {
  color: var(--accent);
}

h1 {
  margin: 0;
  font-size: clamp(60px, 6.5278vw, 94px);
  line-height: 0.95;
  font-weight: 800;
  letter-spacing: -0.045em;
}

.line {
  display: block;
}

.safely {
  color: var(--accent);
}

.hero__sub {
  margin: 0;
  font-size: 21px;
  line-height: 1.5;
  color: var(--on-forest);
  max-width: 600px;
}

.hero__ctas {
  display: flex;
  gap: 14px;
}

.btn {
  text-decoration: none;
  font-size: 18px;
  border-radius: 12px;
}

.btn--accent {
  background: var(--accent);
  color: var(--ink);
  font-weight: 700;
  padding: 18px 28px;
}

.btn--outline {
  color: var(--paper);
  font-weight: 600;
  padding: 17px 27px;
  border: 1.5px solid rgba(243, 237, 224, 0.5);
}

.hero__trust {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  gap: 28px;
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--on-forest-muted);
  letter-spacing: 0.02em;
  flex-wrap: wrap;
  row-gap: 8px;
}

.hero__trust li {
  white-space: nowrap;
}

.hero__art {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding-top: 8px;
}

.ring {
  position: absolute;
  border-radius: 50%;
}

.ring--1 {
  width: 560px;
  height: 560px;
  top: -20px;
  left: 50%;
  margin-left: -280px;
}

.ring--2 {
  width: 380px;
  height: 380px;
  top: 260px;
  left: 50%;
  margin-left: -40px;
}

/* At full width, the reference's exact columns (the receipt overflows its
   1fr column slightly, as in the reference). */
@media (min-width: 1440px) {
  .hero__in {
    grid-template-columns: 780px 1fr;
  }
}

/* 1024–1279: a fixed column for the receipt (shown at 80%). */
@media (min-width: 1024px) and (max-width: 1279px) {
  .hero__in {
    grid-template-columns: minmax(0, 1fr) 420px;
  }
}

/* Below 1024px the receipt no longer fits beside the copy, so it stacks. */
@media (max-width: 1023px) {
  .hero__in {
    grid-template-columns: minmax(0, 1fr);
    gap: 64px;
  }
}

@media (max-width: 767px) {
  .hero {
    overflow: hidden;
  }

  /* Mobile hero is airier than the 390 reference. The headline is sized so
     its last, longest line ("items safely.") spans the column, keeping the
     stepped shape. */
  .hero__in {
    padding-top: 48px;
    padding-bottom: 64px;
    gap: 32px;
  }

  .hero__copy {
    gap: 28px;
  }

  h1 {
    font-size: clamp(48px, 17.5vw, 76px);
    line-height: 0.98;
  }

  /* Smaller than the headline by about the desktop's ratio, with extra room
     above so the two read as separate levels. */
  .hero__sub {
    font-size: 15px;
    line-height: 1.6;
    margin-top: 8px;
    max-width: 34ch;
  }

  .hero__ctas {
    flex-direction: column;
    gap: 12px;
  }

  .btn {
    font-size: 17px;
    text-align: center;
  }

  .btn--accent {
    padding: 17px 20px;
  }

  .btn--outline {
    padding: 16px 20px;
  }

  .hero__trust {
    gap: 16px;
    font-size: 12px;
    letter-spacing: 0;
  }

  .hero__art {
    padding: 0 0 8px;
  }

  .ring--1 {
    width: 440px;
    height: 440px;
    top: -30px;
    margin-left: -220px;
  }
}
</style>
