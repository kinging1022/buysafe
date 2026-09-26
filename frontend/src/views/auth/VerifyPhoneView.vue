<script setup>
import { computed, onBeforeUnmount, onMounted, ref, useTemplateRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { safeRedirect } from '@/router/redirect'
import AuthLayout from '@/components/auth/AuthLayout.vue'
import ReceiptProgress from '@/components/auth/ReceiptProgress.vue'
import { SIGNUP_RECEIPT } from '@/config/receipts'
import OtpInput from '@/components/auth/OtpInput.vue'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const otp = useTemplateRef('otp')
const code = ref('')
const loading = ref(false)
const resending = ref(false)
const error = ref('')

// Countdown to resend, ticking from the stored resendAvailableAt.
const now = ref(Date.now())
let timer
onMounted(() => {
  timer = setInterval(() => (now.value = Date.now()), 1000)
  otp.value?.focus()
})
onBeforeUnmount(() => clearInterval(timer))

const secondsLeft = computed(() => Math.max(0, Math.ceil((auth.resendAvailableAt - now.value) / 1000)))
const countdown = computed(() => {
  const s = secondsLeft.value
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
})
const canResend = computed(() => secondsLeft.value === 0 && !resending.value)

async function submit() {
  if (loading.value) return
  if (!/^\d{6}$/.test(code.value)) {
    error.value = 'Enter the 6-digit code.'
    otp.value?.focus()
    return
  }
  error.value = ''
  loading.value = true
  const res = await auth.verify(code.value)
  loading.value = false

  if (res.ok) {
    auth.signedIn(res.data)
    return router.replace(safeRedirect(route.query.redirect))
  }
  if (res.data?.code === 'invalid_code') {
    const left = res.data.attempts_left
    error.value = `That code isn’t right. ${left} ${left === 1 ? 'try' : 'tries'} left.`
  } else if (res.data?.code === 'expired') {
    error.value = 'This code has expired. Request a new one.'
    auth.setResendIn(0) // enable Resend now
  } else {
    error.value = res.data?.detail || 'Something went wrong on our side. Check your connection and try again.'
  }
  otp.value?.clear()
}

async function resend() {
  if (!canResend.value) return
  resending.value = true
  const res = await auth.resend()
  resending.value = false
  if (res.ok) {
    error.value = ''
    auth.setResendIn(res.data.resend_available_in)
  } else if (res.status === 429) {
    auth.setResendIn(res.data?.retry_after ?? 60)
  } else {
    error.value = res.data?.detail || 'We couldn’t send a new code. Try again in a moment.'
  }
}

function changeNumber() {
  // The sign-up form refills from auth.signupDraft.
  auth.clearPending()
  router.push('/signup')
}
</script>

<template>
  <AuthLayout :step="2">
    <template #mobile-left>
      <a href="/signup" class="back" @click.prevent="changeNumber">← Back</a>
    </template>
    <template #headline>
      One code. So everyone <span class="auth-d">you meet </span>is <span class="accent">who they say.</span>
    </template>
    <template #receipt><ReceiptProgress v-bind="SIGNUP_RECEIPT[2]" /></template>
    <template #top>
      <div class="top">
        <a href="/signup" class="top__back" @click.prevent="changeNumber">← Back</a>
        <span>Wrong number? <a href="/signup" class="strong" @click.prevent="changeNumber">Change it</a></span>
      </div>
    </template>

    <form class="form" novalidate @submit.prevent="submit">
      <div class="form__head">
        <div class="af-eyebrow auth-d">VERIFY YOUR PHONE</div>
        <h2 class="af-h2 form__title">Enter the 6-digit code.</h2>
        <p class="form__sent">
          <span class="auth-d">We sent it by SMS to </span><span class="auth-m">Sent by SMS to </span
          ><span class="phone">{{ auth.maskedPhone }}</span
          ><span class="auth-m">. <a href="/signup" class="strong" @click.prevent="changeNumber">Change</a></span>
        </p>
      </div>

      <fieldset class="otp-set">
        <legend class="visually-hidden">Verification code</legend>
        <OtpInput
          ref="otp"
          v-model="code"
          :invalid="!!error"
          :disabled="loading"
          :describedby="error ? 'verify-error' : undefined"
          @complete="submit"
        />
        <div class="resend">
          <span>
            Didn’t get it?
            <template v-if="secondsLeft > 0">
              Resend in <span class="resend__time" aria-live="off">{{ countdown }}</span>
            </template>
            <button v-else type="button" class="af-link-btn auth-m" :disabled="!canResend" @click="resend">
              Resend code
            </button>
          </span>
          <button type="button" class="af-link-btn auth-d" :disabled="!canResend" @click="resend">
            Resend code
          </button>
        </div>
      </fieldset>

      <div v-if="error" id="verify-error" class="af-box" role="alert">
        <span class="af-box__label af-box__label--error">ERROR</span> <span>{{ error }}</span>
      </div>

      <button type="submit" class="af-btn" :disabled="loading">
        {{ loading ? 'Verifying…' : 'Verify and create account' }}
      </button>

      <div class="af-box note">
        <span class="af-box__label af-box__label--note">NOTE</span>
        <span class="auth-d">buysafe will never call you to ask for this code. Don’t share it with anyone, including a “buyer” or “seller”.</span>
        <span class="auth-m">We’ll never call to ask for this code. Don’t share it with anyone, even a “buyer”.</span>
      </div>
    </form>
  </AuthLayout>
</template>

<style scoped>
.strong {
  font-weight: 700;
}

.back {
  display: flex;
  align-items: center;
  min-height: 44px;
  font-size: 15px;
  font-weight: 600;
  text-decoration: none;
}

.top {
  display: flex;
  justify-content: space-between;
  width: 100%;
}

.top__back {
  font-weight: 600;
  text-decoration: none;
}

.form {
  width: 480px;
  max-width: 100%;
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.form__head {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form__sent {
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
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.resend {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  color: var(--muted);
}

/* 44px hit area (invisible) without changing the row height. */
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

@media (max-width: 899px) {
  .form {
    width: auto;
    padding: 32px 0;
    gap: 24px;
  }

  .form__head {
    gap: 8px;
  }

  .form__title {
    font-size: 28px;
    line-height: 1.1;
    letter-spacing: -0.03em;
  }

  .form__sent {
    font-size: 16px;
  }

  /* Mobile spaces the code, the resend line and the button evenly. */
  .otp-set {
    gap: 24px;
  }

  .note {
    margin-top: auto;
  }
}
</style>
