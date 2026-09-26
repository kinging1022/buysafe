<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useTemplateRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ROUTES } from '@/config/account'
import UserAvatar from './UserAvatar.vue'

// The app nav (account pages, browse, sell). ≥768px: wordmark, links, Sell
// something and the avatar (or Log in when signed out). Below: wordmark,
// optionally a compact Sell button, and a menu button opening a sheet.
defineProps({
  // Browse shows a small "Sell" button beside the menu on mobile.
  mobileSell: { type: Boolean, default: false },
})

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

// Already posting: no "Sell something" button (sell-*.reference.html).
const onSell = computed(() => route.path.startsWith(ROUTES.sell))

const links = [
  { to: ROUTES.browse, label: 'Browse' },
  { to: ROUTES.messages, label: 'Messages' },
  { to: ROUTES.wallet, label: 'Wallet' },
]

const open = ref(false)
const toggleBtn = useTemplateRef('toggle')
const sheet = useTemplateRef('sheet')

async function setOpen(value, { returnFocus = false } = {}) {
  open.value = value
  if (value) {
    await nextTick()
    sheet.value?.querySelector('a')?.focus()
  } else if (returnFocus) {
    toggleBtn.value?.focus()
  }
}

async function logOut() {
  setOpen(false)
  await auth.logout()
  router.push('/')
}

function onKeydown(e) {
  if (e.key === 'Escape' && open.value) setOpen(false, { returnFocus: true })
}

let wide
const onBreakpoint = (e) => e.matches && (open.value = false)

onMounted(() => {
  auth.ensureLoaded() // public pages (browse) aren't guarded, so load the user here
  document.addEventListener('keydown', onKeydown)
  wide = window.matchMedia('(min-width: 768px)')
  wide.addEventListener('change', onBreakpoint)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  wide?.removeEventListener('change', onBreakpoint)
})
</script>

<template>
  <header class="app-nav on-dark">
    <div class="app-nav__in">
      <div class="app-nav__left">
        <RouterLink to="/" class="wordmark">buysafe<span class="wordmark__dot">.</span></RouterLink>
        <nav class="app-nav__links" aria-label="Main">
          <RouterLink v-for="link in links" :key="link.to" :to="link.to">
            <span class="app-nav__label">{{ link.label }}</span>
          </RouterLink>
        </nav>
      </div>

      <div class="app-nav__right">
        <RouterLink v-if="!onSell" :to="ROUTES.sell" class="app-nav__sell">Sell something</RouterLink>
        <RouterLink v-if="auth.loaded && !auth.user" :to="{ path: '/login', query: { redirect: route.fullPath } }" class="app-nav__login">
          Log in
        </RouterLink>
        <RouterLink v-if="auth.user" to="/profile" class="app-nav__avatar" aria-label="Your profile">
          <UserAvatar
            :first-name="auth.user.first_name"
            :last-name="auth.user.last_name"
            :color="auth.avatarPreview || auth.user.avatar_color"
            :size="44"
            :font-size="16"
            :ring="2"
            :ring-width="2"
            :ring-opacity="0.5"
          />
        </RouterLink>
      </div>

      <RouterLink v-if="mobileSell && !onSell" :to="ROUTES.sell" class="app-nav__sell-m">Sell</RouterLink>
      <!-- Below 768px the right group is hidden; profile stays out of the menu. -->
      <RouterLink v-if="auth.user" to="/profile" class="app-nav__avatar app-nav__avatar-m" aria-label="Your profile">
        <UserAvatar
          :first-name="auth.user.first_name"
          :last-name="auth.user.last_name"
          :color="auth.avatarPreview || auth.user.avatar_color"
          :size="40"
          :font-size="15"
          :ring="2"
          :ring-width="2"
          :ring-opacity="0.5"
        />
      </RouterLink>
      <button
        ref="toggle"
        type="button"
        class="app-nav__menu"
        :aria-label="open ? 'Close menu' : 'Open menu'"
        :aria-expanded="open"
        aria-controls="app-nav-sheet"
        @click="setOpen(!open)"
      >
        <span></span>
        <span></span>
      </button>
    </div>

    <div id="app-nav-sheet" ref="sheet" class="sheet" :hidden="!open">
      <nav class="sheet__in" aria-label="Main">
        <RouterLink v-for="link in links" :key="link.to" :to="link.to" @click="setOpen(false)">
          {{ link.label }}
        </RouterLink>
        <button v-if="auth.user" type="button" class="sheet__logout" @click="logOut">Log out</button>
        <RouterLink v-else :to="{ path: '/login', query: { redirect: route.fullPath } }" @click="setOpen(false)">
          Log in
        </RouterLink>
        <RouterLink v-if="!onSell" :to="ROUTES.sell" class="sheet__sell" @click="setOpen(false)">Sell something</RouterLink>
      </nav>
    </div>
  </header>
</template>

<style scoped>
.app-nav {
  position: relative;
  z-index: 50;
  background: var(--forest);
  color: var(--paper);
  border-bottom: 1px solid rgba(243, 237, 224, 0.12);
}

.app-nav__in {
  box-sizing: border-box;
  max-width: 1440px;
  margin-inline: auto;
  padding: 0 var(--pad-x);
  height: 76px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.app-nav a {
  color: var(--paper);
}

.app-nav__left {
  display: flex;
  align-items: center;
  gap: 48px;
}

.wordmark {
  text-decoration: none;
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.wordmark__dot {
  color: var(--accent);
}

.app-nav__links {
  display: flex;
  gap: 32px;
  font-size: 16px;
  font-weight: 500;
}

/* 44px hit area without changing the layout. */
.app-nav__links a {
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  min-height: 44px;
}

/* The current section gets the reference's marigold underline. */
.app-nav__label {
  padding-bottom: 4px;
  border-bottom: 2px solid transparent;
}

.router-link-active .app-nav__label {
  border-bottom-color: var(--accent);
}

.app-nav__right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.app-nav .app-nav__login {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  font-size: 16px;
  font-weight: 600;
  text-decoration: none;
}

.app-nav .app-nav__sell-m {
  display: none;
  height: 40px;
  align-items: center;
  padding: 0 14px;
  text-decoration: none;
  background: var(--accent);
  color: var(--ink);
  border-radius: 10px;
  font-size: 14px;
  font-weight: 700;
  margin-left: auto;
  margin-right: 10px;
  position: relative;
}

/* 44px touch target on the 40px button. */
.app-nav__sell-m::after {
  content: '';
  position: absolute;
  inset: -2px 0;
}

.app-nav .app-nav__sell {
  text-decoration: none;
  background: var(--accent);
  color: var(--ink);
  font-size: 15px;
  font-weight: 700;
  padding: 12px 20px;
  border-radius: 10px;
}

.app-nav__avatar {
  display: flex;
  border-radius: 50%;
  text-decoration: none;
}

.app-nav .app-nav__avatar-m {
  display: none;
  margin-left: auto;
  margin-right: 12px;
}

.app-nav__sell-m + .app-nav__avatar-m {
  margin-left: 0;
}

.app-nav__menu {
  display: none;
  width: 44px;
  height: 44px;
  background: transparent;
  border: 1.5px solid rgba(243, 237, 224, 0.35);
  border-radius: 10px;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 5px;
  padding: 0;
  cursor: pointer;
}

.app-nav__menu span {
  width: 18px;
  height: 2px;
  background: var(--paper);
  display: block;
}

.sheet {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: var(--forest);
  border-bottom: 1px solid rgba(243, 237, 224, 0.12);
}

.sheet[hidden] {
  display: none;
}

.sheet__in {
  display: flex;
  flex-direction: column;
  padding: 0 var(--pad-x) 24px;
}

.sheet__in a,
.sheet__logout {
  display: flex;
  align-items: center;
  min-height: 56px;
  border: 0;
  border-top: 1px solid rgba(243, 237, 224, 0.12);
  background: none;
  padding: 0;
  color: var(--paper);
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  text-decoration: none;
  text-align: left;
  cursor: pointer;
}

.sheet__in .sheet__sell {
  justify-content: center;
  margin-top: 16px;
  border: 0;
  background: var(--accent);
  color: var(--ink);
  font-size: 17px;
  border-radius: 12px;
}

@media (max-width: 767px) {
  .app-nav__in {
    height: 64px;
  }

  .wordmark {
    font-size: 24px;
  }

  .app-nav__links,
  .app-nav__right {
    display: none;
  }

  .app-nav__menu {
    display: flex;
  }

  .app-nav .app-nav__sell-m,
  .app-nav .app-nav__avatar-m {
    display: flex;
  }
}
</style>
