<template>
  <main id="main" class="l-wrap not-found">
    <h1>This page isn’t ready yet.</h1>
    <p>It may not exist, or we may still be building it.</p>
    <RouterLink to="/" class="not-found__link">Back to the home page</RouterLink>
  </main>
</template>

<style scoped>
.not-found {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 24px;
  padding-block: 140px;
}

h1 {
  margin: 0;
  font-size: clamp(42px, 5.2778vw, 76px);
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.04em;
}

p {
  margin: 0;
  font-size: 20px;
  line-height: 1.55;
  color: var(--ink-2);
}

.not-found__link {
  text-decoration: none;
  background: var(--ink);
  color: var(--paper);
  font-size: 18px;
  font-weight: 700;
  padding: 18px 28px;
  border-radius: 12px;
}
</style>
