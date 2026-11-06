<script setup>
import { onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'

// The notification badge follows the session: polling while signed in,
// plus a fresh count after every page change.
const auth = useAuthStore()
const notifications = useNotificationsStore()
const router = useRouter()
const route = useRoute()

onMounted(() => {
  watch(
    () => auth.user?.id,
    (id) => (id ? notifications.start() : notifications.stop()),
    { immediate: true },
  )
  router.afterEach(() => auth.user && notifications.refresh())
})
</script>

<template>
  <a v-if="!route.meta.ownSkipLink" class="skip-link" href="#main">Skip to content</a>
  <RouterView />
</template>
