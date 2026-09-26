<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, useTemplateRef } from 'vue'
import { useAuthStore } from '@/stores/auth'
import UserAvatar from '@/components/account/UserAvatar.vue'

const links = [
  { href: '#how', label: 'How it works' },
  { href: '#wrong', label: 'If it goes wrong' },
  { href: '#fees', label: 'Fees' },
  { href: '#vendors', label: 'For vendors' },
]

const auth = useAuthStore()

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
}

function onKeydown(e) {
  if (e.key === 'Escape' && open.value) setOpen(false, { returnFocus: true })
}

// The sheet only exists below the desktop nav breakpoint.
let wide
const onBreakpoint = (e) => e.matches && (open.value = false)

onMounted(() => {
  // The page is prerendered signed out; swap Log in for Log out once we know.
  auth.ensureLoaded()
  document.addEventListener('keydown', onKeydown)
  wide = window.matchMedia('(min-width: 1024px)')
  wide.addEventListener('change', onBreakpoint)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  wide?.removeEventListener('change', onBreakpoint)
})
</script>

<template>
  <header class="nav on-dark">
    <div class="l-wrap nav__in">
      <RouterLink to="/" class="wordmark">buysafe<span class="wordmark__dot">.</span></RouterLink>

      <nav class="nav__links" aria-label="Main">
        <a v-for="link in links" :key="link.href" :href="link.href">{{ link.label }}</a>
      </nav>

      <div class="nav__right">
        <div class="nav__actions">
          <button v-if="auth.user" type="button" class="nav__login" @click="logOut">Log out</button>
          <RouterLink v-else to="/login" class="nav__login">Log in</RouterLink>
          <RouterLink to="/sell" class="nav__sell">Sell something</RouterLink>
        </div>

        <!-- Profile stays visible at every width, never only in the menu. -->
        <RouterLink v-if="auth.user" to="/profile" class="nav__avatar" aria-label="Your profile">
          <UserAvatar
            :first-name="auth.user.first_name"
            :last-name="auth.user.last_name"
            :color="auth.user.avatar_color"
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
          class="nav__menu"
          :aria-label="open ? 'Close menu' : 'Open menu'"
          :aria-expanded="open"
          aria-controls="nav-sheet"
          @click="setOpen(!open)"
        >
          <span></span>
          <span></span>
        </button>
      </div>
    </div>

    <div id="nav-sheet" ref="sheet" class="sheet" :hidden="!open">
      <nav class="l-wrap sheet__in" aria-label="Main">
        <a v-for="link in links" :key="link.href" :href="link.href" @click="setOpen(false)">
          {{ link.label }}
        </a>
        <button v-if="auth.user" type="button" class="sheet__logout" @click="logOut">Log out</button>
        <RouterLink v-else to="/login" @click="setOpen(false)">Log in</RouterLink>
        <RouterLink to="/sell" class="sheet__sell" @click="setOpen(false)">Sell something</RouterLink>
      </nav>
    </div>
  </header>
</template>

<style scoped>
.nav {
  position: sticky;
  top: 0;
  z-index: 50;
  background: var(--forest);
  color: var(--paper);
  border-bottom: 1px solid rgba(243, 237, 224, 0.12);
}

.nav__in {
  height: 88px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.wordmark {
  text-decoration: none;
  font-size: 30px;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.wordmark__dot {
  color: var(--accent);
}

.nav__links {
  display: flex;
  gap: 40px;
  font-size: 16px;
  font-weight: 500;
}

/* 44px hit area without changing the layout. */
.nav__links a,
.nav__login {
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  min-height: 44px;
}

.nav__right {
  display: flex;
  gap: 24px;
  align-items: center;
}

.nav__avatar {
  display: flex;
  border-radius: 50%;
  text-decoration: none;
}

.nav__actions {
  display: flex;
  gap: 24px;
  align-items: center;
}

.nav__login {
  font-size: 16px;
  font-weight: 500;
}

button.nav__login,
.sheet__logout {
  border: 0;
  background: none;
  padding: 0;
  color: inherit;
  font-family: inherit;
  cursor: pointer;
}

.nav__sell {
  text-decoration: none;
  background: var(--accent);
  color: var(--ink);
  font-size: 16px;
  font-weight: 700;
  padding: 13px 22px;
  border-radius: 10px;
}

.nav__menu {
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

.nav__menu span {
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
  padding-bottom: 24px;
}

.sheet__in a,
.sheet__logout {
  display: flex;
  align-items: center;
  min-height: 56px;
  border-top: 1px solid rgba(243, 237, 224, 0.12);
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  text-decoration: none;
  text-align: left;
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

/* The desktop nav needs ~930px; below that the menu button takes over. */
@media (max-width: 1023px) {
  .nav__links,
  .nav__actions {
    display: none;
  }

  .nav__menu {
    display: flex;
  }

  .nav__right {
    gap: 12px;
  }
}

@media (max-width: 767px) {
  .nav__in {
    height: 64px;
  }

  .wordmark {
    font-size: 24px;
  }
}
</style>
