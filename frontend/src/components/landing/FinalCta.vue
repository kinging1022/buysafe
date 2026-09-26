<script setup>
import { BUSINESS_NAME, CONTACT_EMAIL, PAYMENT_PARTNER, WHATSAPP_NUMBER } from '@/config/landing'

const year = new Date().getFullYear()
// Placeholders aren't real destinations yet, so they link nowhere useful.
const isPlaceholder = (v) => v.startsWith('[')
const waHref = isPlaceholder(WHATSAPP_NUMBER) ? '#' : `https://wa.me/${WHATSAPP_NUMBER.replace(/\D/g, '')}`
const mailHref = isPlaceholder(CONTACT_EMAIL) ? '#' : `mailto:${CONTACT_EMAIL}`
</script>

<template>
  <div class="final on-dark">
    <div class="l-wrap final__in">
      <div class="guilloche final__ring" aria-hidden="true"></div>

      <section class="final__cta" aria-labelledby="final-title">
        <h2 id="final-title">
          Nobody goes<span class="final__accent">first anymore.</span>
        </h2>
        <div class="final__ctas">
          <RouterLink to="/listings" class="btn btn--accent">Browse items →</RouterLink>
          <RouterLink to="/sell" class="btn btn--outline">Sell something</RouterLink>
        </div>
      </section>

      <footer class="footer">
        <div class="footer__brand">
          <span class="footer__wordmark">buysafe<span class="footer__dot">.</span></span>
          <span class="footer__desc">Escrow for second-hand deals, anywhere in Nigeria.</span>
          <span class="footer__partner">PAYMENTS PROCESSED BY {{ PAYMENT_PARTNER }}</span>
        </div>
        <nav class="footer__col" aria-label="Product">
          <span class="footer__head">PRODUCT</span>
          <RouterLink to="/listings">Browse items</RouterLink>
          <RouterLink to="/sell">Sell something</RouterLink>
          <a href="#vendors">For vendors</a>
        </nav>
        <nav class="footer__col" aria-label="Trust">
          <span class="footer__head">TRUST</span>
          <a href="#wrong">Disputes</a>
          <a href="#meet">Meeting safely</a>
          <RouterLink to="/terms">Terms &amp; privacy</RouterLink>
        </nav>
        <div class="footer__col">
          <span class="footer__head">TALK TO US</span>
          <a :href="waHref">WhatsApp {{ WHATSAPP_NUMBER }}</a>
          <a :href="mailHref">{{ CONTACT_EMAIL }}</a>
          <span class="footer__copy">© {{ year }} {{ BUSINESS_NAME }}</span>
        </div>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.final {
  background: var(--forest);
  color: var(--paper);
  overflow: hidden;
}

.final__in {
  padding-top: 140px;
  padding-bottom: 56px;
  display: flex;
  flex-direction: column;
  gap: 56px;
  position: relative;
}

.final__ring {
  position: absolute;
  width: 1100px;
  height: 1100px;
  border-radius: 50%;
  left: -420px;
  bottom: -640px;
}

.final__cta {
  display: flex;
  flex-direction: column;
  gap: 40px;
  position: relative;
}

h2 {
  margin: 0;
  font-size: clamp(64px, 10.4167vw, 150px);
  line-height: 0.9;
  font-weight: 800;
  letter-spacing: -0.055em;
}

.final__accent {
  display: block;
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 400;
  letter-spacing: -0.02em;
  color: var(--accent);
}

.final__ctas {
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

/* ---------- Footer ---------- */

.footer {
  margin-top: auto;
  position: relative;
  border-top: 1px solid rgba(243, 237, 224, 0.2);
  padding-top: 40px;
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr;
  gap: 48px;
  font-size: 15px;
}

.footer__brand,
.footer__col {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.footer__wordmark {
  font-size: 30px;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.footer__dot {
  color: var(--accent);
}

.footer__desc {
  color: var(--on-forest-muted);
  max-width: 320px;
  line-height: 1.5;
}

.footer__partner {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--on-forest-muted);
  margin-top: 12px;
}

.footer__head {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.12em;
  color: var(--on-forest-muted);
}

/* 44px hit area on footer links without changing the spacing. */
.footer__col a {
  text-decoration: none;
  padding-block: 12px;
  margin-block: -12px;
}

.footer__copy {
  color: var(--on-forest-muted);
}

@media (max-width: 1023px) {
  .footer {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    row-gap: 40px;
  }
}

@media (max-width: 767px) {
  .final__in {
    padding-top: 72px;
    padding-bottom: 40px;
    gap: 56px;
  }

  .final__ring {
    width: 640px;
    height: 640px;
    left: -300px;
    bottom: -380px;
  }

  /* ~64px, but small enough to keep "Nobody goes" on one line. */
  h2 {
    font-size: min(64px, 15.5vw);
  }

  .final__ctas {
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

  .footer {
    grid-template-columns: minmax(0, 1fr);
    gap: 32px;
  }
}
</style>
