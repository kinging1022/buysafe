<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useTemplateRef, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api, upload } from '@/api/http'
import { applyHead } from '@/router/head'
import { useNotificationsStore } from '@/stores/notifications'
import { useIsMobile } from '@/composables/useMediaQuery'
import { useCountdown } from '@/composables/useCountdown'
import { shortTitle } from '@/utils/deals'
import AppHeader from '@/components/account/AppHeader.vue'
import UserAvatar from '@/components/account/UserAvatar.vue'
import EscrowCard from '@/components/deals/EscrowCard.vue'
import EscrowBar from '@/components/deals/EscrowBar.vue'
import DealRules from '@/components/deals/DealRules.vue'
import DealChat from '@/components/deals/DealChat.vue'
import DealComposer from '@/components/deals/DealComposer.vue'
import DealAside from '@/components/deals/DealAside.vue'
import ConfirmReceiptDialog from '@/components/deals/ConfirmReceiptDialog.vue'
import ReportDialog from '@/components/deals/ReportDialog.vue'
import '@/styles/account.css'

// /deals/:id: the escrow card and the deal's chat (design/deal-00…11-*).
// Desktop: the app header, the card with its timeline and turn banner, the
// chat and a right column. Mobile: the chat's own header (back, the other
// person), a compact escrow bar that expands, the banner, then the chat.
// Polls every 5s (no Django Channels yet).
const route = useRoute()
const notifications = useNotificationsStore()
const isMobile = useIsMobile()

const POLL_MS = 5000

const id = computed(() => route.params.id)
const deal = ref(null)
const messages = ref([])
const notFound = ref(false)
const busy = ref(false)
const actionError = ref('')
const composerError = ref('')
const picking = ref(false)
const confirmOpen = ref(false)
const confirmError = ref('')
const reportOpen = ref(false)
const reportSent = ref(false)
const reportError = ref('')

const secondsLeft = useCountdown(
  () => deal.value?.seconds_left,
  () => deal.value?.paused,
)
const recordUrl = computed(() => `${window.location.origin}/deals/${id.value}/record`)
const other = computed(() => deal.value?.other)
const headSub = computed(() => {
  const item = shortTitle(deal.value.listing.title)
  return deal.value.role === 'buyer' ? `Selling you the ${item} · IN-APP ONLY` : `Buying your ${item} · IN-APP ONLY`
})

// ---- Loading and polling ----

const thread = useTemplateRef('thread')
function nearBottom() {
  const el = thread.value
  return !el || el.scrollHeight - el.scrollTop - el.clientHeight < 80
}
async function scrollToEnd() {
  await nextTick()
  if (thread.value) thread.value.scrollTop = thread.value.scrollHeight
}

async function load({ first = false } = {}) {
  const [dealRes, msgRes] = await Promise.all([api(`/deals/${id.value}/`), api(`/deals/${id.value}/messages/`)])
  if (dealRes.status === 404) {
    notFound.value = true
    applyHead({ title: 'Page not found' })
    return
  }
  if (dealRes.ok) {
    deal.value = dealRes.data
    if (first) applyHead({ title: `Deal ${dealRes.data.id}` })
  }
  if (msgRes.ok) {
    const stick = first || nearBottom()
    const grew = msgRes.data.results.length !== messages.value.length
    messages.value = msgRes.data.results
    if (stick && grew) scrollToEnd()
  }
}

let timer = null
function onVisibility() {
  clearInterval(timer)
  if (document.visibilityState === 'visible') {
    load()
    timer = setInterval(load, POLL_MS)
  }
}
onMounted(() => {
  load({ first: true }).then(() => notifications.refresh())
  timer = setInterval(load, POLL_MS)
  document.addEventListener('visibilitychange', onVisibility)
})
onBeforeUnmount(() => {
  clearInterval(timer)
  document.removeEventListener('visibilitychange', onVisibility)
})
watch(id, () => {
  deal.value = null
  messages.value = []
  load({ first: true })
})

// ---- Actions ----

async function step(path, body) {
  busy.value = true
  actionError.value = ''
  const res = await api(`/deals/${id.value}/${path}`, { method: 'POST', body })
  busy.value = false
  if (res.ok) {
    deal.value = res.data
    await load()
    notifications.refresh()
  } else {
    actionError.value = res.data?.detail || 'Something went wrong. Please try again.'
    load()
  }
  return res
}

const rate = ({ verdict, chips = [], note = '' }) =>
  step(`videos/${deal.value.video_count}/rate/`, { verdict, chips, note })
const decide = (choice) => step('after-third-bad/', { choice })
const confirmMeetup = (meetupId) => step(`meetups/${meetupId}/confirm/`)

async function confirmReceipt() {
  confirmError.value = ''
  const res = await step('confirm-receipt/', { checked: true })
  if (res.ok) confirmOpen.value = false
  else confirmError.value = actionError.value
}

async function proposeMeetup(body, done) {
  const res = await step('meetups/', body)
  if (res.ok) done()
  else composerError.value = actionError.value
}

async function send(body, done) {
  busy.value = true
  composerError.value = ''
  const res = await api(`/deals/${id.value}/messages/`, { method: 'POST', body: { body } })
  busy.value = false
  if (res.ok) {
    messages.value = res.data.results
    done()
    scrollToEnd()
  } else {
    composerError.value = res.data?.detail || 'Your message wasn’t sent. Try again.'
  }
}

async function sendPhoto(file) {
  busy.value = true
  composerError.value = ''
  const form = new FormData()
  form.append('photo', file)
  const res = await upload(`/deals/${id.value}/messages/`, form)
  busy.value = false
  if (res.ok) {
    messages.value = res.data.results
    scrollToEnd()
  } else {
    composerError.value = res.data?.detail || 'The photo wasn’t sent. Try again.'
  }
}

async function sendReport(text) {
  busy.value = true
  reportError.value = ''
  const res = await api(`/deals/${id.value}/report/`, { method: 'POST', body: { text } })
  busy.value = false
  if (res.ok) reportSent.value = true
  else reportError.value = res.data?.detail || 'Something went wrong. Please try again.'
}

function openReport() {
  confirmOpen.value = false
  reportSent.value = false
  reportError.value = ''
  reportOpen.value = true
}

// Desktop "Record on your phone": bring the QR code into view.
function showRecord() {
  const card = document.getElementById('record-prompt')
  card?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}
</script>

<template>
  <div class="acct dv" :class="{ 'dv--m': isMobile }">
    <template v-if="notFound">
      <AppHeader section="/deals" />
      <main id="main" class="acct-wrap dv-empty">
        <h1 class="dv-empty__h">We couldn’t find this deal.</h1>
        <RouterLink to="/deals" class="acct-btn-outline">←  All deals</RouterLink>
      </main>
    </template>

    <!-- ================= Desktop ================= -->
    <template v-else-if="deal && !isMobile">
      <AppHeader section="/deals" />
      <div class="acct-wrap dv-back-row"><RouterLink to="/deals" class="dv-back">←  All deals</RouterLink></div>
      <div class="acct-wrap dv-card-row">
        <EscrowCard :deal="deal" :seconds-left="secondsLeft" :picking="picking" @record="showRecord" @confirm="confirmOpen = true" />
      </div>
      <main id="main" class="acct-wrap dv-main">
        <section class="dv-chat" aria-label="Chat">
          <DealRules :buyer="deal.buyer_first_name" :seller="deal.seller_first_name" />
          <div class="dv-thread">
            <p v-if="actionError" class="dv-error" role="alert">{{ actionError }}</p>
            <DealChat
              :deal="deal"
              :messages="messages"
              :record-url="recordUrl"
              :busy="busy"
              @rate="rate"
              @decide="decide"
              @confirm-meetup="confirmMeetup"
              @picking="picking = $event"
            />
          </div>
          <DealComposer :deal="deal" :busy="busy" :error="composerError" class="dv-composer" @send="send" @photo="sendPhoto" @meetup="proposeMeetup" />
        </section>
        <DealAside :deal="deal" @report="openReport" />
      </main>
    </template>

    <!-- ================= Mobile ================= -->
    <div v-else-if="deal" class="dv-screen">
      <header class="dv-mhead">
        <RouterLink to="/deals" class="dv-mhead__back" aria-label="Back to deals">←</RouterLink>
        <UserAvatar :first-name="other.first_name" :last-name="other.last_initial" :color="other.avatar_color" :size="36" :font-size="13" />
        <span class="dv-mhead__text">
          <span class="dv-mhead__name">{{ other.first_name }} {{ other.last_initial }}.</span>
          <span class="dv-mhead__sub">{{ headSub }}</span>
        </span>
      </header>
      <EscrowBar :deal="deal" :seconds-left="secondsLeft" :picking="picking" @confirm="confirmOpen = true" />
      <DealRules :buyer="deal.buyer_first_name" :seller="deal.seller_first_name" mobile />
      <main id="main" ref="thread" class="dv-mthread">
        <p v-if="actionError" class="dv-error" role="alert">{{ actionError }}</p>
        <DealChat
          :deal="deal"
          :messages="messages"
          :record-url="recordUrl"
          :busy="busy"
          mobile
          @rate="rate"
          @decide="decide"
          @confirm-meetup="confirmMeetup"
          @picking="picking = $event"
        />
        <!-- No mobile reference places Report a problem; it closes the thread. -->
        <button type="button" class="dv-mreport" @click="openReport">Report a problem</button>
      </main>
      <DealComposer :deal="deal" :busy="busy" :error="composerError" mobile @send="send" @photo="sendPhoto" @meetup="proposeMeetup" />
    </div>

    <template v-if="deal">
      <ConfirmReceiptDialog
        :open="confirmOpen"
        :sheet="isMobile"
        :deal="deal"
        :busy="busy"
        :error="confirmError"
        @close="confirmOpen = false"
        @confirm="confirmReceipt"
        @report="openReport"
      />
      <ReportDialog
        :open="reportOpen"
        :sheet="isMobile"
        :busy="busy"
        :error="reportError"
        :sent="reportSent"
        :state="deal.state"
        @close="reportOpen = false"
        @send="sendReport"
      />
    </template>
  </div>
</template>

<style scoped>
.dv-empty {
  padding-top: 64px;
  padding-bottom: 96px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  align-items: flex-start;
}

.dv-empty__h {
  margin: 0;
  font-size: 40px;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.dv-back-row {
  padding-top: 24px;
}

.acct .dv-back {
  font-size: 15px;
  font-weight: 600;
  text-decoration: none;
  white-space: pre;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
}

.dv-card-row {
  padding-top: 4px;
}

.dv-main {
  flex-grow: 1;
  padding-top: 24px;
  padding-bottom: 72px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 32px;
  align-items: start;
}

.dv-chat {
  background: #efe9dc;
  border-radius: 22px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.dv-thread {
  padding: 24px 28px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* The composer stays in reach while the chat scrolls with the page. */
.dv-composer {
  position: sticky;
  bottom: 0;
  z-index: 2;
}

.dv-error {
  margin: 0;
  font-size: 14px;
  color: #a3361f;
  text-align: center;
}

@media (max-width: 1279px) {
  .dv-main {
    grid-template-columns: minmax(0, 1fr) 300px;
    gap: 24px;
  }
}

@media (max-width: 1023px) {
  .dv-main {
    grid-template-columns: minmax(0, 1fr);
  }
}

/* ---- Mobile: a full-height chat screen ---- */

.dv--m {
  min-height: 0;
}

.dv-screen {
  height: 100vh;
  height: 100dvh;
  display: flex;
  flex-direction: column;
  background: #efe9dc;
  overflow: hidden;
}

.dv-mhead {
  flex-shrink: 0;
  background: var(--paper);
  padding: 8px 12px 8px 4px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid rgba(18, 20, 16, 0.14);
}

.acct .dv-mhead__back {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  font-size: 20px;
  color: var(--ink);
}

.dv-mhead__text {
  display: flex;
  flex-direction: column;
  flex-grow: 1;
  min-width: 0;
}

.dv-mhead__name {
  font-size: 16px;
  font-weight: 700;
}

.dv-mhead__sub {
  font-size: 12px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dv-mreport {
  align-self: center;
  margin-top: 10px;
  background: transparent;
  border: 0;
  padding: 0;
  min-height: 44px;
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 700;
  color: #a3361f;
  text-decoration: underline;
  cursor: pointer;
}

.dv-mthread {
  flex-grow: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 14px;
  display: flex;
  flex-direction: column;
}

/* Short chats sit at the bottom, above the composer. */
.dv-mthread > :first-child {
  margin-top: auto;
}

.dv :is(a, button):focus-visible {
  outline: 2px solid var(--ink);
  outline-offset: 2px;
  box-shadow: 0 0 0 5px rgba(245, 184, 46, 0.45);
}
</style>
