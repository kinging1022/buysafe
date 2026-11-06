<script setup>
import { computed } from 'vue'
import { qaAge, shortAgo } from '@/utils/format'
import AnswerEditor from './AnswerEditor.vue'

// One question, in one of four looks (design/qa-*):
//   public         an answered question, as buyers see it
//   mine           the buyer's own unanswered question (only they and the seller see it)
//   owner-pending  a question waiting for the owner's answer
//   owner-answered an answered question, as the owner sees it
// `editing` opens the inline AnswerEditor (answering, or editing an answer).
const props = defineProps({
  question: { type: Object, required: true },
  variant: { type: String, required: true },
  sellerName: { type: String, required: true }, // first name
  compact: { type: Boolean, default: false },
  now: { type: Date, default: () => new Date() },
  editing: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
  serverKind: { type: String, default: null },
  error: { type: String, default: '' },
})
const emit = defineEmits(['open-editor', 'submit', 'cancel', 'remove'])

const q = computed(() => props.question)
const askerName = computed(() => `${q.value.asker.first_name} ${q.value.asker.last_initial}.`)
const askerFirst = computed(() => q.value.asker.first_name)
const seller = computed(() => props.sellerName.toUpperCase())
const asked = computed(() => qaAge(q.value.created_at, props.now))
const answered = computed(() => (q.value.answered_at ? qaAge(q.value.answered_at, props.now) : ''))
const edited = computed(() => (q.value.edited ? ' · EDITED' : ''))
const askedLine = computed(() => {
  const ago = shortAgo(q.value.created_at, props.now)
  return ago === 'Just now' ? 'Asked just now.' : `Asked ${ago.toLowerCase()}.`
})
</script>

<template>
  <!-- ============ Buyer: public answered ============ -->
  <article v-if="variant === 'public'" class="qi" :class="{ 'qi--m': compact }">
    <div class="qi__q">
      <span class="qi__letter" aria-hidden="true">Q</span>
      <span class="qi__stack">
        <span class="qi__text">{{ q.text }}</span>
        <span class="qi__meta num">{{ askerName.toUpperCase() }} · {{ asked }}</span>
      </span>
    </div>
    <div class="qi__a">
      <span class="qi__letter qi__letter--a" aria-hidden="true">A</span>
      <span class="qi__stack">
        <span class="qi__answer">{{ q.answer }}</span>
        <span class="qi__meta qi__meta--a num">{{ seller }} · SELLER · {{ answered }}{{ edited }}</span>
      </span>
    </div>
  </article>

  <!-- ============ Buyer: my question, waiting ============ -->
  <article v-else-if="variant === 'mine'" class="qm" :class="{ 'qm--m': compact }">
    <span class="qm__label">
      <template v-if="!compact">YOUR QUESTION · WAITING FOR {{ seller }} · ONLY YOU AND {{ seller }} CAN SEE THIS</template>
      <template v-else>YOUR QUESTION · WAITING · ONLY YOU AND {{ seller }} SEE THIS</template>
    </span>
    <span v-if="!compact" class="qm__text"><span class="qm__letter" aria-hidden="true">Q</span>{{ q.text }}</span>
    <span v-else class="qm__text">{{ q.text }}</span>
    <span class="qm__note">
      <template v-if="!compact">{{ askedLine }} We’ll notify you when {{ sellerName }} answers.</template>
      <template v-else>We’ll notify you when {{ sellerName }} answers.</template>
    </span>
  </article>

  <!-- ============ Owner: needs an answer ============ -->
  <article v-else-if="variant === 'owner-pending'" class="qo" :class="{ 'qo--m': compact, 'qo--editing': editing }">
    <div v-if="!compact" class="qi__q">
      <span class="qi__letter" aria-hidden="true">Q</span>
      <span class="qi__stack">
        <span class="qo__text">{{ q.text }}</span>
        <span class="qi__meta num">{{ askerName.toUpperCase() }} · {{ asked }} · ONLY YOU AND {{ askerFirst.toUpperCase() }} SEE THIS UNTIL YOU ANSWER</span>
      </span>
    </div>
    <div v-else class="qo__head-m">
      <span class="qo__text">{{ q.text }}</span>
      <span class="qi__meta num">{{ askerName.toUpperCase() }} · {{ asked }} · PRIVATE UNTIL ANSWERED</span>
    </div>

    <AnswerEditor
      v-if="editing"
      :compact="compact"
      :busy="busy"
      :server-kind="serverKind"
      :error="error"
      submit-label="Post answer"
      @submit="emit('submit', $event)"
      @cancel="emit('cancel')"
    />
    <div v-else-if="!compact" class="qo__actions">
      <button type="button" class="qo__spam" :disabled="busy" @click="emit('remove')">Remove as spam</button>
      <button type="button" class="qo__answer" @click="emit('open-editor')">Answer</button>
    </div>
    <div v-else class="qo__actions-m">
      <button type="button" class="qo__spam-m" :disabled="busy" @click="emit('remove')">Remove as spam</button>
      <button type="button" class="qo__answer" @click="emit('open-editor')">Answer</button>
    </div>
  </article>

  <!-- ============ Owner: answered ============ -->
  <article v-else class="qi qi--owner" :class="{ 'qi--m': compact }">
    <template v-if="!compact">
      <div class="qi__q">
        <span class="qi__letter" aria-hidden="true">Q</span>
        <span class="qi__stack">
          <span class="qi__text">{{ q.text }}</span>
          <span class="qi__meta num">{{ askerName.toUpperCase() }} · {{ asked }}</span>
        </span>
      </div>
      <AnswerEditor
        v-if="editing"
        :initial="q.answer"
        :busy="busy"
        :server-kind="serverKind"
        :error="error"
        submit-label="Save answer"
        @submit="emit('submit', $event)"
        @cancel="emit('cancel')"
      />
      <div v-else class="qi__a">
        <span class="qi__letter qi__letter--a" aria-hidden="true">A</span>
        <span class="qi__stack qi__stack--owner">
          <span class="qi__answer">{{ q.answer }}</span>
          <span class="qi__tools">
            <span class="qi__meta qi__meta--a num">YOU · {{ answered }}{{ edited }}</span>
            <button type="button" class="qi__link" @click="emit('open-editor')">Edit answer</button>
            <button type="button" class="qi__link qi__link--red" :disabled="busy" @click="emit('remove')">Remove question</button>
          </span>
        </span>
      </div>
    </template>
    <template v-else>
      <span class="qo__text qo__text--answered">{{ q.text }}</span>
      <AnswerEditor
        v-if="editing"
        compact
        :initial="q.answer"
        :busy="busy"
        :server-kind="serverKind"
        :error="error"
        submit-label="Save answer"
        @submit="emit('submit', $event)"
        @cancel="emit('cancel')"
      />
      <template v-else>
        <div class="qi__a-m">
          <span class="qi__answer">{{ q.answer }}</span>
          <span class="qi__meta qi__meta--a">YOU · {{ answered }}{{ edited }}</span>
        </div>
        <div class="qi__tools-m">
          <button type="button" class="qi__link qi__link--44" @click="emit('open-editor')">Edit answer</button>
          <button type="button" class="qi__link qi__link--44 qi__link--red" :disabled="busy" @click="emit('remove')">Remove</button>
        </div>
      </template>
    </template>
  </article>
</template>

<style scoped>
/* ---- Q/A rows (public, owner answered) ---- */
.qi {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 24px 0;
  border-bottom: 1px solid rgba(18, 20, 16, 0.15);
}

.qi--owner {
  padding: 22px 0;
}

.qi--m {
  gap: 10px;
  padding: 18px 0;
}

.qi--m.qi--owner {
  padding: 16px 0;
}

.qi__q,
.qi__a {
  display: grid;
  grid-template-columns: 28px 1fr;
  gap: 8px;
}

.qi__a {
  margin-left: 36px;
  padding-left: 18px;
  border-left: 2px solid var(--released);
}

.qi--m .qi__q,
.qi--m .qi__a {
  grid-template-columns: 22px 1fr;
  gap: 6px;
}

.qi--m .qi__a {
  margin-left: 28px;
  padding-left: 12px;
}

.qi__letter {
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 600;
  color: var(--amber-ink);
  padding-top: 3px;
}

.qi__letter--a {
  color: var(--released);
  padding-top: 2px;
}

.qi--m .qi__letter {
  font-size: 13px;
  padding-top: 2px;
}

.qi--m .qi__letter--a {
  padding-top: 1px;
}

.qi__stack {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.qi__stack--owner {
  gap: 6px;
}

.qi--m .qi__stack {
  gap: 3px;
}

.qi__text {
  font-size: 18px;
  font-weight: 600;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.qi--m .qi__text {
  font-size: 16px;
}

.qi__answer {
  font-size: 16px;
  line-height: 1.55;
  color: #2a2c26;
  overflow-wrap: anywhere;
}

.qi--m .qi__answer {
  font-size: 15px;
  line-height: 1.5;
}

.qi__meta {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--muted);
}

.qi--m .qi__meta,
.qo--m .qi__meta {
  font-size: 10px;
}

.qo--m .qi__meta {
  font-size: 9px;
}

.qi__meta--a {
  color: var(--released);
}

.qi__tools {
  display: flex;
  gap: 18px;
  align-items: center;
  flex-wrap: wrap;
}

.qi__a-m {
  padding-left: 12px;
  border-left: 2px solid var(--released);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.qi__tools-m {
  display: flex;
  gap: 18px;
}

.qi__link {
  background: transparent;
  border: 0;
  padding: 0;
  min-height: 36px;
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 700;
  color: var(--forest);
  text-decoration: underline;
  cursor: pointer;
}

/* 44px touch target on the 36px-tall link. */
.qi__link:not(.qi__link--44) {
  position: relative;
}

.qi__link:not(.qi__link--44)::after {
  content: '';
  position: absolute;
  inset: -4px -4px;
}

.qi__link--44 {
  min-height: 44px;
}

.qi__link--red {
  color: #a3361f;
}

/* ---- My waiting question ---- */
.qm {
  background: #ffffff;
  border-radius: 16px;
  border-left: 4px solid var(--accent);
  padding: 20px 22px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.qm--m {
  border-radius: 14px;
  padding: 14px 16px;
  gap: 6px;
}

.qm__label {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--amber-ink);
}

.qm--m .qm__label {
  font-size: 9px;
  letter-spacing: 0.1em;
}

.qm__text {
  display: grid;
  grid-template-columns: 28px 1fr;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.qm--m .qm__text {
  display: block;
  font-size: 16px;
}

.qm__letter {
  font-family: var(--font-mono);
  font-size: 14px;
  color: var(--amber-ink);
  padding-top: 3px;
}

.qm__note {
  padding-left: 36px;
  font-size: 14px;
  color: var(--muted);
}

.qm--m .qm__note {
  padding-left: 0;
  font-size: 12px;
}

/* ---- Owner: needs an answer ---- */
.qo {
  background: #ffffff;
  border-radius: 18px;
  padding: 22px 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  border: 2px solid var(--accent);
}

.qo--m {
  border-radius: 16px;
  padding: 16px;
  gap: 12px;
}

.qo--editing {
  border-color: var(--ink);
}

.qo__text {
  font-size: 19px;
  font-weight: 600;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.qo--m .qo__text,
.qo__text--answered {
  font-size: 16px;
}

.qo__head-m {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.qo__actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 14px;
  border-top: 1px dashed rgba(18, 20, 16, 0.2);
}

.qo__actions-m {
  display: grid;
  grid-template-columns: 1fr 1.3fr;
  gap: 8px;
}

.qo__spam {
  background: transparent;
  border: 0;
  padding: 0;
  min-height: 44px;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  color: #a3361f;
  text-decoration: underline;
  cursor: pointer;
}

.qo__spam-m {
  height: 46px;
  border: 1.5px solid rgba(163, 54, 31, 0.4);
  background: transparent;
  border-radius: 12px;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
  color: #a3361f;
  cursor: pointer;
}

.qo__answer {
  height: 46px;
  padding: 0 22px;
  border: 0;
  border-radius: 12px;
  background: var(--forest);
  color: var(--paper);
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
}

.qo--m .qo__answer {
  padding: 0;
}

button:focus-visible {
  outline: 2px solid var(--ink);
  outline-offset: 2px;
  box-shadow: 0 0 0 5px rgba(245, 184, 46, 0.45);
}
</style>
