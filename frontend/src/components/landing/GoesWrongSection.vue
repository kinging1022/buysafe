<template>
  <section id="wrong" class="wrong" aria-labelledby="wrong-title">
    <div class="l-wrap wrong__in">
      <div class="wrong__head">
        <div class="wrong__title">
          <div class="eyebrow wrong__eyebrow">IF IT GOES WRONG</div>
          <h2 id="wrong-title">What if the deal goes bad?</h2>
        </div>
        <div class="wrong__aside">We planned for that part first.</div>
      </div>

      <div class="wrong__grid">
        <div class="case">
          <h3>The item isn’t what was posted.</h3>
          <p>
            Don’t confirm. Open a dispute from the chat. Your money stays locked while we review the
            listing, photos and conversation. If it was misrepresented, you get a full refund within
            [X HOURS].
          </p>
        </div>
        <div class="case">
          <h3>The seller never showed up.</h3>
          <p>
            Cancel from the chat and the money goes straight back to your buysafe wallet. Withdraw it
            to your bank whenever you like.
          </p>
        </div>
        <div class="case">
          <h3>The buyer never showed up.</h3>
          <p>
            Your item never left your hands, and their money was already committed before you
            stepped out. [NO-SHOW POLICY].
          </p>
        </div>
        <div class="case">
          <h3>Who decides a dispute?</h3>
          <p>
            A real person on our team, working from the in-app chat record. That’s why every message
            stays inside buysafe.
          </p>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.wrong__in {
  padding-block: 140px;
  display: flex;
  flex-direction: column;
  gap: 64px;
}

.wrong__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 48px;
}

.wrong__title {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.wrong__eyebrow {
  color: var(--muted);
}

h2 {
  margin: 0;
  font-size: clamp(42px, 5.2778vw, 76px);
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.wrong__aside {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: clamp(28px, 2.7778vw, 40px);
  color: var(--muted);
  padding-bottom: 6px;
  white-space: nowrap;
}

.wrong__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 64px;
  row-gap: 56px;
}

.case {
  display: flex;
  flex-direction: column;
  gap: 14px;
  border-top: 2px solid var(--ink);
  padding-top: 24px;
}

h3 {
  margin: 0;
  font-size: clamp(24px, 2.0834vw, 30px);
  font-weight: 700;
  letter-spacing: -0.02em;
}

.case p {
  margin: 0;
  font-size: 18px;
  line-height: 1.6;
  color: var(--ink-2);
}

@media (max-width: 1279px) {
  .wrong__head {
    flex-wrap: wrap;
    row-gap: 20px;
  }

  .wrong__grid {
    column-gap: 48px;
  }
}

@media (max-width: 767px) {
  .wrong__in {
    padding-block: 72px;
    gap: 40px;
  }

  .wrong__title {
    gap: 16px;
  }

  h2 {
    font-size: 42px;
  }

  .wrong__aside {
    font-size: 28px;
    white-space: normal;
    padding-bottom: 0;
  }

  .wrong__grid {
    grid-template-columns: minmax(0, 1fr);
    row-gap: 36px;
  }

  .case {
    gap: 10px;
    padding-top: 20px;
  }

  h3 {
    font-size: 22px;
  }

  .case p {
    font-size: 16px;
    line-height: 1.55;
  }
}
</style>
