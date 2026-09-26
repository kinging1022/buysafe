<template>
  <section class="founder" aria-labelledby="founder-title">
    <div class="l-wrap founder__in">
      <h2 id="founder-title" class="eyebrow founder__label">WHY THIS EXISTS</h2>
      <figure class="founder__note">
        <blockquote>
          <p>
            “I sold most of my things last year through an Instagram declutter vendor. It worked, but
            it ran on trust and screenshots. So we built the version where
            <span class="founder__accent">nobody has to trust blindly.</span>”
          </p>
        </blockquote>
        <figcaption class="founder__by">
          <div class="founder__photo">PHOTO</div>
          <div class="founder__who">
            <span class="founder__name">[FOUNDER NAME]</span>
            <span class="founder__role">Founder, buysafe</span>
          </div>
        </figcaption>
      </figure>
    </div>
  </section>
</template>

<style scoped>
.founder {
  background: var(--paper-deep);
}

.founder__in {
  padding-block: 120px;
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  gap: 64px;
}

.founder__label {
  margin: 0;
  color: var(--muted);
  padding-top: 14px;
}

.founder__note {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 28px;
}

blockquote {
  margin: 0;
}

blockquote p {
  margin: 0;
  font-family: var(--font-serif);
  font-size: clamp(30px, 3.4723vw, 50px);
  line-height: 1.15;
  letter-spacing: -0.01em;
}

.founder__accent {
  font-style: italic;
  color: var(--released);
}

.founder__by {
  display: flex;
  align-items: center;
  gap: 16px;
}

.founder__photo {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: #cfc4ac;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--muted);
}

.founder__who {
  display: flex;
  flex-direction: column;
}

.founder__name {
  font-weight: 700;
  font-size: 18px;
}

.founder__role {
  color: var(--muted);
  font-size: 15px;
}

@media (max-width: 1023px) {
  .founder__in {
    grid-template-columns: minmax(0, 1fr);
    gap: 24px;
  }

  .founder__label {
    padding-top: 0;
  }
}

@media (max-width: 767px) {
  .founder__in {
    padding-block: 72px;
  }

  blockquote p {
    font-size: 32px;
  }
}
</style>
