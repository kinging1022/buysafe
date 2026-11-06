<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useTemplateRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { badgeText, useNotificationsStore } from '@/stores/notifications'
import { takeBellFocus, useNotificationsPanel } from '@/composables/useNotificationsPanel'
import { ROUTES } from '@/config/account'
import UserAvatar from './UserAvatar.vue'
import IconBell from '@/components/ui/IconBell.vue'
import IconMessage from '@/components/ui/IconMessage.vue'

// The app nav. ≥768px: wordmark, text links (Deals & messages and
// Notifications with marigold count pills), Sell something and the avatar
// (or Log in when signed out). Below 768px, signed in (design/header-spec
// and nav-and-notifications-update):
//   [menu][wordmark] ……… [messages][bell][avatar]
// The speech bubble opens the deals list: every chat belongs to a deal.
// Signed in, 768–1023px (tablets) use the same compact bar on the page's
// 48px margin: the full row (four links, Sell, Log out, avatar) doesn't fit.
// The bell toggles the notifications panel (/notifications). Sell moves to
// the top of the menu sheet. Signed out, below 768px: wordmark, optional
// Sell, and the menu button on the right, as before.
defineProps({
  // Browse shows a small "Sell" button beside the menu on mobile (signed out).
  mobileSell: { type: Boolean, default: false },
  // Underline a section the current page belongs to but isn't nested under
  // (a listing page is part of Browse).
  section: { type: String, default: '' },
  // Stays at the top while the page scrolls (home, like the landing nav).
  sticky: { type: Boolean, default: false },
})

const auth = useAuthStore()
const notifications = useNotificationsStore()
const panel = useNotificationsPanel()
const router = useRouter()
const route = useRoute()

// Already posting: no "Sell something" button (sell-*.reference.html).
const onSell = computed(() => route.path.startsWith(ROUTES.sell))

const links = [
  { to: ROUTES.browse, label: 'Browse' },
  { to: ROUTES.deals, label: 'Deals & messages', badge: 'deals' },
  { to: ROUTES.notifications, label: 'Notifications', badge: 'unread', signedIn: true },
]
const shownLinks = computed(() => links.filter((l) => !l.signedIn || auth.user))
const badge = computed(() => badgeText(notifications.unread))
const dealsBadge = computed(() => badgeText(notifications.deals))
const badgeFor = (link) => (link.badge === 'deals' ? dealsBadge.value : link.badge === 'unread' ? badge.value : '')
const badgeHint = (link) => (link.badge === 'deals' ? ' need you' : ' unread')
const bellLabel = computed(() =>
  notifications.unread ? `Notifications, ${notifications.unread} unread` : 'Notifications',
)
const dealsLabel = computed(() =>
  notifications.deals ? `Deals and messages, ${notifications.deals} need you` : 'Deals and messages',
)
const onDeals = computed(() => route.path.startsWith(ROUTES.deals))

// Count changes are announced once, politely (not on first load).
const liveText = ref('')
watch(
  () => notifications.unread,
  (now, before) => {
    if (before === undefined || now === before) return
    liveText.value = now ? `${now} unread notification${now === 1 ? '' : 's'}` : 'No unread notifications'
  },
)

const open = ref(false)
const toggleBtn = useTemplateRef('toggle')
const toggleBtnM = useTemplateRef('toggleM')
const bellBtn = useTemplateRef('bell')
const sheet = useTemplateRef('sheet')

// Whichever menu button is showing (the signed-in mobile bar has its own, on the left).
const visibleToggle = () => [toggleBtnM.value, toggleBtn.value].find((el) => el && el.offsetParent !== null)

async function setOpen(value, { returnFocus = false } = {}) {
  open.value = value
  if (value) {
    await nextTick()
    sheet.value?.querySelector('a, button')?.focus()
  } else if (returnFocus) {
    visibleToggle()?.focus()
  }
}

function toggleNotifications() {
  setOpen(false)
  panel.toggle()
}

async function logOut() {
  setOpen(false)
  await auth.logout()
  router.push('/')
}

function onKeydown(e) {
  if (e.key === 'Escape' && open.value) setOpen(false, { returnFocus: true })
}

// The menu sheet closes when the layout changes size class.
const queries = []
const onBreakpoint = () => (open.value = false)

onMounted(() => {
  auth.ensureLoaded() // public pages (browse) aren't guarded, so load the user here
  document.addEventListener('keydown', onKeydown)
  for (const q of ['(min-width: 768px)', '(min-width: 1024px)']) {
    const mql = window.matchMedia(q)
    mql.addEventListener('change', onBreakpoint)
    queries.push(mql)
  }
  // Back from the notifications panel: focus returns to the bell.
  if (takeBellFocus()) nextTick(() => bellBtn.value?.offsetParent && bellBtn.value.focus({ preventScroll: true }))
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  queries.forEach((mql) => mql.removeEventListener('change', onBreakpoint))
})
</script>

<template>
  <header class="app-nav on-dark" :class="{ 'app-nav--user': auth.user, 'app-nav--sticky': sticky }">
    <!-- Desktop, and signed-out mobile. -->
    <div class="app-nav__in">
      <div class="app-nav__left">
        <RouterLink to="/" class="wordmark">buysafe<span class="wordmark__dot">.</span></RouterLink>
        <nav class="app-nav__links" aria-label="Main">
          <RouterLink v-for="link in shownLinks" :key="link.to" :to="link.to" :class="{ 'app-nav__in-section': link.to === section }">
            <span class="app-nav__label">{{ link.label }}</span>
            <span v-if="badgeFor(link)" class="app-nav__badge num">
              {{ badgeFor(link) }}<span class="visually-hidden">{{ badgeHint(link) }}</span>
            </span>
          </RouterLink>
        </nav>
      </div>

      <div class="app-nav__right">
        <RouterLink v-if="!onSell" :to="ROUTES.sell" class="app-nav__sell">Sell something</RouterLink>
        <RouterLink v-if="auth.loaded && !auth.user" :to="{ path: '/login', query: { redirect: route.fullPath } }" class="app-nav__login">
          Log in
        </RouterLink>
        <button v-if="auth.user" type="button" class="app-nav__login app-nav__logout" @click="logOut">Log out</button>
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

    <!-- Signed-in mobile bar. Padding 0 14px 0 9px puts the visible glyph and
         avatar edges on the page's 20px margin; every control is a 44px target. -->
    <div v-if="auth.user" class="mbar">
      <div class="mbar__group">
        <button
          ref="toggleM"
          type="button"
          class="mbar__btn mbar__menu"
          :aria-label="open ? 'Close menu' : 'Open menu'"
          :aria-expanded="open"
          aria-controls="app-nav-sheet"
          @click="setOpen(!open)"
        >
          <span></span>
          <span></span>
        </button>
        <RouterLink to="/" class="mbar__mark">buysafe<span>.</span></RouterLink>
      </div>
      <div class="mbar__group">
        <RouterLink
          :to="ROUTES.deals"
          class="mbar__btn mbar__msgs"
          :class="{ 'mbar__btn--on': onDeals }"
          :aria-label="dealsLabel"
          :aria-current="onDeals ? 'page' : undefined"
        >
          <IconMessage />
          <span v-if="dealsBadge" class="mbar__badge num" aria-hidden="true">{{ dealsBadge }}</span>
        </RouterLink>
        <button
          ref="bell"
          type="button"
          class="mbar__btn mbar__bell"
          :class="{ 'mbar__btn--on': panel.isOpen.value }"
          :aria-label="bellLabel"
          :aria-expanded="panel.isOpen.value"
          @click="toggleNotifications"
        >
          <IconBell />
          <span v-if="badge" class="mbar__badge num" aria-hidden="true">{{ badge }}</span>
        </button>
        <RouterLink to="/profile" class="mbar__btn mbar__avatar" aria-label="Your profile">
          <UserAvatar
            :first-name="auth.user.first_name"
            :last-name="auth.user.last_name"
            :color="auth.avatarPreview || auth.user.avatar_color"
            :size="32"
            :font-size="12"
            :ring="1.5"
            :ring-width="1.5"
            :ring-opacity="0.55"
          />
        </RouterLink>
      </div>
      <span class="visually-hidden" aria-live="polite">{{ liveText }}</span>
    </div>

    <div id="app-nav-sheet" ref="sheet" class="sheet" :hidden="!open">
      <nav class="sheet__in" :class="{ 'sheet__in--user': auth.user }" aria-label="Main">
        <!-- Signed in: Sell is the first, primary item (it left the mobile bar). -->
        <RouterLink v-if="auth.user && !onSell" :to="ROUTES.sell" class="sheet__sell sheet__sell--top" @click="setOpen(false)">
          Sell something
        </RouterLink>
        <RouterLink v-for="link in shownLinks" :key="link.to" :to="link.to" @click="setOpen(false)">
          {{ link.label }}
          <span v-if="badgeFor(link)" class="app-nav__badge num">
            {{ badgeFor(link) }}<span class="visually-hidden">{{ badgeHint(link) }}</span>
          </span>
        </RouterLink>
        <button v-if="auth.user" type="button" class="sheet__logout" @click="logOut">Log out</button>
        <RouterLink v-else :to="{ path: '/login', query: { redirect: route.fullPath } }" @click="setOpen(false)">
          Log in
        </RouterLink>
        <RouterLink v-if="!auth.user && !onSell" :to="ROUTES.sell" class="sheet__sell" @click="setOpen(false)">Sell something</RouterLink>
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

.app-nav--sticky {
  position: sticky;
  top: 0;
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

.router-link-active .app-nav__label,
.app-nav__in-section .app-nav__label {
  border-bottom-color: var(--accent);
}

/* Unread count: marigold pill beside "Notifications". */
.app-nav__badge {
  margin-left: 8px;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  box-sizing: border-box;
  border-radius: 10px;
  background: var(--accent);
  color: var(--ink);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  letter-spacing: 0;
}

.sheet__in .app-nav__badge {
  margin-left: 10px;
  height: 24px;
  min-width: 24px;
  font-size: 13px;
}

/* ---- Signed-in mobile bar (design/header-spec) ---- */

.mbar {
  display: none;
  height: 64px;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px 0 9px;
  box-sizing: border-box;
}

.mbar__group {
  display: flex;
  align-items: center;
}

.mbar__btn {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  border: 0;
  padding: 0;
  border-radius: 12px;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  text-decoration: none;
  -webkit-tap-highlight-color: transparent;
}

/* Pressed / focus: a 12px-radius tint on the tap area. */
.mbar__btn:active,
.mbar__btn--on,
.mbar__btn:focus-visible {
  background: rgba(243, 237, 224, 0.14);
}

.app-nav .mbar__btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 0;
  box-shadow: none;
}

.mbar__menu {
  flex-direction: column;
  gap: 5px;
}

.mbar__menu span {
  width: 18px;
  height: 2px;
  border-radius: 1px;
  background: var(--paper);
}

.app-nav .mbar__mark {
  margin-left: 1px;
  flex-shrink: 0;
  white-space: nowrap;
  text-decoration: none;
  color: var(--paper);
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.mbar__mark span {
  color: var(--accent);
}

.mbar__bell,
.mbar__msgs {
  position: relative;
}

/* On the bell glyph's top-right corner, not the tap area's. */
.mbar__badge {
  position: absolute;
  left: 25px;
  top: 6px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  box-sizing: border-box;
  border-radius: 9px;
  background: var(--accent);
  color: var(--ink);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 0 2px var(--forest);
}

/* Sell, first in the signed-in sheet. */
.sheet__in .sheet__sell--top {
  margin: 16px 0 8px;
}

.app-nav__right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.app-nav__logout {
  border: 0;
  padding: 0;
  background: transparent;
  color: var(--paper);
  font-family: var(--font-display);
  cursor: pointer;
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

/* Tablets, signed in: the compact bar, on the 48px page margin (bars and
   avatar sit on --pad-x the way they sit on 20px on phones). */
@media (min-width: 768px) and (max-width: 1023px) {
  .app-nav--user {
    border-bottom: 0;
  }

  .app-nav--user .app-nav__in {
    display: none;
  }

  .app-nav--user .mbar {
    display: flex;
    padding: 0 calc(var(--pad-x) - 6px) 0 calc(var(--pad-x) - 11px);
  }
}

/* Small tablets, signed out: three links, Sell and Log in in one row. */
@media (min-width: 768px) and (max-width: 959px) {
  .app-nav__left {
    gap: 24px;
  }

  .app-nav__links {
    gap: 18px;
    font-size: 15px;
  }

  .app-nav__right {
    gap: 14px;
  }

  .app-nav .app-nav__sell {
    padding: 12px 14px;
    font-size: 14px;
    white-space: nowrap;
  }
}

@media (max-width: 767px) {
  .app-nav__in {
    height: 64px;
  }

  /* Signed in: the new bar replaces the row above, with no bottom rule. */
  .app-nav--user {
    border-bottom: 0;
  }

  .app-nav--user .app-nav__in {
    display: none;
  }

  .app-nav--user .mbar {
    display: flex;
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
