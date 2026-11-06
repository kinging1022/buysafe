<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { useIsMobile } from '@/composables/useMediaQuery'
import AppHeader from '@/components/account/AppHeader.vue'
import NativeSelect from '@/components/ui/NativeSelect.vue'
import OtpInput from '@/components/auth/OtpInput.vue'
import '@/styles/account.css'

// /profile/payout: where sellers are paid. design/payout-1…5-*.
// On the 10th digit the bank is asked for the account name (looking up), and
// it must match the profile name (match / mismatch); if the bank can't be
// reached, Try again (error). Replacing an existing account needs the code
// sent to the phone (TODO: that step has no design yet; it reuses OtpInput).
const auth = useAuthStore()
const router = useRouter()
const isMobile = useIsMobile()

const banks = ref([])
const bankCode = ref('')
const digits = ref('')
const state = ref('idle') // idle | looking | match | mismatch | error
const accountName = ref('')
const saving = ref(false)
const saveError = ref('')
const needsCode = ref(false)
const code = ref('')
const codeError = ref('')
const myName = ref('')

const bankOptions = computed(() => banks.value.map((b) => ({ value: b.code, label: b.name })))
const bankName = computed(() => banks.value.find((b) => b.code === bankCode.value)?.name || '')
const grouped = computed(() => digits.value.replace(/^(\d{4})(\d{0,4})(\d{0,2}).*$/, (m, a, b, c) => [a, b, c].filter(Boolean).join(' ')))
const canSave = computed(() => state.value === 'match' && !saving.value)

onMounted(async () => {
  auth.ensureLoaded()
  const [list, mine] = await Promise.all([api('/payments/banks/'), api('/me/payout-account/')])
  if (list.ok) banks.value = list.data
  if (mine.ok) {
    myName.value = mine.data.name
    if (mine.data.account) bankCode.value = mine.data.account.bank_code
  }
})

const name = computed(() => myName.value || (auth.user ? `${auth.user.first_name} ${auth.user.last_name}` : ''))

function onDigits(e) {
  digits.value = e.target.value.replace(/\D/g, '').slice(0, 10)
  e.target.value = grouped.value
}

let lookupSeq = 0
async function lookUp() {
  if (digits.value.length !== 10 || !bankCode.value) {
    state.value = 'idle'
    return
  }
  const seq = ++lookupSeq
  state.value = 'looking'
  needsCode.value = false
  saveError.value = ''
  const res = await api('/me/payout-account/lookup/', {
    method: 'POST',
    body: { bank_code: bankCode.value, account_number: digits.value },
  })
  if (seq !== lookupSeq) return
  if (res.ok) {
    accountName.value = res.data.account_name
    state.value = res.data.matches ? 'match' : 'mismatch'
  } else {
    state.value = 'error'
  }
}
watch([digits, bankCode], lookUp)

async function save(withCode) {
  if (!canSave.value) return
  saving.value = true
  saveError.value = ''
  codeError.value = ''
  const body = { bank_code: bankCode.value, account_number: digits.value }
  if (withCode) body.code = withCode
  const res = await api('/me/payout-account/', { method: 'PUT', body })
  saving.value = false
  if (res.ok) {
    router.push('/profile')
  } else if (res.data?.code === 'otp_required') {
    needsCode.value = true
  } else if (res.data?.code === 'invalid_code' || res.data?.code === 'expired') {
    codeError.value = res.data.detail || 'That code isn’t right. Check it and try again.'
  } else if (res.data?.code === 'name_mismatch') {
    accountName.value = res.data.account_name
    state.value = 'mismatch'
  } else {
    saveError.value = res.data?.detail || 'Something went wrong. Please try again.'
  }
}
</script>

<template>
  <div class="acct po" :class="{ 'po--m': isMobile }">
    <AppHeader />

    <main id="main" class="po-page">
      <div v-if="isMobile" class="po-band on-dark">
        <RouterLink to="/profile" class="po-band__back">←  Profile</RouterLink>
        <span class="po-band__k">PAYOUT ACCOUNT</span>
        <h1 class="po-band__h1">Where should we <span class="po-serif">pay you?</span></h1>
      </div>
      <div v-else class="acct-wrap po-top">
        <RouterLink to="/profile" class="acct-back">←  Back to profile</RouterLink>
        <span class="po-k">PAYOUT ACCOUNT</span>
        <h1 class="po-h1">Where should we <span class="po-serif">pay you?</span></h1>
      </div>

      <div class="po-body" :class="{ 'acct-wrap': !isMobile }">
        <form class="po-form" novalidate @submit.prevent="save()">
          <label class="po-label" for="po-bank">Bank</label>
          <NativeSelect
            id="po-bank"
            v-model="bankCode"
            class="po-select"
            :class="{ 'po-select--empty': !bankCode }"
            :options="bankOptions"
            placeholder="Choose your bank"
          />

          <label class="po-label" for="po-acct">Account number</label>
          <input
            id="po-acct"
            class="po-input num"
            :class="{
              'po-input--looking': state === 'looking',
              'po-input--match': state === 'match',
              'po-input--bad': state === 'mismatch' || state === 'error',
            }"
            type="text"
            inputmode="numeric"
            autocomplete="off"
            maxlength="12"
            placeholder="10 digits"
            :value="grouped"
            :aria-invalid="state === 'mismatch' || state === 'error' || undefined"
            aria-describedby="po-status"
            @input="onDigits"
          />

          <div id="po-status" class="po-status">
            <span v-if="state === 'idle'" class="po-hint">
              <template v-if="!isMobile">We’ll look up the account name. It must match your buysafe name, <strong>{{ name }}</strong>.</template>
              <template v-else>The account name must match your buysafe name, <strong>{{ name }}</strong>.</template>
            </span>

            <div v-else-if="state === 'looking'" role="status" class="po-looking">
              <span class="po-dots" aria-hidden="true"><span></span><span></span><span></span></span>
              <template v-if="!isMobile">Looking up the account name with {{ bankName }}…</template>
              <template v-else>Looking up account name…</template>
            </div>

            <div v-else-if="state === 'match'" class="po-match">
              <span class="po-match__k">{{ isMobile ? '✓ MATCHES YOUR BUYSAFE NAME' : '✓ ACCOUNT NAME MATCHES YOUR BUYSAFE NAME' }}</span>
              <span class="po-match__name">{{ accountName }}</span>
              <span v-if="!isMobile" class="po-match__meta num">{{ bankName }} · {{ grouped }}</span>
            </div>

            <div v-else-if="state === 'mismatch'" role="alert" class="po-mismatch">
              <span class="po-mismatch__k">NAME DOESN’T MATCH</span>
              <span class="po-mismatch__name">{{ accountName }}</span>
              <span v-if="!isMobile" class="po-mismatch__p">This account isn’t in your name (<strong>{{ name }}</strong>). To protect buyers and you, payouts only go to an account you own. Use your own account, or if your buysafe name is wrong, <RouterLink to="/profile/edit">update it on your profile</RouterLink>.</span>
              <span v-else class="po-mismatch__p">Payouts only go to an account in your own name. Use your own account, or <RouterLink to="/profile/edit">fix your name</RouterLink>.</span>
            </div>

            <div v-else role="alert" class="po-error">
              <span class="po-error__text">
                <span class="po-error__h">We couldn’t reach {{ bankName }}.</span>
                <span class="po-error__p">{{ isMobile ? 'Check the number and try again.' : 'Check the number and try again in a moment.' }}</span>
              </span>
              <button type="button" class="po-retry" @click="lookUp">Try again</button>
            </div>
          </div>

          <div v-if="needsCode" class="po-otp">
            <span class="po-hint">Enter the code we sent to your phone.</span>
            <OtpInput v-model="code" :invalid="!!codeError" :disabled="saving" describedby="po-otp-error" @complete="save" />
            <p id="po-otp-error" class="po-err" aria-live="polite">{{ codeError }}</p>
          </div>

          <p v-if="saveError" class="po-err" role="alert">{{ saveError }}</p>
          <button type="submit" class="po-save" :class="{ 'po-save--on': canSave }" :aria-disabled="!canSave">Save payout account</button>
          <span v-if="!isMobile" class="po-later">Changing it later needs a code sent to your phone.</span>
        </form>

        <section v-if="!isMobile" class="po-why" aria-labelledby="po-why-h">
          <span id="po-why-h" class="po-why__h">WHY WE NEED THIS</span>
          <div class="po-why__row"><span class="po-why__n">1</span><span>When a buyer confirms, the money goes straight to this account. There’s no wallet to withdraw from.</span></div>
          <div class="po-why__row"><span class="po-why__n">2</span><span>Your listings can’t take payment until it’s set.</span></div>
          <div class="po-why__row po-why__row--last"><span class="po-why__n">3</span><span>The name must match yours, so nobody can redirect your money.</span></div>
        </section>
      </div>
    </main>
  </div>
</template>

<style scoped>
.po-page {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
}

.po-serif {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 400;
  color: var(--released);
}

.po-top {
  padding-top: 48px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.po-k {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.14em;
  color: var(--muted);
  margin-top: 8px;
}

.po-h1 {
  margin: 0;
  font-size: 72px;
  line-height: 0.98;
  font-weight: 800;
  letter-spacing: -0.045em;
}

.po-body {
  padding-top: 40px;
  padding-bottom: 96px;
  display: grid;
  grid-template-columns: 640px 1fr;
  gap: 80px;
  align-items: start;
}

.po-form {
  background: #ffffff;
  border-radius: 20px;
  padding: 32px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.po-label {
  font-size: 15px;
  font-weight: 600;
}

/* Gap between the fields is 22px; label to control is 8px. */
.po-select,
.po-input {
  margin-bottom: 14px;
}

.po-select :deep(select) {
  height: 56px;
  box-sizing: border-box;
  background: #f7f3ea;
  border: 1.5px solid rgba(18, 20, 16, 0.18);
  border-radius: 12px;
  padding-left: 16px;
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
  color: var(--ink);
  outline: none;
}

.po-select--empty :deep(select) {
  font-weight: 400;
  color: #8c8e85;
}

.po-input {
  height: 60px;
  box-sizing: border-box;
  padding: 0 16px;
  background: #f7f3ea;
  border: 1.5px solid rgba(18, 20, 16, 0.18);
  border-radius: 12px;
  font-family: var(--font-mono);
  font-size: 20px;
  letter-spacing: 0.08em;
  color: var(--ink);
  outline: none;
}

.po-input::placeholder {
  color: #8c8e85;
}

.po-input--looking {
  box-shadow: 0 0 0 4px rgba(245, 184, 46, 0.45);
}

.po-input--match {
  border: 2px solid var(--released);
}

.po-input--bad {
  border: 2px solid #a3361f;
}

.po-select :deep(select):focus-visible,
.po-input:focus-visible {
  box-shadow: 0 0 0 4px rgba(245, 184, 46, 0.45);
}

.po-status {
  margin-bottom: 14px;
}

.po-hint {
  font-size: 14px;
  line-height: 1.5;
  color: var(--muted);
}

.po-hint strong {
  color: var(--ink);
}

.po-looking {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 18px;
  background: #f7f3ea;
  border-radius: 14px;
  font-size: 16px;
  font-weight: 600;
}

.po-dots {
  display: flex;
  gap: 5px;
}

.po-dots span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--ink);
}

.po-dots span:nth-child(2) {
  background: rgba(18, 20, 16, 0.45);
}

.po-dots span:nth-child(3) {
  background: rgba(18, 20, 16, 0.2);
}

@media (prefers-reduced-motion: no-preference) {
  .po-dots span {
    animation: po-pulse 1.2s infinite;
  }

  .po-dots span:nth-child(2) {
    animation-delay: 0.2s;
  }

  .po-dots span:nth-child(3) {
    animation-delay: 0.4s;
  }
}

@keyframes po-pulse {
  50% {
    opacity: 0.3;
  }
}

.po-match {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 18px 20px;
  background: rgba(30, 107, 69, 0.08);
  border: 1.5px solid var(--released);
  border-radius: 14px;
}

.po-match__k,
.po-mismatch__k {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--released);
}

.po-match__name,
.po-mismatch__name {
  font-size: 24px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.po-match__meta {
  font-size: 14px;
  color: var(--ink-2);
}

.po-mismatch {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 18px 20px;
  background: rgba(163, 54, 31, 0.07);
  border: 1.5px solid #a3361f;
  border-radius: 14px;
}

.po-mismatch__k {
  color: #a3361f;
}

.po-mismatch__p {
  font-size: 15px;
  line-height: 1.55;
  color: var(--ink-2);
}

.po-mismatch__p strong {
  color: var(--ink);
}

.po-mismatch__p a {
  font-weight: 700;
}

.po-error {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 16px 18px;
  background: var(--paper-deep);
  border-radius: 14px;
}

.po-error__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.po-error__h {
  font-size: 16px;
  font-weight: 700;
}

.po-error__p {
  font-size: 14px;
  color: var(--ink-2);
}

.po-retry {
  height: 44px;
  padding: 0 18px;
  border: 1.5px solid var(--ink);
  background: transparent;
  border-radius: 10px;
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
  cursor: pointer;
  white-space: nowrap;
}

.po-otp {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 14px;
}

.po-err {
  margin: 0 0 8px;
  font-size: 14px;
  color: #a3361f;
}

.po-save {
  height: 60px;
  border: 0;
  border-radius: 14px;
  background: #8c8e85;
  color: var(--paper);
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  cursor: not-allowed;
}

.po-save--on {
  background: var(--forest);
  cursor: pointer;
}

.po-later {
  font-size: 13px;
  line-height: 1.5;
  color: var(--muted);
  margin-top: 6px;
}

.po-why {
  display: flex;
  flex-direction: column;
}

.po-why__h {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: var(--muted);
  padding-bottom: 10px;
  border-bottom: 2px solid var(--ink);
}

.po-why__row {
  display: grid;
  grid-template-columns: 26px 1fr;
  gap: 10px;
  padding: 14px 0;
  border-bottom: 1px solid rgba(18, 20, 16, 0.15);
  font-size: 15px;
  line-height: 1.5;
}

.po-why__row--last {
  border-bottom: 0;
}

.po-why__n {
  font-family: var(--font-serif);
  font-size: 22px;
  line-height: 1;
  color: var(--amber-ink);
}

/* ---- Mobile (design/payout-*-mobile) ---- */

.po-band {
  background: var(--forest);
  color: var(--paper);
  padding: 8px 20px 26px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.acct .po-band__back {
  color: var(--paper);
  text-decoration: none;
  font-size: 15px;
  font-weight: 600;
  min-height: 44px;
  display: flex;
  align-items: center;
  margin-left: -8px;
  padding-left: 8px;
  white-space: pre;
}

.po-band__k {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--accent);
}

.po-band__h1 {
  margin: 0;
  font-size: 38px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.po-band .po-serif {
  color: var(--accent);
}

.po--m .po-body {
  flex-grow: 1;
  padding: 20px 20px calc(24px + env(safe-area-inset-bottom, 0px));
  display: flex;
  flex-direction: column;
}

.po--m .po-form {
  flex-grow: 1;
  background: transparent;
  padding: 0;
  border-radius: 0;
}

.po--m .po-label {
  font-size: 14px;
}

.po--m .po-select :deep(select) {
  height: 54px;
  background: #ffffff;
  padding-left: 14px;
  font-size: 17px;
}

.po--m .po-input {
  height: 56px;
  background: #ffffff;
  padding: 0 14px;
  font-size: 19px;
}

.po--m .po-hint {
  font-size: 13px;
}

.po--m .po-looking {
  gap: 10px;
  padding: 14px;
  background: #ffffff;
  border-radius: 12px;
  font-size: 15px;
}

.po--m .po-dots {
  gap: 4px;
}

.po--m .po-dots span {
  width: 7px;
  height: 7px;
}

.po--m .po-match {
  gap: 4px;
  padding: 14px 16px;
  border-radius: 12px;
}

.po--m .po-mismatch {
  gap: 6px;
  padding: 14px 16px;
  border-radius: 12px;
}

.po--m .po-match__k,
.po--m .po-mismatch__k {
  font-size: 10px;
  letter-spacing: 0.1em;
}

.po--m .po-match__name,
.po--m .po-mismatch__name {
  font-size: 19px;
  letter-spacing: 0;
}

.po--m .po-mismatch__p {
  font-size: 13px;
  line-height: 1.5;
}

.po--m .po-error {
  flex-direction: column;
  align-items: stretch;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 12px;
}

.po--m .po-error__h {
  font-size: 15px;
}

.po--m .po-error__p {
  font-size: 13px;
}

.po--m .po-retry {
  align-self: flex-start;
  padding: 0 16px;
  font-size: 14px;
}

.po--m .po-save {
  margin-top: auto;
  height: 58px;
  font-size: 17px;
}

@media (max-width: 1279px) and (min-width: 768px) {
  .po-body {
    grid-template-columns: minmax(0, 1fr);
    gap: 48px;
  }

  .po-h1 {
    font-size: 56px;
  }
}
</style>
