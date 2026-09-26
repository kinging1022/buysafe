<script setup>
import { computed, nextTick, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { isValidNational, toE164 } from '@/utils/phone'
import { nameError, passwordRules, passwordRulesError } from '@/utils/validation'
import AuthLayout from '@/components/auth/AuthLayout.vue'
import ReceiptProgress from '@/components/auth/ReceiptProgress.vue'
import { SIGNUP_RECEIPT } from '@/config/receipts'
import FormField from '@/components/auth/FormField.vue'
import PhoneInput from '@/components/auth/PhoneInput.vue'
import PasswordInput from '@/components/auth/PasswordInput.vue'

const auth = useAuthStore()
const router = useRouter()

// Restored from the store after "Change it" on /verify. Passwords never are.
const form = reactive({
  firstName: auth.signupDraft.firstName,
  lastName: auth.signupDraft.lastName,
  phone: auth.signupDraft.phoneDigits,
  password: '',
  confirm: '',
})

// Errors show after a field is blurred or the form is submitted, never while
// typing into an untouched field.
const touched = reactive({ firstName: false, lastName: false, phone: false, password: false, confirm: false })
const submitted = ref(false)
const serverErrors = reactive({})
const phoneTaken = ref(false)
const generalError = ref('')
const loading = ref(false)

const rules = computed(() => passwordRules(form.password))

const clientErrors = computed(() => ({
  firstName: nameError(form.firstName, 'first name'),
  lastName: nameError(form.lastName, 'last name'),
  phone: isValidNational(form.phone) ? '' : 'Enter a valid Nigerian mobile number.',
  password: passwordRulesError(rules.value),
  confirm: form.confirm === form.password ? '' : 'Passwords don’t match yet.',
}))

function shown(field) {
  if (serverErrors[field]) return serverErrors[field]
  // The mismatch shows once they've typed in the confirm field.
  if (field === 'confirm' && !submitted.value && !form.confirm) return ''
  // The live checklist covers the password until they submit.
  if (field === 'password' && !submitted.value) return ''
  return touched[field] || submitted.value ? clientErrors.value[field] : ''
}

const errors = computed(() => ({
  firstName: shown('firstName'),
  lastName: shown('lastName'),
  phone: phoneTaken.value ? ' ' : shown('phone'),
  password: shown('password'),
  confirm: shown('confirm'),
}))

// Editing a field clears its server-side error.
function edited(field) {
  delete serverErrors[field]
  if (field === 'phone') phoneTaken.value = false
  generalError.value = ''
}

const FIELD_IDS = {
  firstName: 'su-first',
  lastName: 'su-last',
  phone: 'su-phone',
  password: 'su-password',
  confirm: 'su-confirm',
}

async function focusFirstInvalid() {
  await nextTick()
  const first = Object.keys(FIELD_IDS).find((f) => errors.value[f])
  if (first) document.getElementById(FIELD_IDS[first])?.focus()
}

async function submit() {
  submitted.value = true
  generalError.value = ''
  if (Object.values(clientErrors.value).some(Boolean)) return focusFirstInvalid()

  auth.signupDraft = { firstName: form.firstName, lastName: form.lastName, phoneDigits: form.phone }
  loading.value = true
  const phone = toE164(form.phone)
  const res = await auth.register({
    first_name: form.firstName.trim(),
    last_name: form.lastName.trim(),
    phone,
    password: form.password,
    password_confirm: form.confirm,
  })
  loading.value = false

  if (res.status === 201) {
    auth.setPending(phone, res.data.masked_phone, res.data.resend_available_in)
    return router.push({ path: '/verify', query: router.currentRoute.value.query })
  }
  if (res.status === 400 && res.data) {
    if (res.data.code === 'phone_taken') phoneTaken.value = true
    const map = {
      first_name: 'firstName',
      last_name: 'lastName',
      phone: 'phone',
      password: 'password',
      password_confirm: 'confirm',
    }
    for (const [key, field] of Object.entries(map)) {
      if (res.data[key] && !(key === 'phone' && phoneTaken.value)) serverErrors[field] = res.data[key].join(' ')
    }
    return focusFirstInvalid()
  }
  generalError.value =
    res.data?.detail || 'Something went wrong on our side. Check your connection and try again.'
}
</script>

<template>
  <AuthLayout :step="1">
    <template #headline>
      Two minutes<span class="auth-d"> to set up</span>. Then <span class="accent">nobody goes first.</span>
    </template>
    <template #receipt><ReceiptProgress v-bind="SIGNUP_RECEIPT[1]" /></template>
    <template #top>
      <span>Already have an account?</span><RouterLink to="/login" class="strong">Log in</RouterLink>
    </template>

    <form class="form" novalidate @submit.prevent="submit">
      <div class="form__head">
        <div class="af-eyebrow auth-d">CREATE ACCOUNT</div>
        <h2 class="af-h2 form__title">Let’s get you in.</h2>
      </div>

      <div class="form__names">
        <FormField id="su-first" label="First name" :error="errors.firstName">
          <template #default="{ id, describedby, invalid }">
            <input
              :id="id"
              v-model="form.firstName"
              class="af-input"
              :class="{ 'is-error': invalid }"
              type="text"
              autocomplete="given-name"
              :aria-invalid="invalid || undefined"
              :aria-describedby="describedby"
              @input="edited('firstName')"
              @blur="touched.firstName = true"
            />
          </template>
        </FormField>
        <FormField id="su-last" label="Last name" :error="errors.lastName">
          <template #default="{ id, describedby, invalid }">
            <input
              :id="id"
              v-model="form.lastName"
              class="af-input"
              :class="{ 'is-error': invalid }"
              type="text"
              autocomplete="family-name"
              placeholder="As on your bank account"
              :aria-invalid="invalid || undefined"
              :aria-describedby="describedby"
              @input="edited('lastName')"
              @blur="touched.lastName = true"
            />
          </template>
        </FormField>
      </div>

      <FormField
        id="su-phone"
        label="Phone number"
        helper="We’ll text a 6-digit code to confirm it’s yours."
        :error="errors.phone"
      >
        <template #default="{ id, describedby, invalid }">
          <PhoneInput
            :id="id"
            v-model="form.phone"
            :invalid="invalid"
            :describedby="describedby"
            @update:model-value="edited('phone')"
            @blur="touched.phone = true"
          />
        </template>
        <template v-if="phoneTaken" #error>
          An account with this number already exists. <RouterLink to="/login">Log in</RouterLink> instead
        </template>
      </FormField>

      <FormField id="su-password" label="Password" :error="errors.password">
        <template #default="{ id, describedby, invalid }">
          <PasswordInput
            :id="id"
            v-model="form.password"
            autocomplete="new-password"
            spaced
            :rules="rules"
            :invalid="invalid"
            :describedby="describedby"
            @update:model-value="edited('password')"
            @blur="touched.password = true"
          />
        </template>
      </FormField>

      <FormField id="su-confirm" label="Confirm password" :error="errors.confirm">
        <template #default="{ id, describedby, invalid }">
          <PasswordInput
            :id="id"
            v-model="form.confirm"
            autocomplete="new-password"
            spaced
            :invalid="invalid"
            :describedby="describedby"
            @update:model-value="edited('confirm')"
            @blur="touched.confirm = true"
          />
        </template>
      </FormField>

      <div v-if="generalError" class="af-box" role="alert">
        <span class="af-box__label af-box__label--error">ERROR</span> <span>{{ generalError }}</span>
      </div>

      <button type="submit" class="af-btn form__submit" :disabled="loading">
        {{ loading ? 'Creating account…' : 'Continue →' }}
      </button>
      <p class="form__terms">
        By continuing you agree to our <RouterLink to="/terms">Terms</RouterLink> and
        <RouterLink to="/privacy">Privacy Policy</RouterLink>.
      </p>
      <p class="form__switch auth-m">
        Already have an account? <RouterLink to="/login" class="strong">Log in</RouterLink>
      </p>
    </form>
  </AuthLayout>
</template>

<style scoped>
.strong {
  font-weight: 700;
}

.form {
  width: 480px;
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

.form__names {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.form__submit {
  margin-top: 6px;
}

.form__terms {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--muted);
}

.form__switch {
  margin: 8px 0 0;
  font-size: 15px;
  color: var(--ink-2);
  text-align: center;
}

@media (max-width: 899px) {
  .form {
    width: auto;
    padding: 32px 0 40px;
    gap: 20px;
  }

  /* The mobile design has no form title; it stays for screen readers. */
  .form__head {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
    margin: 0;
  }

  .form__names {
    grid-template-columns: minmax(0, 1fr);
    gap: 20px;
  }

  .form__submit {
    margin-top: 8px;
  }
}
</style>
