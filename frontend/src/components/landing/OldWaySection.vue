<template>
  <section class="old" aria-labelledby="old-title">
    <div class="l-wrap old__in">
      <div class="old__copy">
        <div class="eyebrow old__eyebrow">THE OLD WAY</div>
        <h2 id="old-title">Somebody always has to go first.</h2>
        <div class="old__lose">And sometimes they lose.</div>
        <div class="old__cols">
          <div class="old__col">
            <div class="old__col-title">If you’re buying</div>
            <p>
              You send the transfer, they send a “received.” Then the photos stop matching, or the
              number stops going through.
            </p>
          </div>
          <div class="old__col">
            <div class="old__col-title">If you’re selling</div>
            <p>
              You clean it, pack it, cross Lagos traffic to meet — and the buyer “is on the way” for
              two hours before going quiet.
            </p>
          </div>
        </div>
      </div>

      <figure class="dm" aria-label="Example Instagram DM thread that ends with the money gone">
        <div class="dm__head">
          <div class="dm__avatar"></div>
          <div class="dm__who"><span class="dm__name">declutter_by_tee</span><span class="dm__src">Instagram DM</span></div>
        </div>
        <div class="msg msg--out">Is the air fryer still available?</div>
        <div class="msg msg--in">Yes dear. Send ₦45,000 to confirm, I’ll dispatch today.</div>
        <div class="msg msg--out">Sent. Check your alert</div>
        <div class="dm__seen">Seen 2:14 PM</div>
        <div class="msg msg--out">Hello? Any update on dispatch?</div>
        <div class="dm__system">This account is no longer available</div>
        <div class="dm__gone"><span class="naira">₦</span>45,000, gone.</div>
      </figure>
    </div>
  </section>
</template>

<style scoped>
.old__in {
  padding-block: 140px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 520px;
  gap: 96px;
  align-items: center;
}

.old__copy {
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.old__eyebrow {
  color: var(--muted);
}

h2 {
  margin: 0;
  font-size: clamp(42px, 5.2778vw, 76px);
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.old__lose {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: clamp(30px, 3.3334vw, 48px);
  line-height: 1.1;
  color: var(--muted);
}

.old__cols {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 40px;
  margin-top: 16px;
}

.old__col {
  display: flex;
  flex-direction: column;
  gap: 10px;
  border-top: 2px solid var(--ink);
  padding-top: 18px;
}

.old__col-title {
  font-size: 20px;
  font-weight: 700;
}

.old__col p {
  margin: 0;
  font-size: 17px;
  line-height: 1.55;
  color: var(--ink-2);
}

/* ---------- DM card ---------- */

.dm {
  margin: 0;
  background: #ffffff;
  border-radius: 20px;
  padding: 28px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  box-shadow:
    0 1px 0 rgba(18, 20, 16, 0.08),
    0 20px 50px rgba(18, 20, 16, 0.08);
  font-size: 16px;
}

.dm__head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(18, 20, 16, 0.1);
}

.dm__avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #e4dbc6;
}

.dm__who {
  display: flex;
  flex-direction: column;
}

.dm__name {
  font-weight: 700;
}

.dm__src {
  font-size: 13px;
  color: var(--muted);
}

.msg {
  padding: 12px 16px;
  max-width: 300px;
}

.msg--out {
  align-self: flex-end;
  background: var(--ink);
  color: var(--paper);
  border-radius: 16px 16px 4px 16px;
}

.msg--in {
  align-self: flex-start;
  background: #efe9dc;
  border-radius: 16px 16px 16px 4px;
}

.dm__seen {
  align-self: flex-end;
  font-size: 12px;
  color: var(--muted);
  font-family: var(--font-mono);
}

.dm__system {
  align-self: center;
  margin-top: 8px;
  font-size: 14px;
  color: var(--muted);
  background: var(--paper);
  padding: 8px 14px;
  border-radius: 999px;
}

.dm__gone {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 30px;
  color: var(--loss);
  align-self: flex-start;
  transform: rotate(-3deg);
  margin-top: 6px;
}

/* The 520px card leaves too little room for the copy below 1280. */
@media (max-width: 1279px) {
  .old__in {
    grid-template-columns: minmax(0, 1fr);
    gap: 64px;
  }

  .dm {
    max-width: 520px;
  }
}

@media (max-width: 767px) {
  .old__in {
    padding-block: 72px;
    gap: 40px;
  }

  .old__copy {
    gap: 20px;
  }

  h2 {
    font-size: 42px;
  }

  .old__lose {
    font-size: 32px;
  }

  .old__cols {
    grid-template-columns: minmax(0, 1fr);
    gap: 28px;
    margin-top: 8px;
  }

  .old__col p {
    font-size: 16px;
    line-height: 1.5;
  }

  .dm {
    padding: 20px;
    border-radius: 16px;
  }

  .msg {
    max-width: 260px;
  }

  .dm__gone {
    font-size: 28px;
  }
}
</style>
