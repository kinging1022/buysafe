<script setup>
import { computed, ref, useTemplateRef } from 'vue'
import { useRouter } from 'vue-router'
import { useNotificationsStore } from '@/stores/notifications'
import { useNotificationsPanel } from '@/composables/useNotificationsPanel'
import { useIsMobile } from '@/composables/useMediaQuery'
import { useModal } from '@/composables/useModal'
import AppHeader from '@/components/account/AppHeader.vue'
import NotificationList from '@/components/notifications/NotificationList.vue'
import '@/styles/account.css'

// /notifications. Mobile: the panel the header bell toggles, below the
// header (design/notifications-2-panel-open-mobile, -3-all-read-mobile): a
// dialog with a focus trap; Escape, the bell or the phone's back button
// close it. Desktop (no reference): the same list in the page column.
const router = useRouter()
const store = useNotificationsStore()
const panel = useNotificationsPanel()
const isMobile = useIsMobile()

const list = useTemplateRef('list')
const dialog = useTemplateRef('dialog')
const scroller = useTemplateRef('scroller')
const toast = ref('')
let toastTimer = null

const { onKeydown } = useModal(dialog, () => isMobile.value, () => panel.close())

const canMarkAll = computed(() => store.unread > 0 || list.value?.hasUnread)

async function markAll() {
  if (!canMarkAll.value) return
  const ok = await list.value.markAllRead()
  if (!ok) {
    toast.value = 'Couldn’t mark them as read. Please try again.'
    clearTimeout(toastTimer)
    toastTimer = setTimeout(() => (toast.value = ''), 4000)
  }
}

// A row goes to its target. On mobile the panel's history entry is replaced,
// so Back from there returns to the page underneath, not the panel.
const navigate = (item) => (isMobile.value ? router.replace(item.target_url) : router.push(item.target_url))
</script>

<template>
  <div class="acct nt" :class="{ 'nt--m': isMobile }">
    <AppHeader />

    <div
      v-if="isMobile"
      id="main"
      ref="dialog"
      class="nt-panel"
      role="dialog"
      aria-label="Notifications"
      @keydown="onKeydown"
    >
      <div class="nt-head">
        <h1 class="nt-h1" tabindex="-1" data-autofocus>Notifications</h1>
        <button type="button" class="nt-markall" :aria-disabled="!canMarkAll" @click="markAll">Mark all read</button>
      </div>
      <div ref="scroller" class="nt-scroll">
        <NotificationList v-if="scroller" ref="list" :scroll-root="scroller" @navigate="navigate" />
      </div>
    </div>

    <main v-else id="main" class="acct-wrap nt-main">
      <div class="nt-head nt-head--d">
        <h1 class="nt-h1 nt-h1--d">Notifications</h1>
        <button type="button" class="nt-markall" :aria-disabled="!canMarkAll" @click="markAll">Mark all read</button>
      </div>
      <NotificationList ref="list" class="nt-list-d" @navigate="navigate" />
    </main>

    <div v-if="toast" class="nt-toast af-box" role="alert">{{ toast }}</div>
  </div>
</template>

<style scoped>
/* ---- Mobile panel ---- */

.nt--m {
  height: 100vh;
  height: 100dvh;
  min-height: 0;
  overflow: hidden;
}

.nt-panel {
  flex-grow: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--paper);
}

.nt-head {
  flex-shrink: 0;
  margin: 0 20px;
  padding: 20px 0 12px;
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  border-bottom: 2px solid var(--ink);
}

.nt-h1 {
  margin: 0;
  font-size: 34px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.nt-h1:focus {
  outline: none;
}

.nt-markall {
  background: transparent;
  border: 0;
  padding: 0;
  min-height: 44px;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  color: var(--forest);
  text-decoration: underline;
  cursor: pointer;
}

.nt-markall[aria-disabled='true'] {
  color: #8c8e85;
  cursor: default;
}

.nt-scroll {
  flex-grow: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-bottom: env(safe-area-inset-bottom, 0px);
}

/* ---- Desktop page ---- */

.nt-main {
  flex-grow: 1;
  padding-top: 48px;
  padding-bottom: 96px;
}

.nt-head--d,
.nt-list-d {
  max-width: 880px;
}

.nt-head--d {
  margin: 0;
  padding-top: 0;
  padding-bottom: 16px;
}

.nt-h1--d {
  font-size: 56px;
}

.nt-list-d {
  margin-top: 4px;
}

.nt-list-d :deep(.nl__group) {
  padding-left: 0;
}

/* ---- Toast (mark-all failure) ---- */

.nt-toast {
  position: fixed;
  z-index: 60;
  left: 20px;
  right: 20px;
  bottom: calc(20px + env(safe-area-inset-bottom, 0px));
  max-width: 520px;
  margin: 0 auto;
  box-shadow: 0 12px 30px rgba(18, 20, 16, 0.12);
}

.nt :is(button, a):focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
</style>
