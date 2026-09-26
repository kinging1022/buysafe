<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, useTemplateRef } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { resetReceipt } from '@/config/receipts'
import { isValidNational, toE164 } from '@/utils/phone'
import { passwordRules, passwordRulesError } from '@/utils/validation'
import AuthLayout from '@/components/auth/AuthLayout.vue'
import ReceiptProgress from '@/components/auth/ReceiptProgress.vue'
import FormField from '@/components/auth/FormField.vue'
import PhoneInput from '@/components/auth/PhoneInput.vue'
import OtpInput from '@/components/auth/OtpInput.vue'
import PasswordInput from '@/components/auth/PasswordInput.vue'

// One route, four steps: 1 phone -> 2 SMS code -> 3 new password -> 4 done.
// The reset token lives only in the store's memory, so a refresh restarts at 1.
const auth = useAuthStore()
const router = useRouter()

const GENERIC_ERROR = 'Something went wrong on our side. Check your connection and try again.'

const step = ref(1)
const loading = ref(false)
const error = ref('') // general error box for the current step

const receipt = computed(() => resetReceipt(step.value))

async function goTo(n) {
  step.value = n
  error.value = ''
  await nextTick()
  // Move focus into the new step so keyboard and screen-reader users follow along.
  if (n === 1) document.getElementById('rp-phone')?.focus()
  else if (n === 2) otp.value?.focus()
  else if (n === 3) document.getElementById('rp-password')?.focus()
  else document.getElementById('rp-done')?.focus()
}

function back() {
  if (step.value === 1 || step.value === 4) return router.push('/login')
  if (step.value === 3) auth.reset.token = null
  goTo(step.value - 1)
}

// ---- Step 1: phone ----

const phone = ref('')
const phoneTouched = ref(false)
const phoneServerError = ref('')
const phoneError = computed(() => {
  if (phoneServerError.value) return phoneServerError.value
  return phoneTouched.value && !isValidNational(phone.value) ? 'Enter a valid Nigerian mobile number.' : ''
})

async function requestCode() {
  phoneTouched.value = true
  error.value = ''
  if (!isValidNational(phone.value)) return document.getElementById('rp-phone')?.focus()

  loading.value = true
  const res = await auth.requestReset(toE164(phone.value))
  loading.value = false
  if (res.ok) {
    code.value = ''
    codeError.value = ''
    return goTo(2)
  }
  if (res.status === 400 && res.data?.phone) phoneServerError.value = res.data.phone.join(' ')
  else error.value = res.data?.detail || GENERIC_ERROR
}

// ---- Step 2: SMS code ----

const otp = useTemplateRef('otp')
const code = ref('')
const codeError = ref('')
const resending = ref(false)

const now = ref(Date.now())
let timer
onMounted(() => {
  // A fresh start every time: nothing from an earlier visit carries over.
  auth.clearReset()
  timer = setInterval(() => (now.value = Date.now()), 1000)
  document.getElementById('rp-phone')?.focus()
})
onBeforeUnmount(() => {
  clearInterval(timer)
  auth.clearReset()
})

const secondsLeft = computed(() => Math.max(0, Math.ceil((auth.reset.resendAvailableAt - now.value) / 1000)))
const countdown = computed(() => {
  const s = secondsLeft.value
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
})

async function verifyCode() {
  if (loading.value) return
  if (!/^\d{6}$/.test(code.value)) {
    codeError.value = 'Enter the 6-digit code.'
    return otp.value?.focus()
  }
  codeError.value = ''
  loading.value = true
  const res = await auth.verifyReset(code.value)
  loading.value = false

  if (res.ok) return goTo(3)
  if (res.data?.code === 'invalid_code') {
    const left = res.data.attempts_left
    codeError.value = `That code isn’t right. ${left} ${left === 1 ? 'try' : 'tries'} left.`
  } else if (res.data?.code === 'expired') {
    codeError.value = 'This code has expired. Request a new one.'
    auth.reset.resendAvailableAt = 0 // enable Resend now
  } else {
    codeError.value = res.data?.detail || GENERIC_ERROR
  }
  otp.value?.clear()
}

async function resend() {
  if (secondsLeft.value > 0 || resending.value) return
  resending.value = true
  const res = await auth.requestReset(auth.reset.phone)
  resending.value = false
  if (res.ok) codeError.value = ''
  else codeError.value = res.data?.detail || 'We couldn’t send a new code. Try again in a moment.'
}

// ---- Step 3: new password ----

const pw = reactive({ password: '', confirm: '' })
const pwSubmitted = ref(false)
const pwServer = reactive({ password: '', confirm: '' })
const rules = computed(() => passwordRules(pw.password))
const passwordsMatch = computed(() => pw.confirm !== '' && pw.confirm === pw.password)
const pwErrors = computed(() => ({
  password: pwServer.password || (pwSubmitted.value ? passwordRulesError(rules.value) : ''),
  confirm:
    pwServer.confirm ||
    ((pwSubmitted.value || pw.confirm) && pw.confirm !== pw.password ? 'Passwords don’t match yet.' : ''),
}))

async function savePassword() {
  pwSubmitted.value = true
  pwServer.password = pwServer.confirm = ''
  error.value = ''
  if (pwErrors.value.password || pwErrors.value.confirm) {
    await nextTick()
    return document.getElementById(pwErrors.value.password ? 'rp-password' : 'rp-confirm')?.focus()
  }

  loading.value = true
  const res = await auth.confirmReset(pw.password, pw.confirm)
  loading.value = false
  if (res.ok) {
    pw.password = pw.confirm = ''
    return goTo(4)
  }
  if (res.data?.code === 'reset_token_invalid') {
    await goTo(1)
    error.value = res.data.detail
    return
  }
  if (res.status === 400 && res.data) {
    pwServer.password = res.data.new_password?.join(' ') || ''
    pwServer.confirm = res.data.new_password_confirm?.join(' ') || ''
    if (pwServer.password || pwServer.confirm) return
  }
  error.value = res.data?.detail || GENERIC_ERROR
}
</script>

<template>
  <AuthLayout :step="step" :steps="3" :step-label="step > 3 ? 'DONE' : ''">
    <template #mobile-left>
      <button type="button" class="back" @click="back">← Back</button>
    </template>
    <template #headline>
      Forgot it? <span class="auth-d">Happens. </span>Your money <span class="accent">didn’t go anywhere.</span>
    </template>
    <template #receipt><ReceiptProgress v-bind="receipt" /></template>
    <template #top>
      <div class="top">
        <button type="button" class="top__back" @click="back">← Back</button>
        <span>Remembered it? <RouterLink to="/login" class="strong">Log in</RouterLink></span>
      </div>
    </template>

    <div class="rp">
      <div v-if="error" class="af-box rp__error" role="alert">
        <span class="af-box__label af-box__label--error">ERROR</span> <span>{{ error }}</span>
      </div>

      <!-- Step 1 -->
      <form v-if="step === 1" class="step step--1" novalidate @submit.prevent="requestCode">
        <div class="step__head">
          <div class="af-eyebrow auth-d">RESET PASSWORD</div>
          <h2 class="af-h2 step__title">What number did you sign up with?</h2>
          <p class="step__lede">
            We’ll text a 6-digit code to it.<span class="auth-d">
              No code, no reset. That’s how we keep your wallet yours.</span
            >
          </p>
        </div>
        <FormField id="rp-phone" label="Phone number" :error="phoneError">
          <template #default="{ id, describedby, invalid }">
            <PhoneInput
              :id="id"
              v-model="phone"
              :invalid="invalid"
              :describedby="describedby"
              @update:model-value="phoneServerError = ''"
              @blur="phoneTouched = !!phone"
            />
          </template>
        </FormField>
        <button type="submit" class="af-btn" :disabled="loading">{{ loading ? 'Sending…' : 'Send code  →' }}</button>
      </form>

      <!-- Step 2 -->
      <form v-else-if="step === 2" class="step" novalidate @submit.prevent="verifyCode">
        <div class="step__head">
          <div class="af-eyebrow auth-d">CHECK YOUR SMS</div>
          <h2 class="af-h2 step__title">Enter the 6-digit code.</h2>
          <p class="step__lede">Sent to <span class="phone">{{ auth.reset.masked }}</span></p>
        </div>
        <fieldset class="otp-set">
          <legend class="visually-hidden">Verification code</legend>
          <OtpInput
            ref="otp"
            v-model="code"
            :invalid="!!codeError"
            :disabled="loading"
            :describedby="codeError ? 'rp-code-error' : undefined"
            @complete="verifyCode"
          />
        </fieldset>
        <p id="rp-code-error" class="af-error" aria-live="polite">{{ codeError }}</p>
        <div class="resend">
          Didn’t get it?
          <template v-if="secondsLeft > 0">
            Resend in <span class="resend__time" aria-live="off">{{ countdown }}</span>
          </template>
          <button v-else type="button" class="af-link-btn" :disabled="resending" @click="resend">Resend code</button>
        </div>
        <button type="submit" class="af-btn" :disabled="loading">{{ loading ? 'Verifying…' : 'Verify code' }}</button>
      </form>

      <!-- Step 3 -->
      <form v-else-if="step === 3" class="step step--3" novalidate @submit.prevent="savePassword">
        <div class="step__head">
          <div class="af-eyebrow auth-d">NEW PASSWORD</div>
          <h2 class="af-h2 step__title">Pick a new one.</h2>
        </div>
        <FormField id="rp-password" label="New password" :error="pwErrors.password">
          <template #default="{ id, describedby, invalid }">
            <PasswordInput
              :id="id"
              v-model="pw.password"
              autocomplete="new-password"
              spaced
              :rules="rules"
              :invalid="invalid"
              :describedby="describedby"
              @update:model-value="pwServer.password = ''"
            />
          </template>
        </FormField>
        <FormField id="rp-confirm" label="Confirm new password" :error="pwErrors.confirm">
          <template #default="{ id, describedby, invalid }">
            <PasswordInput
              :id="id"
              v-model="pw.confirm"
              autocomplete="new-password"
              spaced
              :invalid="invalid"
              :describedby="describedby"
              @update:model-value="pwServer.confirm = ''"
            />
          </template>
          <template v-if="passwordsMatch && !pwErrors.confirm" #error>
            <span class="match">✓ Passwords match</span>
          </template>
        </FormField>
        <button type="submit" class="af-btn" :disabled="loading">{{ loading ? 'Saving…' : 'Save new password' }}</button>
        <div class="af-box">
          <span class="af-box__label af-box__label--note">NOTE</span>
          <span>For your safety, you’ll be logged out on every other device.</span>
        </div>
      </form>

      <!-- Done -->
      <div v-else class="step step--done">
        <span class="done__stamp auth-m" aria-hidden="true">RESET</span>
        <div class="step__head">
          <div class="af-eyebrow done__eyebrow auth-d">ALL SET</div>
          <h2 id="rp-done" class="af-h2 step__title done__title" tabindex="-1">
            Password changed. <span class="done__accent">You’re back in.</span>
          </h2>
          <p class="step__lede">
            Log in with your new password.
            <span class="auth-d">Any other devices using your account have been signed out.</span>
            <span class="auth-m">Other devices have been signed out.</span>
          </p>
        </div>
        <RouterLink to="/login" class="af-btn done__login">Log in  →</RouterLink>
      </div>

      <p class="rp__switch auth-m">Remembered it? <RouterLink to="/login" class="strong">Log in</RouterLink></p>
    </div>
  </AuthLayout>
</template>

<style scoped>
.strong {
  font-weight: 700;
}

.back,
.top__back {
  background: transparent;
  border: 0;
  padding: 0;
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 600;
  min-height: 44px;
  cursor: pointer;
}

.back {
  color: var(--paper);
}

.top__back {
  color: var(--forest);
}

.top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.rp {
  width: 460px;
  max-width: 100%;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.step {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.step--3 {
  gap: 22px;
}

.step__head {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.step__lede {
  margin: 0;
  font-size: 17px;
  line-height: 1.5;
  color: var(--ink-2);
}

.phone {
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--ink);
}

.otp-set {
  border: 0;
  margin: 0;
  padding: 0;
  min-width: 0;
}

/* The error sits between the boxes and the resend line without extra gap. */
.otp-set + .af-error {
  margin-top: -14px;
}

.resend {
  font-size: 14px;
  color: var(--muted);
}

.resend .af-link-btn {
  min-height: 0;
  position: relative;
}

.resend .af-link-btn::after {
  content: '';
  position: absolute;
  inset: -13px -6px;
}

.resend__time {
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--ink);
}

.match {
  color: var(--released);
}

.done__eyebrow {
  color: var(--released);
}

.done__title {
  font-size: 52px;
}

.done__title:focus {
  outline: none;
}

.done__accent {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 400;
  color: var(--released);
}

.rp .done__login {
  text-decoration: none;
  color: var(--paper);
}

.done__stamp {
  align-self: flex-start;
  transform: rotate(-6deg);
  border: 2.5px solid var(--released);
  outline: 1.5px solid var(--released);
  outline-offset: 3px;
  color: var(--released);
  font-family: var(--font-mono);
  font-weight: 600;
  font-size: 14px;
  letter-spacing: 0.14em;
  padding: 5px 10px;
  border-radius: 4px;
}

.rp__switch {
  margin: auto 0 0;
  padding-top: 24px;
  font-size: 15px;
  color: var(--ink-2);
  text-align: center;
}

@media (max-width: 899px) {
  .rp {
    width: auto;
    padding: 32px 0;
    gap: 22px;
  }

  .step {
    gap: 22px;
  }

  .step--3 {
    gap: 20px;
  }

  .step__head {
    gap: 8px;
  }

  .step__title {
    font-size: 28px;
    line-height: 1.1;
    letter-spacing: -0.03em;
  }

  .step__lede {
    font-size: 16px;
  }

  /* The code, resend line and button share the step's gap on mobile too. */
  .otp-set + .af-error {
    margin-top: -12px;
  }

  .step--done .step__head {
    gap: 22px;
  }

  .done__title {
    font-size: 34px;
    line-height: 1.05;
    letter-spacing: -0.04em;
  }
}
</style>
