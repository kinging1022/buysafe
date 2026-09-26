<template>
  <figure class="receipt perf" aria-label="Example escrow receipt: PlayStation 5 Slim, ₦280,000 held safe">
    <div class="receipt__head">
      <span>ESCROW RECEIPT</span><span>No. BS-004213</span>
    </div>
    <div class="dash"></div>

    <div class="receipt__item">
      <div class="receipt__photo d-only">PHOTO</div>
      <div class="receipt__item-text">
        <div class="receipt__title">PlayStation 5 Slim</div>
        <div class="receipt__meta">Used · 1 year · Ikeja, Lagos</div>
      </div>
    </div>

    <div class="receipt__amount-wrap">
      <div class="receipt__label d-only">AMOUNT</div>
      <div class="receipt__amount num">₦280,000</div>
      <div class="receipt__stamp">HELD SAFE</div>
    </div>
    <div class="dash"></div>

    <ol class="timeline">
      <li class="row">
        <span class="dot dot--done"></span>
        <span class="row__label row__label--done">Buyer paid</span>
        <span class="row__time">TUE 10:42</span>
      </li>
      <li class="row" aria-current="step">
        <span class="dot dot--held"></span>
        <span class="row__label row__label--held">Held by buysafe</span>
        <span class="row__time row__time--held">NOW</span>
      </li>
      <li class="row row--todo">
        <span class="dot dot--todo"></span>
        <span class="row__label">Met &amp; checked<span class="d-only"> the item</span></span>
        <span class="row__time d-only">—</span>
      </li>
      <li class="row row--todo">
        <span class="dot dot--todo"></span>
        <span class="row__label">Released to seller</span>
        <span class="row__time d-only">—</span>
      </li>
    </ol>
  </figure>
</template>

<style scoped>
.receipt {
  margin: 0;
  flex-shrink: 0;
  width: 430px;
  background: var(--paper);
  color: var(--ink);
  padding: 30px 32px 36px;
  transform: rotate(-2.5deg);
  box-shadow: 0 30px 60px rgba(0, 0, 0, 0.28);
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.receipt__head {
  display: flex;
  justify-content: space-between;
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.12em;
  color: var(--muted);
}

.receipt__item {
  display: flex;
  gap: 16px;
  align-items: center;
}

.receipt__photo {
  width: 64px;
  height: 64px;
  border-radius: 8px;
  background: #e4dbc6;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--muted);
}

.receipt__item-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.receipt__title {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.receipt__meta {
  font-size: 14px;
  color: var(--muted);
}

.receipt__amount-wrap {
  position: relative;
}

.receipt__label {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.12em;
  color: var(--muted);
}

.receipt__amount {
  font-size: 60px;
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 1.05;
}

.receipt__stamp {
  position: absolute;
  right: -6px;
  top: 4px;
  transform: rotate(9deg);
  border: 3px solid var(--amber-ink);
  outline: 1.5px solid var(--amber-ink);
  outline-offset: 3px;
  color: var(--amber-ink);
  font-family: var(--font-mono);
  font-weight: 600;
  font-size: 20px;
  letter-spacing: 0.14em;
  padding: 6px 12px;
  border-radius: 4px;
  opacity: 0.92;
}

.timeline {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 14px;
  font-size: 15px;
}

.row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.row--todo {
  color: var(--muted);
}

.dot {
  border-radius: 50%;
}

.dot--done {
  width: 14px;
  height: 14px;
  background: var(--released);
}

.dot--held {
  width: 14px;
  height: 14px;
  background: var(--accent);
  box-shadow: 0 0 0 5px rgba(245, 184, 46, 0.3);
}

.dot--todo {
  width: 12px;
  height: 12px;
  border: 1.5px solid #8c8e85;
}

.row__label {
  flex-grow: 1;
}

.row__label--done {
  font-weight: 600;
}

.row__label--held {
  font-weight: 700;
}

.row__time {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--muted);
}

.row--todo .row__time {
  color: inherit;
}

.row__time--held {
  color: var(--amber-ink);
}

/* 1024–1279: the receipt sits beside the copy at 80% so it fits its column. */
@media (min-width: 1024px) and (max-width: 1279px) {
  .receipt {
    transform: rotate(-2.5deg) scale(0.8);
    transform-origin: 50% 0;
  }
}

@media (max-width: 767px) {
  /* Mobile reference lets the receipt shrink to its column. */
  .receipt {
    flex-shrink: 1;
    width: 330px;
    padding: 22px 22px 28px;
    transform: rotate(-2deg);
    box-shadow: 0 24px 48px rgba(0, 0, 0, 0.28);
    gap: 16px;
  }

  .receipt__head {
    font-size: 10px;
  }

  .receipt__item-text {
    gap: 2px;
  }

  .receipt__title {
    font-size: 18px;
    letter-spacing: 0;
  }

  .receipt__meta {
    font-size: 13px;
  }

  .receipt__amount {
    font-size: 46px;
  }

  .receipt__stamp {
    right: -4px;
    top: -6px;
    transform: rotate(10deg);
    border-width: 2.5px;
    outline-offset: 2px;
    font-size: 14px;
    letter-spacing: 0.12em;
    padding: 4px 8px;
    border-radius: 3px;
    opacity: 1;
  }

  .timeline {
    gap: 11px;
    font-size: 14px;
  }

  .row {
    gap: 10px;
  }

  .dot--done,
  .dot--held {
    width: 12px;
    height: 12px;
  }

  .dot--held {
    box-shadow: 0 0 0 4px rgba(245, 184, 46, 0.3);
  }

  .dot--todo {
    width: 10px;
    height: 10px;
  }

  .row__time {
    font-size: 11px;
  }
}
/* Very narrow phones: keep the amount clear of the HELD SAFE stamp. */
@media (max-width: 379px) {
  .receipt__amount {
    font-size: 40px;
  }
}
</style>
