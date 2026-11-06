<script setup>
import { computed, ref, useTemplateRef } from 'vue'

// The chat composer (design/deal-*): locked for the seller until the video
// is rated Good, read-only once the deal is closed, otherwise text + photo.
// TODO: proposing a meetup isn't designed yet; this is a minimal form in the
// composer's own style.
const props = defineProps({
  deal: { type: Object, required: true },
  mobile: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
  error: { type: String, default: '' },
})
const emit = defineEmits(['send', 'photo', 'meetup'])

const text = ref('')
const fileInput = useTemplateRef('file')
const closed = computed(() => props.deal.state === 'released' || props.deal.state === 'refunded')
const buyer = computed(() => props.deal.buyer_first_name)
const other = computed(() => props.deal.other.first_name)

function send() {
  const body = text.value.trim()
  if (!body || props.busy) return
  emit('send', body, () => (text.value = ''))
}

function onPhoto(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (file) emit('photo', file)
}

// ---- Meetup (undesigned) ----
const meeting = ref(false)
const when = ref('')
const place = ref('')
function propose() {
  if (!when.value || !place.value.trim()) return
  emit('meetup', { when: new Date(when.value).toISOString(), place: place.value.trim() }, () => {
    meeting.value = false
    when.value = ''
    place.value = ''
  })
}
</script>

<template>
  <div class="cp" :class="{ 'cp--m': mobile }">
    <div v-if="closed" class="cp-lock">
      <svg :width="mobile ? 16 : 18" :height="mobile ? 16 : 18" viewBox="0 0 24 24" fill="none" stroke="#5B5E55" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></svg>
      <span>{{ mobile ? 'Deal closed. Chat stays readable.' : 'This deal is closed. The chat stays readable for your records.' }}</span>
    </div>

    <div v-else-if="!deal.can.send_text" class="cp-lock">
      <svg :width="mobile ? 16 : 18" :height="mobile ? 16 : 18" viewBox="0 0 24 24" fill="none" stroke="#5B5E55" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></svg>
      <span>
        <template v-if="mobile">You can type after {{ buyer }} rates your video.</template>
        <template v-else>Your chat unlocks after {{ buyer }} rates your video. {{ buyer }} can already type.</template>
      </span>
    </div>

    <template v-else>
      <form v-if="meeting" class="cp-meet" @submit.prevent="propose">
        <label class="cp-meet__field">
          <span class="cp-meet__k">WHEN</span>
          <input v-model="when" type="datetime-local" required class="cp-input" />
        </label>
        <label class="cp-meet__field cp-meet__field--grow">
          <span class="cp-meet__k">WHERE</span>
          <input v-model="place" type="text" maxlength="160" required placeholder="A busy public place" class="cp-input" />
        </label>
        <div class="cp-meet__btns">
          <button type="button" class="cp-link" @click="meeting = false">Cancel</button>
          <button type="submit" class="cp-meet__go" :disabled="busy">Propose</button>
        </div>
      </form>

      <form class="cp-row" @submit.prevent="send">
        <button type="button" class="cp-attach" aria-label="Attach a photo" :disabled="busy" @click="fileInput?.click()">
          <svg :width="mobile ? 20 : 22" :height="mobile ? 20 : 22" viewBox="0 0 24 24" fill="none" stroke="#121410" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2.5" /><circle cx="9" cy="10" r="1.8" /><path d="M21 16l-5-5-8 9" /></svg>
        </button>
        <input ref="file" type="file" accept="image/jpeg,image/png,image/webp" hidden @change="onPhoto" />
        <input v-model="text" type="text" class="cp-input cp-text" :placeholder="`Message ${other}…`" aria-label="Message" maxlength="1000" />
        <button type="submit" class="cp-send" aria-label="Send" :disabled="busy || !text.trim()">
          <svg :width="mobile ? 18 : 20" :height="mobile ? 18 : 20" viewBox="0 0 24 24" fill="none" stroke="#F3EDE0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7" /></svg>
        </button>
      </form>
      <p v-if="error" class="cp-error" role="alert">{{ error }}</p>
      <div v-if="!mobile || deal.can.meetup" class="cp-foot">
        <span v-if="!mobile" class="cp-hint">
          {{ deal.contacts_masked ? 'Contact details are hidden until the video is rated Good.' : 'Chat is fully open. You can share contact details now.' }}
        </span>
        <button v-if="deal.can.meetup && !meeting" type="button" class="cp-link" @click="meeting = true">Propose a meetup</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.cp {
  background: var(--paper);
  border-top: 1px solid rgba(18, 20, 16, 0.14);
  padding: 14px 24px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cp-lock {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 52px;
  padding: 0 16px;
  box-sizing: border-box;
  background: var(--paper-deep);
  border-radius: 12px;
  color: var(--muted);
  font-size: 15px;
  font-weight: 600;
}

.cp-lock svg {
  flex-shrink: 0;
}

.cp-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.cp-attach,
.cp-send {
  width: 48px;
  height: 48px;
  flex-shrink: 0;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.cp-attach {
  border: 1.5px solid rgba(18, 20, 16, 0.22);
  background: #ffffff;
}

.cp-send {
  border: 0;
  background: var(--forest);
}

.cp-send:disabled {
  opacity: 0.6;
  cursor: default;
}

.cp-input {
  height: 48px;
  box-sizing: border-box;
  padding: 0 16px;
  background: #ffffff;
  border: 1.5px solid rgba(18, 20, 16, 0.22);
  border-radius: 12px;
  font-family: var(--font-display);
  font-size: 16px;
  color: var(--ink);
  outline: none;
}

.cp-input::placeholder {
  color: #8c8e85;
}

.cp-text {
  flex-grow: 1;
  min-width: 0;
}

.cp-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.cp-hint {
  font-size: 12px;
  color: var(--muted);
}

.cp-link {
  background: transparent;
  border: 0;
  padding: 0;
  min-height: 32px;
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 700;
  color: var(--forest);
  text-decoration: underline;
  cursor: pointer;
  white-space: nowrap;
}

.cp-error {
  margin: 0;
  font-size: 13px;
  color: #a3361f;
}

.cp-meet {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 10px;
  padding-bottom: 6px;
}

.cp-meet__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cp-meet__field--grow {
  flex-grow: 1;
  min-width: 180px;
}

.cp-meet__k {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: var(--muted);
}

.cp-meet__btns {
  display: flex;
  align-items: center;
  gap: 12px;
}

.cp-meet__go {
  height: 48px;
  padding: 0 18px;
  border: 0;
  border-radius: 12px;
  background: var(--forest);
  color: var(--paper);
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
}

.cp :is(button, input):focus-visible {
  outline: 2px solid var(--ink);
  outline-offset: 2px;
  box-shadow: 0 0 0 5px rgba(245, 184, 46, 0.45);
}

/* ---- Mobile ---- */

.cp--m {
  flex-shrink: 0;
  padding: 10px 12px calc(20px + env(safe-area-inset-bottom, 0px));
}

.cp--m .cp-lock {
  gap: 10px;
  min-height: 48px;
  padding: 8px 14px;
  font-size: 13px;
  line-height: 1.35;
}

.cp--m .cp-row {
  gap: 8px;
}

.cp--m .cp-attach,
.cp--m .cp-send {
  width: 44px;
  height: 44px;
}

.cp--m .cp-input {
  height: 44px;
  padding: 0 14px;
}

.cp--m .cp-foot {
  justify-content: flex-end;
}
</style>
