<script setup>
// TODO placeholder for pages that aren't built yet (/profile/phone).
import AppHeader from '@/components/account/AppHeader.vue'
import { useAuthStore } from '@/stores/auth'
import '@/styles/account.css'

defineProps({
  heading: { type: String, required: true },
  back: { type: String, default: '/profile' },
  backLabel: { type: String, default: 'Back to profile' },
})

const auth = useAuthStore()
auth.ensureLoaded()
</script>

<template>
  <div class="acct">
    <AppHeader />
    <main id="main" class="acct-wrap todo">
      <RouterLink :to="auth.user ? back : '/'" class="acct-back">←  {{ auth.user ? backLabel : 'Back to buysafe' }}</RouterLink>
      <h1 class="acct-h1">{{ heading }}</h1>
      <p class="todo__note">This page is coming soon.</p>
    </main>
  </div>
</template>

<style scoped>
.todo {
  padding-top: 56px;
  padding-bottom: 96px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.todo__note {
  margin: 0;
  font-size: 17px;
  color: var(--muted);
}
</style>
