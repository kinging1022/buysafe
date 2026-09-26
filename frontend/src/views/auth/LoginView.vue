<script setup>
import { nextTick, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { isValidNational, toE164 } from '@/utils/phone'
import { safeRedirect } from '@/router/redirect'
import AuthLayout from '@/components/auth/AuthLayout.vue'
import ReceiptHeld from '@/components/auth/ReceiptHeld.vue'
import FormField from '@/components/auth/FormField.vue'
import PhoneInput from '@/components/auth/PhoneInput.vue'
import PasswordInput from '@/components/auth/PasswordInput.vue'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const form = reactive({ phone: '', password: '' })
const touched = reactive({ phone: false, password: false })
const submitted = ref(false)
const generalError = ref('')
const loading = ref(false)

const clientErrors = () => ({
  phone: isValidNational(form.phone) ? '' : 'Enter a valid Nigerian mobile number.',
  password: form.password ? '' : 'Enter your password.',
})

function errorFor(field) {
  return touched[field] || submitted.value ? clientErrors()[field] : ''
}

async function submit() {
  submitted.value = true
  generalError.value = ''
  const errs = clientErrors()
  if (errs.phone || errs.password) {
    await nextTick()
    document.getElementById(errs.phone ? 'li-phone' : 'li-password')?.focus()
    return
  }

  loading.value = true
  const phone = toE164(form.phone)
  const res = await auth.login(phone, form.password)
  loading.value = false

  if (res.ok) {
    auth.signedIn(res.data)
    return router.replace(safeRedirect(route.query.redirect, '/profile'))
  }
  if (res.status === 403 && res.data?.code === 'phone_unverified') {
    // The backend has already sent a fresh code.
    auth.setPending(phone, res.data.masked_phone, res.data.resend_available_in)
    return router.push({ path: '/verify', query: route.query })
  }
  // Never say which of the two was wrong.
  generalError.value =
    res.data?.code === 'invalid_credentials'
      ? 'Phone number or password is incorrect.'
      : res.data?.detail || 'Something went wrong on our side. Check your connection and try again.'
}
</script>

<template>
  <AuthLayout large>
    <template #headline>
      Welcome back. Your money is <span class="accent">where you left it.</span>
    </template>
    <template #receipt><ReceiptHeld /></template>
    <template #top>
      <span>New to buysafe?</span><RouterLink to="/signup" class="strong">Create an account</RouterLink>
    </template>

    <form class="form" novalidate @submit.prevent="submit">
      <div class="form__head">
        <div class="af-eyebrow auth-d">LOG IN</div>
        <h2 class="af-h2">Good to see you.</h2>
      </div>

      <FormField id="li-phone" label="Phone number" :error="errorFor('phone')">
        <template #default="{ id, describedby, invalid }">
          <PhoneInput
            :id="id"
            v-model="form.phone"
            :invalid="invalid"
            :describedby="describedby"
            @update:model-value="generalError = ''"
            @blur="touched.phone = true"
          />
        </template>
      </FormField>

      <FormField id="li-password" label="Password" :error="errorFor('password')">
        <template #label-aside>
          <RouterLink to="/reset-password" class="forgot">Forgot password?</RouterLink>
        </template>
        <template #default="{ id, describedby, invalid }">
          <PasswordInput
            :id="id"
            v-model="form.password"
            placeholder="Your password"
            autocomplete="current-password"
            :invalid="invalid"
            :describedby="describedby"
            @update:model-value="generalError = ''"
            @blur="touched.password = true"
          />
        </template>
      </FormField>

      <div v-if="generalError" class="af-box" role="alert">
        <span class="af-box__label af-box__label--error">ERROR</span> <span>{{ generalError }}</span>
      </div>

      <button type="submit" class="af-btn form__submit" :disabled="loading">
        {{ loading ? 'Logging in…' : 'Log in →' }}
      </button>

      <div class="or auth-d" aria-hidden="true"><span></span>OR<span></span></div>
      <RouterLink to="/signup" class="af-btn-secondary auth-d">Create a new account</RouterLink>

      <p class="form__switch auth-m">
        New to buysafe? <RouterLink to="/signup" class="strong">Create an account</RouterLink>
      </p>
    </form>
  </AuthLayout>
</template>

<style scoped>
.strong {
  font-weight: 700;
}

.forgot {
  font-weight: 600;
  font-size: 14px;
  /* 44px hit area without changing the label row */
  padding-block: 12px;
  margin-block: -12px;
}

.form {
  width: 440px;
  max-width: 100%;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.form__head {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 6px;
}

.form__submit {
  margin-top: 6px;
}

.or {
  display: flex;
  align-items: center;
  gap: 14px;
  color: #8c8e85;
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.1em;
}

.or span {
  flex-grow: 1;
  border-top: 1px solid rgba(18, 20, 16, 0.15);
}

.form__switch {
  margin: auto 0 0;
  font-size: 15px;
  color: var(--ink-2);
  text-align: center;
}

@media (max-width: 899px) {
  .form {
    width: auto;
    padding: 32px 0;
    gap: 20px;
  }

  .form__head {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
    margin: 0;
  }

  .form__submit {
    margin-top: 8px;
  }
}
</style>
