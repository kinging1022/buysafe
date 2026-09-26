<script setup>
import { computed, nextTick, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { passwordRules, passwordRulesError } from '@/utils/validation'
import AppHeader from '@/components/account/AppHeader.vue'
import FormField from '@/components/auth/FormField.vue'
import PasswordInput from '@/components/auth/PasswordInput.vue'
import '@/styles/auth.css'
import '@/styles/account.css'

const auth = useAuthStore()
const router = useRouter()

const form = reactive({ current: '', password: '', confirm: '' })
const submitted = ref(false)
const serverErrors = reactive({ current: '', password: '', confirm: '' })
const generalError = ref('')
const loading = ref(false)

// "Not your old one" is checked by the server; it shows as met until the
// server rejects this exact password.
const rejectedAsOld = ref(null)
const rules = computed(() => [
  ...passwordRules(form.password),
  { label: 'Not your old one', met: form.password === '' || form.password !== rejectedAsOld.value },
])

const clientErrors = computed(() => ({
  current: form.current ? '' : 'Enter your current password.',
  password: passwordRulesError(rules.value.slice(0, 3)),
  confirm: form.confirm === form.password ? '' : 'Passwords don’t match yet.',
}))

const errors = computed(() => ({
  current: serverErrors.current || (submitted.value ? clientErrors.value.current : ''),
  password: serverErrors.password || (submitted.value ? clientErrors.value.password : ''),
  confirm: serverErrors.confirm || ((submitted.value || form.confirm) ? clientErrors.value.confirm : ''),
}))

const FIELD_IDS = { current: 'cp-current', password: 'cp-password', confirm: 'cp-confirm' }

async function focusFirstInvalid() {
  await nextTick()
  const first = Object.keys(FIELD_IDS).find((f) => errors.value[f])
  if (first) document.getElementById(FIELD_IDS[first])?.focus()
}

function edited(field) {
  serverErrors[field] = ''
  generalError.value = ''
}

async function submit() {
  submitted.value = true
  generalError.value = ''
  if (Object.values(clientErrors.value).some(Boolean)) return focusFirstInvalid()

  loading.value = true
  const res = await auth.changePassword({
    current_password: form.current,
    new_password: form.password,
    new_password_confirm: form.confirm,
  })
  loading.value = false

  if (res.ok) {
    auth.flash = 'Password updated. Other devices have been signed out.'
    return router.push('/profile')
  }
  if (res.status === 400 && res.data) {
    if (res.data.code === 'password_unchanged') rejectedAsOld.value = form.password
    serverErrors.current = res.data.current_password?.join(' ') || ''
    serverErrors.password = res.data.new_password?.join(' ') || ''
    serverErrors.confirm = res.data.new_password_confirm?.join(' ') || ''
    if (Object.values(serverErrors).some(Boolean)) return focusFirstInvalid()
  }
  generalError.value =
    res.data?.detail || 'Something went wrong on our side. Check your connection and try again.'
}
</script>

<template>
  <div class="acct">
    <AppHeader />

    <main id="main" class="acct-wrap page">
      <div class="intro">
        <RouterLink to="/profile" class="acct-back intro__back">←  Back to profile</RouterLink>
        <div class="intro__eyebrow">SECURITY</div>
        <h1 class="acct-h1 intro__h1">
          Change your password. <span class="intro__accent">Keep your wallet yours.</span>
        </h1>
        <p class="intro__lede">Your password guards money held in escrow. Use one you don’t use anywhere else.</p>
      </div>

      <ol class="notes">
        <li><span class="notes__n">01</span><span>We never ask for your password by SMS, call or WhatsApp.</span></li>
        <li><span class="notes__n">02</span><span>Changing it logs you out on every other device.</span></li>
      </ol>

      <form class="card" novalidate aria-labelledby="cp-title" @submit.prevent="submit">
        <h2 id="cp-title" class="visually-hidden">Change password</h2>

        <FormField id="cp-current" label="Current password" :error="errors.current">
          <template #label-aside>
            <RouterLink to="/reset-password" class="forgot">Forgot it?</RouterLink>
          </template>
          <template #default="{ id, describedby, invalid }">
            <PasswordInput
              :id="id"
              v-model="form.current"
              autocomplete="current-password"
              spaced
              :invalid="invalid"
              :describedby="describedby"
              @update:model-value="edited('current')"
            />
          </template>
        </FormField>

        <div class="card__rule" role="presentation"></div>

        <FormField id="cp-password" label="New password" :error="errors.password">
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
            />
          </template>
        </FormField>

        <FormField id="cp-confirm" label="Confirm new password" :error="errors.confirm">
          <template #default="{ id, describedby, invalid }">
            <PasswordInput
              :id="id"
              v-model="form.confirm"
              autocomplete="new-password"
              placeholder="Type it again"
              :spaced="!!form.confirm"
              :invalid="invalid"
              :describedby="describedby"
              @update:model-value="edited('confirm')"
            />
          </template>
        </FormField>

        <div v-if="generalError" class="af-box" role="alert">
          <span class="af-box__label af-box__label--error">ERROR</span> <span>{{ generalError }}</span>
        </div>

        <button type="submit" class="af-btn card__submit" :disabled="loading">
          {{ loading ? 'Updating…' : 'Update password' }}
        </button>
      </form>
    </main>
  </div>
</template>

<style scoped>
/* Left column: intro, then the numbered notes; the card spans both rows. */
.page {
  flex-grow: 1;
  padding-top: 56px;
  padding-bottom: 96px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 520px;
  grid-template-rows: auto 1fr;
  grid-template-areas:
    'intro card'
    'notes card';
  column-gap: 96px;
  align-items: start;
}

.intro {
  grid-area: intro;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.intro__back {
  min-height: 0;
  position: relative;
}

.intro__back::after {
  content: '';
  position: absolute;
  inset: -12px -4px;
}

.intro__eyebrow {
  margin-top: 12px;
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.14em;
  color: var(--muted);
}

.intro__h1 {
  font-size: 80px;
  line-height: 0.98;
}

.intro__accent {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 400;
  letter-spacing: -0.01em;
  color: var(--released);
}

.intro__lede {
  margin: 0;
  font-size: 19px;
  line-height: 1.55;
  color: var(--ink-2);
  max-width: 520px;
}

.notes {
  grid-area: notes;
  list-style: none;
  margin: 34px 0 0;
  padding: 0;
  max-width: 520px;
  display: flex;
  flex-direction: column;
}

.notes li {
  display: flex;
  gap: 16px;
  padding: 16px 0;
  border-top: 1.5px solid rgba(18, 20, 16, 0.25);
  font-size: 16px;
}

.notes li:last-child {
  border-bottom: 1.5px solid rgba(18, 20, 16, 0.25);
}

.notes__n {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  color: var(--amber-ink);
  padding-top: 2px;
}

.card {
  grid-area: card;
  margin-top: 48px;
  background: #ffffff;
  border-radius: 20px;
  padding: 40px;
  display: flex;
  flex-direction: column;
  gap: 22px;
  box-shadow:
    0 1px 0 rgba(18, 20, 16, 0.06),
    0 20px 50px rgba(18, 20, 16, 0.06);
}

.forgot {
  font-weight: 600;
  position: relative;
}

.forgot::after {
  content: '';
  position: absolute;
  inset: -14px -6px;
}

.card__rule {
  border-top: 1px dashed rgba(18, 20, 16, 0.2);
}

.card__submit {
  margin-top: 6px;
}

/* Smaller desktops: a narrower card and title. */
@media (max-width: 1279px) {
  .page {
    grid-template-columns: minmax(0, 1fr) 460px;
    column-gap: 56px;
  }

  .intro__h1 {
    font-size: 60px;
  }
}

/* Below 1024: one column. Intro, then the form, then the notes. */
@media (max-width: 1023px) {
  .page {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: none;
    grid-template-areas:
      'intro'
      'card'
      'notes';
  }

  .card {
    max-width: 560px;
    margin-top: 32px;
  }

  .notes {
    margin-top: 32px;
  }
}

@media (max-width: 767px) {
  .page {
    padding-top: 24px;
    padding-bottom: 56px;
  }

  .intro {
    gap: 16px;
  }

  .intro__back {
    min-height: 44px;
  }

  .intro__back::after {
    content: none;
  }

  .intro__eyebrow {
    margin-top: 0;
  }

  .intro__h1 {
    font-size: 44px;
    line-height: 1;
  }

  .intro__lede {
    font-size: 17px;
  }

  .card {
    max-width: none;
    padding: 20px;
    margin-top: 28px;
  }

  .notes {
    margin-top: 28px;
  }

  .notes li {
    font-size: 15px;
  }
}
</style>
