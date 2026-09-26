<template>
  <div class="receipt perf" role="img" aria-label="Escrow receipt: PlayStation 5 Slim, ₦280,000, held safe">
    <div class="receipt__head"><span>ESCROW RECEIPT</span><span>No. BS-004213</span></div>
    <div class="dash"></div>
    <div class="receipt__item">PlayStation 5 Slim</div>
    <div class="receipt__amount">₦280,000</div>
    <div class="stamp">HELD SAFE</div>
  </div>
</template>

<style scoped>
.receipt {
  width: 400px;
  background: var(--paper);
  color: var(--ink);
  padding: 24px 26px 30px;
  transform: rotate(-2deg);
  box-shadow: 0 24px 50px rgba(0, 0, 0, 0.28);
  display: flex;
  flex-direction: column;
  gap: 14px;
  position: relative;
}

.receipt__head {
  display: flex;
  justify-content: space-between;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--muted);
}

.receipt__item {
  font-size: 16px;
  font-weight: 700;
}

.receipt__amount {
  font-size: 44px;
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.stamp {
  position: absolute;
  right: 18px;
  top: 64px;
  transform: rotate(9deg);
  border: 3px solid var(--amber-ink);
  outline: 1.5px solid var(--amber-ink);
  outline-offset: 3px;
  color: var(--amber-ink);
  font-family: var(--font-mono);
  font-weight: 600;
  font-size: 17px;
  letter-spacing: 0.14em;
  padding: 5px 10px;
  border-radius: 4px;
  opacity: 0.92;
}
</style>
