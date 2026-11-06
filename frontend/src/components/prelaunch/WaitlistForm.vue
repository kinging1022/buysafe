<script setup>
// The pre-launch waitlist form, used in the hero and the final section.
// Markup, copy and behaviour from design/prelaunch.reference.html.
import { ref, useId } from 'vue'
import { ROLES, WAITLIST_STATES, attribution, joinWaitlist, normalizeWaitlistPhone } from './waitlist'

const STATE_KEY = 'bs_state'
const MESSAGES = {
  phone: 'Enter a Nigerian mobile number, like 0803 123 4567.',
  state: 'Choose your state.',
  throttled: 'Too many tries. Please wait a minute and try again.',
  failed: 'Something went wrong. Please try again.',
}
const STATE_LABELS = Object.fromEntries(WAITLIST_STATES)

const uid = useId()
const ids = { phone: `phone-${uid}`, state: `state-${uid}`, company: `company-${uid}` }

const phone = ref('')
const state = ref(savedState())
const role = ref('buy')
const company = ref('') // honeypot
const message = ref('')
const submitting = ref(false)
const joinedState = ref('')
const phoneInput = ref(null)
const stateSelect = ref(null)

function savedState() {
  if (import.meta.env.SSR) return '' // prerendering: no stored state
  try {
    const s = localStorage.getItem(STATE_KEY)
    return s in STATE_LABELS ? s : ''
  } catch {
    return ''
  }
}

function fail(text, el) {
  message.value = text
  el?.focus()
}

async function onSubmit() {
  message.value = ''
  const normalized = normalizeWaitlistPhone(phone.value)
  if (!normalized) return fail(MESSAGES.phone, phoneInput.value)
  if (!state.value) return fail(MESSAGES.state, stateSelect.value)

  submitting.value = true
  const status = await joinWaitlist({
    phone: normalized,
    state: state.value,
    role: role.value,
    company: company.value,
    ...attribution(),
  })
  submitting.value = false

  // 200 for new and already-listed numbers alike.
  if (status >= 200 && status < 300) {
    try {
      localStorage.setItem(STATE_KEY, state.value)
    } catch {
      // private mode / storage blocked: nothing to remember
    }
    joinedState.value = state.value
  } else {
    fail(status === 429 ? MESSAGES.throttled : MESSAGES.failed)
  }
}

defineExpose({
  selectRole(value) {
    role.value = value
  },
})
</script>

<template>
  <div class="join" :class="{ 'is-done': joinedState }">
    <form novalidate @submit.prevent="onSubmit">
      <div class="join-row">
        <div class="field">
          <label :for="ids.phone">Phone number</label>
          <div class="phone"><span>+234</span><input :id="ids.phone" ref="phoneInput" v-model="phone" name="phone" type="tel" inputmode="numeric" autocomplete="tel-national" placeholder="803 123 4567" required></div>
        </div>
        <div class="field">
          <label :for="ids.state">Your state</label>
          <select :id="ids.state" ref="stateSelect" v-model="state" name="state" required>
            <option value="" disabled>Choose</option>
            <option v-for="[key, label] in WAITLIST_STATES" :key="key" :value="key">{{ label }}</option>
          </select>
        </div>
        <button class="btn" type="submit" :disabled="submitting">{{ submitting ? 'Joining…' : 'Join the waitlist' }}</button>
      </div>
      <fieldset class="roles">
        <legend>I want to</legend>
        <label v-for="[value, label] in ROLES" :key="value" class="chip"><input v-model="role" type="radio" name="role" :value="value"><span>{{ label }}</span></label>
      </fieldset>
      <p class="msg" :class="{ err: message }" role="status" aria-live="polite">{{ message }}</p>
      <div class="hp" aria-hidden="true">
        <label :for="ids.company">Company</label>
        <input :id="ids.company" v-model="company" name="company" type="text" tabindex="-1" autocomplete="off">
      </div>
    </form>
    <div class="done" role="status">
      <strong>You’re on the list.</strong>
      <p>We’ll text you when buysafe opens in <span class="done-state">{{ STATE_LABELS[joinedState] || 'your state' }}</span>.</p>
    </div>
  </div>
</template>
