<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, useTemplateRef } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/http'
import QuestionAskBox from './QuestionAskBox.vue'
import QuestionItem from './QuestionItem.vue'
import QuestionsHowTo from './QuestionsHowTo.vue'

// The public Q&A section of a listing (id="questions"), buyer or owner view
// (design/qa-buyer-*, qa-owner-*). The API decides what each viewer may see;
// changes show at once (optimistic) and roll back if the request fails.
const props = defineProps({
  listing: { type: Object, required: true }, // GET /api/listings/:id/
  owner: { type: Boolean, default: false }, // the owner's view (not ?as=buyer)
  compact: { type: Boolean, default: false }, // mobile
})

const GENERIC_ERROR = 'Something went wrong. Please try again.'
const UNDO_MS = 60_000

const route = useRoute()
const seller = computed(() => props.listing.seller.first_name)
const base = computed(() => `/listings/${props.listing.id}/questions/`)

const meta = ref(null)
const pending = ref([])
const answered = ref([])
const nextPage = ref(null)
const loadingMore = ref(false)
const loadError = ref('')
const now = ref(new Date())

async function load() {
  const res = await api(base.value)
  if (!res.ok) {
    loadError.value = GENERIC_ERROR
    return
  }
  loadError.value = ''
  meta.value = res.data.meta
  pending.value = res.data.pending
  answered.value = res.data.answered
  nextPage.value = res.data.next_page
}

async function loadMore() {
  loadingMore.value = true
  const res = await api(`${base.value}?page=${nextPage.value}`)
  loadingMore.value = false
  if (!res.ok) return
  const seen = new Set(answered.value.map((q) => q.id))
  answered.value.push(...res.data.answered.filter((q) => !seen.has(q.id)))
  nextPage.value = res.data.next_page
}

// ---- Buyer: ask ----

const askBox = useTemplateRef('askBox')
const asking = ref(false)
const askError = ref('')
const askKind = ref(null)

async function ask(text) {
  asking.value = true
  askError.value = ''
  askKind.value = null
  const temp = {
    id: `temp-${Date.now()}`,
    text,
    asker: { first_name: '', last_initial: '' },
    created_at: new Date().toISOString(),
    answer: '',
    answered_at: null,
    edited: false,
    status: 'pending',
    is_mine: true,
  }
  pending.value.unshift(temp)
  const left = meta.value.questions_left_today
  meta.value.questions_left_today = Math.max(0, left - 1)
  const res = await api(base.value, { method: 'POST', body: { text } })
  asking.value = false
  if (res.ok) {
    pending.value.splice(pending.value.indexOf(temp), 1, res.data)
    askBox.value?.clear()
    if (!meta.value.questions_left_today) load() // now at the limit: show the 3 OF 3 panel
    return
  }
  pending.value = pending.value.filter((q) => q !== temp)
  meta.value.questions_left_today = left
  const code = res.data?.code
  if (code === 'contact_details') askKind.value = res.data.kind
  else if (code === 'question_limit' || code === 'not_live') load()
  else askError.value = res.data?.detail || GENERIC_ERROR
}

const showAskBox = computed(() => meta.value?.can_ask)
const showLimit = computed(() => meta.value?.reason === 'question_limit')
const showLogin = computed(() => meta.value?.reason === 'login_required' && props.listing.display_status === 'live')
const loginLink = computed(() => ({ path: '/login', query: { redirect: `/listings/${props.listing.id}#questions` } }))
const mine = computed(() => pending.value.filter((q) => q.is_mine))

// ---- Owner: answer, edit, remove (with Undo) ----

const editingId = ref(null)
const busyId = ref(null)
const itemErrors = reactive({}) // id -> { kind, error }
const removed = reactive({}) // id -> { until, from }
function openEditor(q) {
  editingId.value = q.id
  delete itemErrors[q.id]
}

// Focus goes back to the question's button: "Answer" after Cancel, "Edit
// answer" once an answer is posted (the button that opened the editor was
// replaced while it was open).
async function closeEditor(q) {
  editingId.value = null
  await nextTick()
  const item = section.value?.querySelector(`[data-q="${q.id}"]`)
  const button = item?.querySelector('.qo__answer') || item?.querySelector('.qi__link')
  if (button) button.focus()
  else heading.value?.focus()
}

function failed(q, res) {
  itemErrors[q.id] =
    res.data?.code === 'contact_details'
      ? { kind: res.data.kind, error: '' }
      : { kind: null, error: res.data?.detail || GENERIC_ERROR }
}

async function submitAnswer(q, text) {
  const wasPending = q.status === 'pending'
  const before = { ...q }
  busyId.value = q.id
  // Optimistic: an answer moves the card into ANSWERED; an edit updates in place.
  Object.assign(q, { answer: text, status: 'answered', answered_at: q.answered_at || new Date().toISOString(), edited: q.edited || !wasPending })
  if (wasPending) {
    pending.value = pending.value.filter((x) => x !== q)
    answered.value.unshift(q)
  }
  editingId.value = null
  const res = await api(`/questions/${q.id}/answer/`, { method: wasPending ? 'POST' : 'PATCH', body: { answer: text } })
  busyId.value = null
  if (res.ok) {
    Object.assign(q, res.data)
    await closeEditor(q)
    return
  }
  Object.assign(q, before)
  if (wasPending) {
    answered.value = answered.value.filter((x) => x !== q)
    pending.value.push(q)
    pending.value.sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
  }
  failed(q, res)
  editingId.value = q.id
}

async function remove(q) {
  busyId.value = q.id
  removed[q.id] = { until: Date.now() + UNDO_MS }
  const res = await api(`/questions/${q.id}/remove/`, { method: 'POST' })
  busyId.value = null
  if (!res.ok) {
    delete removed[q.id]
    failed(q, res)
    return
  }
  // After the Undo window it's gone for good.
  removed[q.id].timer = setTimeout(() => {
    pending.value = pending.value.filter((x) => x.id !== q.id)
    answered.value = answered.value.filter((x) => x.id !== q.id)
    delete removed[q.id]
  }, UNDO_MS)
}

async function undo(q) {
  const entry = removed[q.id]
  if (!entry) return
  const res = await api(`/questions/${q.id}/restore/`, { method: 'POST' })
  if (res.ok) {
    clearTimeout(entry.timer)
    delete removed[q.id]
    Object.assign(q, res.data)
  } else {
    itemErrors[q.id] = { kind: null, error: res.data?.detail || GENERIC_ERROR }
  }
}

const pendingCount = computed(() => pending.value.filter((q) => !removed[q.id]).length)
const removedLine = (q) =>
  props.compact
    ? `${q.asker.first_name}’s question removed.`
    : `Question from ${q.asker.first_name.toUpperCase()} ${q.asker.last_initial}. removed as spam.`

// ---- Section ----

const heading = useTemplateRef('heading')
const section = useTemplateRef('section')

/** "Ask Tolu a question" elsewhere on the page: scroll here and focus the box. */
function focusAsk() {
  section.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  if (askBox.value) askBox.value.focus()
  else heading.value?.focus({ preventScroll: true })
}
defineExpose({ focusAsk })

let clock = null
onMounted(async () => {
  await load()
  clock = setInterval(() => (now.value = new Date()), 60_000)
  if (route.hash === '#questions') {
    await nextTick()
    section.value?.scrollIntoView({ block: 'start' })
  }
})
onBeforeUnmount(() => {
  clearInterval(clock)
  Object.values(removed).forEach((r) => clearTimeout(r.timer))
})
</script>

<template>
  <section id="questions" ref="section" class="lq" :class="{ 'lq--m': compact, 'lq--owner': owner }" aria-labelledby="questions-h">
    <!-- ================= Owner ================= -->
    <template v-if="owner">
      <div class="lq__head lq__head--owner">
        <h2 id="questions-h" ref="heading" class="lq__h" tabindex="-1">Questions</h2>
        <span v-if="pendingCount" class="lq__pill" aria-live="polite">
          <template v-if="!compact">NEEDS YOUR ANSWER · {{ pendingCount }}</template>
          <template v-else>{{ pendingCount }} TO ANSWER</template>
        </span>
      </div>

      <template v-for="q in pending" :key="q.id">
        <div v-if="removed[q.id]" class="lq__removed">
          <span>{{ removedLine(q) }}</span>
          <button type="button" class="lq__undo" @click="undo(q)">Undo</button>
        </div>
        <QuestionItem
          v-else
          :data-q="q.id"
          :question="q"
          variant="owner-pending"
          :seller-name="seller"
          :compact="compact"
          :now="now"
          :editing="editingId === q.id"
          :busy="busyId === q.id"
          :server-kind="itemErrors[q.id]?.kind"
          :error="itemErrors[q.id]?.error"
          @open-editor="openEditor(q)"
          @cancel="closeEditor(q)"
          @submit="submitAnswer(q, $event)"
          @remove="remove(q)"
        />
      </template>

      <div v-if="answered.length" class="lq__list">
        <span class="lq__answered-h">{{ compact ? 'ANSWERED · PUBLIC' : 'ANSWERED · VISIBLE TO EVERYONE' }}</span>
        <template v-for="q in answered" :key="q.id">
          <div v-if="removed[q.id]" class="lq__removed lq__removed--row">
            <span>{{ removedLine(q) }}</span>
            <button type="button" class="lq__undo" @click="undo(q)">Undo</button>
          </div>
          <QuestionItem
            v-else
            :data-q="q.id"
            :question="q"
            variant="owner-answered"
            :seller-name="seller"
            :compact="compact"
            :now="now"
            :editing="editingId === q.id"
            :busy="busyId === q.id"
            :server-kind="itemErrors[q.id]?.kind"
            :error="itemErrors[q.id]?.error"
            @open-editor="openEditor(q)"
            @cancel="closeEditor(q)"
            @submit="submitAnswer(q, $event)"
            @remove="remove(q)"
          />
        </template>
      </div>

      <div v-if="meta && !pending.length && !answered.length" class="lq__empty">
        <span class="lq__empty-h">No questions yet.</span>
        <span v-if="!compact" class="lq__empty-p lq__empty-p--owner">When a buyer asks something, you’ll get a notification. Clear photos and an honest description mean fewer questions.</span>
        <span v-else class="lq__empty-p">We’ll notify you when a buyer asks something.</span>
      </div>
    </template>

    <!-- ================= Buyer ================= -->
    <template v-else>
      <div class="lq__head">
        <h2 id="questions-h" ref="heading" class="lq__h" tabindex="-1">
          Questions <span class="lq__count num" aria-live="polite">{{ meta?.public_count ?? 0 }}</span>
        </h2>
        <span v-if="!compact" class="lq__sub">Ask {{ seller }} anything before you pay. Answers are public, so everyone buys with the same facts.</span>
        <span v-else class="lq__sub">Ask before you pay. Answers are public.</span>
      </div>

      <QuestionsHowTo v-if="compact" :seller-name="seller" compact />

      <QuestionAskBox
        v-if="showAskBox"
        ref="askBox"
        :seller-name="seller"
        :left="meta.questions_left_today"
        :compact="compact"
        :busy="asking"
        :server-kind="askKind"
        :error="askError"
        @ask="ask"
      />
      <div v-else-if="showLimit" class="lq__limit">
        <span class="lq__limit-label">{{ compact ? '3 OF 3 ASKED TODAY' : '3 OF 3 QUESTIONS ASKED TODAY' }}</span>
        <span class="lq__limit-h">You can ask {{ seller }} more tomorrow.</span>
        <span v-if="!compact" class="lq__limit-p">Or buy now: once you’ve paid, a private chat with {{ seller }} opens and your money stays held until you confirm the item.</span>
        <span v-else class="lq__limit-p">Or buy now: a private chat opens after you pay, and your money stays held.</span>
      </div>
      <div v-else-if="showLogin" class="lq__login">
        <span class="lq__login-label">Ask {{ seller }} a question</span>
        <RouterLink :to="loginLink" class="lq__login-btn">Log in to ask</RouterLink>
      </div>

      <QuestionItem v-for="q in mine" :key="q.id" :question="q" variant="mine" :seller-name="seller" :compact="compact" :now="now" />

      <div v-if="answered.length" class="lq__list">
        <QuestionItem v-for="q in answered" :key="q.id" :question="q" variant="public" :seller-name="seller" :compact="compact" :now="now" />
      </div>
      <div v-else-if="meta && !mine.length" class="lq__empty">
        <span class="lq__empty-h">No questions yet.</span>
        <span v-if="!compact" class="lq__empty-p">Be the first to ask. Once {{ seller }} answers, it shows here for every buyer.</span>
        <span v-else class="lq__empty-p">Be the first to ask. Answers show here for every buyer.</span>
      </div>
    </template>

    <button v-if="nextPage" type="button" class="lq__more" :disabled="loadingMore" @click="loadMore">
      {{ loadingMore ? 'Loading…' : 'Show more questions' }}
    </button>
    <p v-if="loadError" class="lq__error" role="alert">{{ loadError }}</p>
  </section>
</template>

<style scoped>
.lq {
  display: flex;
  flex-direction: column;
  gap: 28px;
  scroll-margin-top: 24px;
}

.lq--m {
  gap: 18px;
}

.lq--m.lq--owner {
  gap: 16px;
}

.lq__head {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-bottom: 18px;
  border-bottom: 2px solid var(--ink);
}

.lq--m .lq__head {
  gap: 6px;
  padding-bottom: 12px;
}

.lq__head--owner {
  flex-direction: row;
  justify-content: space-between;
  align-items: flex-end;
}

.lq__h {
  margin: 0;
  font-size: 56px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.lq--m .lq__h {
  font-size: 36px;
}

.lq__h:focus {
  outline: none;
}

.lq__count {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 400;
  color: var(--amber-ink);
}

.lq__sub {
  font-size: 17px;
  color: var(--ink-2);
}

.lq--m .lq__sub {
  font-size: 14px;
  line-height: 1.45;
}

.lq__pill {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.1em;
  padding: 8px 12px;
  border-radius: 999px;
  background: var(--accent);
  color: var(--ink);
}

.lq--m .lq__pill {
  font-size: 10px;
  letter-spacing: 0.08em;
  padding: 6px 10px;
}

.lq__list {
  display: flex;
  flex-direction: column;
}

.lq__answered-h {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.14em;
  color: var(--muted);
  padding-top: 8px;
}

.lq--m .lq__answered-h {
  font-size: 10px;
  letter-spacing: 0.12em;
  padding-top: 6px;
}

.lq__removed {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  border: 1.5px dashed rgba(18, 20, 16, 0.25);
  border-radius: 14px;
  font-size: 14px;
  color: var(--muted);
}

.lq__removed--row {
  margin: 14px 0;
}

.lq--m .lq__removed {
  padding: 8px 14px;
  border-radius: 12px;
  font-size: 13px;
}

.lq__undo {
  background: transparent;
  border: 0;
  min-height: 44px;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  color: var(--forest);
  text-decoration: underline;
  cursor: pointer;
}

.lq--m .lq__undo {
  font-size: 13px;
}

.lq__limit {
  background: var(--paper-deep);
  border-radius: 18px;
  padding: 22px 24px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.lq--m .lq__limit {
  border-radius: 16px;
  padding: 16px;
  gap: 6px;
}

.lq__limit-label {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--amber-ink);
}

.lq--m .lq__limit-label {
  font-size: 10px;
}

.lq__limit-h {
  font-size: 20px;
  font-weight: 700;
}

.lq--m .lq__limit-h {
  font-size: 17px;
}

.lq__limit-p {
  font-size: 15px;
  line-height: 1.5;
  color: var(--ink-2);
}

.lq--m .lq__limit-p {
  font-size: 14px;
}

/* Signed out: the ask box's frame with a Log in button (no reference). */
.lq__login {
  background: #ffffff;
  border-radius: 18px;
  padding: 22px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  box-shadow: 0 1px 0 rgba(18, 20, 16, 0.06);
}

.lq--m .lq__login {
  border-radius: 16px;
  padding: 16px;
  flex-direction: column;
  align-items: stretch;
  gap: 10px;
}

.lq__login-label {
  font-size: 18px;
  font-weight: 700;
}

.lq--m .lq__login-label {
  font-size: 16px;
}

.lq .lq__login-btn {
  height: 48px;
  padding: 0 24px;
  border-radius: 12px;
  background: var(--forest);
  color: var(--paper);
  font-size: 16px;
  font-weight: 700;
  text-decoration: none;
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
}

.lq__empty {
  border: 1.5px dashed rgba(18, 20, 16, 0.3);
  border-radius: 18px;
  padding: 36px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.lq--m .lq__empty {
  border-radius: 16px;
  padding: 22px;
  gap: 6px;
}

.lq__empty-h {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.lq--m .lq__empty-h {
  font-size: 20px;
  letter-spacing: 0;
}

.lq__empty-p {
  font-size: 16px;
  line-height: 1.55;
  color: var(--ink-2);
  max-width: 520px;
}

.lq__empty-p--owner {
  max-width: 560px;
}

.lq--m .lq__empty-p {
  font-size: 14px;
  line-height: 1.5;
}

.lq__more {
  align-self: flex-start;
  min-height: 44px;
  padding: 0 20px;
  border: 1.5px solid var(--ink);
  border-radius: 12px;
  background: transparent;
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
  cursor: pointer;
}

.lq__error {
  margin: 0;
  font-size: 15px;
  color: #a3361f;
}

.lq :is(button, a):focus-visible {
  outline: 2px solid var(--ink);
  outline-offset: 2px;
  box-shadow: 0 0 0 5px rgba(245, 184, 46, 0.45);
}
</style>
