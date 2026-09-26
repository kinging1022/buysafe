<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { NG_STATES } from '@/config/states'
import { ROUTES } from '@/config/account'
import { nameError } from '@/utils/validation'
import { useIsMobile } from '@/composables/useMediaQuery'
import AppHeader from '@/components/account/AppHeader.vue'
import UserAvatar from '@/components/account/UserAvatar.vue'
import AvatarColorPicker from '@/components/account/AvatarColorPicker.vue'
import FormField from '@/components/auth/FormField.vue'
import '@/styles/auth.css'
import '@/styles/account.css'

const auth = useAuthStore()
const router = useRouter()
const isMobile = useIsMobile()

const BIO_MAX = 160
const FIELDS = ['first_name', 'last_name', 'state', 'area', 'bio', 'avatar_color']

const snapshot = () => Object.fromEntries(FIELDS.map((f) => [f, auth.user[f] ?? '']))
let initial = snapshot()
const form = reactive(snapshot())

const dirty = computed(() => FIELDS.some((f) => form[f] !== initial[f]))

// The header avatar previews the colour until the form is saved or left.
watch(
  () => form.avatar_color,
  (color) => (auth.avatarPreview = color === initial.avatar_color ? null : color),
)
onBeforeUnmount(() => (auth.avatarPreview = null))

// ---- Validation (names as on sign up; area 2–60 and optional; bio optional) ----

const touched = reactive({})
const submitted = ref(false)
const serverErrors = reactive({})
const generalError = ref('')
const saving = ref(false)

const clientErrors = computed(() => ({
  first_name: nameError(form.first_name, 'first name'),
  last_name: nameError(form.last_name, 'last name'),
  area: form.area.trim() && form.area.trim().length < 2 ? 'Enter your area or town (2–60 characters).' : '',
}))

const errors = computed(() =>
  Object.fromEntries(
    FIELDS.map((f) => [f, serverErrors[f] || ((touched[f] || submitted.value) && clientErrors.value[f]) || '']),
  ),
)

function edited(field) {
  delete serverErrors[field]
  generalError.value = ''
}

const FIELD_IDS = { first_name: 'ep-first', last_name: 'ep-last', state: 'ep-state', area: 'ep-area', bio: 'ep-bio' }

async function focusFirstInvalid() {
  await nextTick()
  const first = Object.keys(FIELD_IDS).find((f) => errors.value[f])
  if (first) document.getElementById(FIELD_IDS[first])?.focus()
}

// ---- Save / cancel / leave ----

let leaving = false

async function save() {
  submitted.value = true
  generalError.value = ''
  if (Object.values(clientErrors.value).some(Boolean)) return focusFirstInvalid()

  saving.value = true
  const res = await auth.updateProfile({
    first_name: form.first_name.trim(),
    last_name: form.last_name.trim(),
    state: form.state,
    area: form.area.trim(),
    bio: form.bio.trim(),
    avatar_color: form.avatar_color,
  })
  saving.value = false

  if (res.ok) {
    initial = snapshot()
    Object.assign(form, initial)
    auth.avatarPreview = null
    leaving = true
    return router.push('/profile')
  }
  if (res.status === 400 && res.data) {
    for (const f of FIELDS) if (res.data[f]) serverErrors[f] = res.data[f].join(' ')
    if (FIELDS.some((f) => serverErrors[f])) return focusFirstInvalid()
  }
  generalError.value = res.data?.detail || 'Something went wrong on our side. Check your connection and try again.'
}

function cancel() {
  leaving = true
  router.push('/profile')
}

const LEAVE_MESSAGE = 'You have unsaved changes. Leave without saving?'

onBeforeRouteLeave(() => {
  if (leaving || !dirty.value) return true
  return window.confirm(LEAVE_MESSAGE)
})

function onBeforeUnload(e) {
  if (!dirty.value) return
  e.preventDefault()
  e.returnValue = LEAVE_MESSAGE
}
onMounted(() => window.addEventListener('beforeunload', onBeforeUnload))
onBeforeUnmount(() => window.removeEventListener('beforeunload', onBeforeUnload))
</script>

<template>
  <div class="acct">
    <AppHeader />

    <main id="main" class="edit">
      <!-- Phone: back link, title and avatar share a green band. -->
      <div v-if="isMobile" class="band on-dark">
        <div class="guilloche band__ring" aria-hidden="true"></div>
        <RouterLink to="/profile" class="acct-back band__back">←  Back to profile</RouterLink>
        <h1 class="acct-h1 band__h1">Edit profile</h1>
        <div class="band__avatar">
          <UserAvatar
            :first-name="form.first_name"
            :last-name="form.last_name"
            :color="form.avatar_color"
            :size="88"
            :font-size="36"
            :ring="4"
          />
          <div class="picker">
            <span id="ep-colour-label" class="picker__label">AVATAR COLOUR</span>
            <AvatarColorPicker v-model="form.avatar_color" :ring="5" labelledby="ep-colour-label" />
          </div>
        </div>
      </div>

      <div v-else class="acct-wrap top">
        <RouterLink to="/profile" class="acct-back">←  Back to profile</RouterLink>
        <h1 class="acct-h1">Edit profile</h1>
      </div>

      <div class="acct-wrap body">
        <aside v-if="!isMobile" class="panel on-dark" aria-label="Avatar">
          <div class="guilloche panel__ring" aria-hidden="true"></div>
          <UserAvatar
            class="panel__avatar"
            :first-name="form.first_name"
            :last-name="form.last_name"
            :color="form.avatar_color"
            :size="176"
            :font-size="72"
            :ring="6"
          />
          <div class="picker picker--panel">
            <span id="ep-colour-label" class="picker__label">AVATAR COLOUR</span>
            <AvatarColorPicker v-model="form.avatar_color" labelledby="ep-colour-label" />
            <p class="picker__help">Your initials come from your name. Photo uploads are coming soon.</p>
          </div>
        </aside>

        <form class="form" novalidate @submit.prevent="save">
          <div class="frow frow--first">
            <div class="frow__intro">
              <span class="frow__title">Your name</span>
              <span class="frow__hint">Use the name on your bank account so payouts go through.</span>
            </div>
            <div class="frow__pair">
              <FormField id="ep-first" label="First name" :error="errors.first_name">
                <template #default="{ id, describedby, invalid }">
                  <input
                    :id="id"
                    v-model="form.first_name"
                    class="af-input"
                    :class="{ 'is-error': invalid }"
                    type="text"
                    autocomplete="given-name"
                    :aria-invalid="invalid || undefined"
                    :aria-describedby="describedby"
                    @input="edited('first_name')"
                    @blur="touched.first_name = true"
                  />
                </template>
              </FormField>
              <FormField id="ep-last" label="Last name" :error="errors.last_name">
                <template #default="{ id, describedby, invalid }">
                  <input
                    :id="id"
                    v-model="form.last_name"
                    class="af-input"
                    :class="{ 'is-error': invalid }"
                    type="text"
                    autocomplete="family-name"
                    :aria-invalid="invalid || undefined"
                    :aria-describedby="describedby"
                    @input="edited('last_name')"
                    @blur="touched.last_name = true"
                  />
                </template>
              </FormField>
            </div>
          </div>

          <div class="frow">
            <div class="frow__intro">
              <span class="frow__title">Where you are</span>
              <span class="frow__hint">Shown on your listings so buyers know how far to travel.</span>
            </div>
            <div class="frow__pair">
              <FormField id="ep-state" label="State" :error="errors.state">
                <template #default="{ id, describedby, invalid }">
                  <div class="select">
                    <select
                      :id="id"
                      v-model="form.state"
                      class="af-input select__el"
                      :class="{ 'is-error': invalid, 'is-empty': !form.state }"
                      autocomplete="address-level1"
                      :aria-invalid="invalid || undefined"
                      :aria-describedby="describedby"
                      @change="edited('state')"
                    >
                      <option value="" disabled>Choose your state</option>
                      <option v-for="[key, label] in NG_STATES" :key="key" :value="key">{{ label }}</option>
                    </select>
                    <svg class="select__chevron" width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="#121410" stroke-width="1.8" aria-hidden="true"><path d="M3 5l4 4 4-4"></path></svg>
                  </div>
                </template>
              </FormField>
              <FormField id="ep-area" label="Area or town" :error="errors.area">
                <template #default="{ id, describedby, invalid }">
                  <input
                    :id="id"
                    v-model="form.area"
                    class="af-input"
                    :class="{ 'is-error': invalid }"
                    type="text"
                    maxlength="60"
                    autocomplete="address-level2"
                    :aria-invalid="invalid || undefined"
                    :aria-describedby="describedby"
                    @input="edited('area')"
                    @blur="touched.area = true"
                  />
                </template>
              </FormField>
            </div>
          </div>

          <div class="frow">
            <div class="frow__intro">
              <span class="frow__title">About you</span>
              <span class="frow__hint">Optional. One line buyers see on your profile.</span>
            </div>
            <FormField id="ep-bio" label="Short bio" :error="errors.bio">
              <template #default="{ id, describedby, invalid }">
                <textarea
                  :id="id"
                  v-model="form.bio"
                  class="af-input bio"
                  :class="{ 'is-error': invalid }"
                  :rows="isMobile ? 4 : 3"
                  :maxlength="BIO_MAX"
                  :aria-invalid="invalid || undefined"
                  :aria-describedby="[describedby, 'ep-bio-count'].filter(Boolean).join(' ')"
                  @input="edited('bio')"
                ></textarea>
                <span id="ep-bio-count" class="bio__count">{{ form.bio.length }} / {{ BIO_MAX }}</span>
              </template>
            </FormField>
          </div>

          <div class="frow frow--last">
            <div class="frow__intro">
              <span id="ep-phone-title" class="frow__title">Phone number</span>
              <span class="frow__hint">Used to log in. Changing it needs a new code.</span>
            </div>
            <div class="phone" role="group" aria-labelledby="ep-phone-title">
              <div class="phone__num">
                <span class="phone__masked">{{ auth.user.masked_phone }}</span>
                <span v-if="auth.user.phone_verified" class="phone__ok">✓ VERIFIED</span>
              </div>
              <RouterLink :to="ROUTES.changePhone" class="phone__change">Change number</RouterLink>
            </div>
          </div>

          <div v-if="generalError" class="af-box form__error" role="alert">
            <span class="af-box__label af-box__label--error">ERROR</span> <span>{{ generalError }}</span>
          </div>

          <div class="actions">
            <button type="submit" class="actions__save" :disabled="saving">{{ saving ? 'Saving…' : 'Save changes' }}</button>
            <button type="button" class="actions__cancel" @click="cancel">Cancel</button>
            <span class="actions__dirty" role="status">{{ dirty ? '● UNSAVED CHANGES' : '' }}</span>
          </div>
        </form>
      </div>
    </main>
  </div>
</template>

<style scoped>
.edit {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
}

/* ---------- Desktop title ---------- */

.top {
  padding-top: 56px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* The reference's link sits 18px above the title; the 44px hit area keeps that. */
.top .acct-back {
  min-height: 0;
  position: relative;
}

.top .acct-back::after {
  content: '';
  position: absolute;
  inset: -12px -4px;
}

.body {
  flex-grow: 1;
  padding-top: 48px;
  padding-bottom: 96px;
  display: grid;
  grid-template-columns: 400px minmax(0, 1fr);
  gap: 80px;
  align-items: start;
}

/* ---------- Avatar panel ---------- */

.panel {
  position: relative;
  overflow: hidden;
  background: var(--forest);
  color: var(--paper);
  border-radius: 20px;
  padding: 40px 36px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 28px;
}

.panel__ring {
  position: absolute;
  width: 520px;
  height: 520px;
  border-radius: 50%;
  left: 50%;
  margin-left: -260px;
  top: -150px;
}

.panel__avatar {
  position: relative;
}

.picker {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.picker--panel {
  align-items: center;
  width: 100%;
}

.picker__label {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.14em;
  color: var(--on-forest-muted);
}

.picker__help {
  margin: 6px 0 0;
  font-size: 14px;
  line-height: 1.5;
  color: var(--on-forest-2);
  text-align: center;
}

/* ---------- Form rows ---------- */

.form {
  display: flex;
  flex-direction: column;
  max-width: 720px;
}

.frow {
  display: grid;
  grid-template-columns: 200px minmax(0, 1fr);
  gap: 40px;
  padding: 32px 0;
  border-top: 1px solid rgba(18, 20, 16, 0.18);
}

.frow--first {
  border-top: 2px solid var(--ink);
}

.frow--last {
  border-bottom: 1px solid rgba(18, 20, 16, 0.18);
}

.frow__intro {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.frow__title {
  font-size: 20px;
  font-weight: 700;
}

.frow__hint {
  font-size: 14px;
  line-height: 1.5;
  color: var(--muted);
}

.frow__pair {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  align-items: start;
}

.frow .af-input {
  width: 100%;
}

/* State: native select drawn like the reference (chevron on the right). */
.select {
  position: relative;
}

.select__el {
  appearance: none;
  -webkit-appearance: none;
  padding-right: 40px;
  cursor: pointer;
}

.select__el.is-empty {
  color: #8c8e85;
}

.select__el option {
  color: var(--ink);
}

.select__chevron {
  position: absolute;
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
}

.bio {
  height: auto;
  padding: 14px 16px;
  line-height: 1.5;
  resize: vertical;
}

.bio__count {
  align-self: flex-end;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 500;
  color: var(--muted);
}

.phone {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: 54px;
  padding: 0 6px 0 16px;
  background: #efe9dc;
  border-radius: 12px;
}

.phone__num {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.phone__masked {
  font-family: var(--font-mono);
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
}

.phone__ok {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--released);
  white-space: nowrap;
}

.acct .phone__change,
.acct .phone__change:hover {
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 16px;
  text-decoration: none;
  font-size: 14px;
  font-weight: 700;
  color: var(--ink);
  background: #ffffff;
  border-radius: 9px;
  white-space: nowrap;
  position: relative;
}

.phone__change::after {
  content: '';
  position: absolute;
  inset: -1px 0;
}

.form__error {
  margin-top: 24px;
}

.actions {
  display: flex;
  align-items: center;
  gap: 20px;
  padding-top: 36px;
}

.actions__save {
  height: 58px;
  padding: 0 36px;
  border: 0;
  background: var(--forest);
  color: var(--paper);
  border-radius: 12px;
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  cursor: pointer;
}

.actions__save:disabled {
  cursor: progress;
}

.actions__cancel {
  min-height: 44px;
  padding: 0;
  border: 0;
  background: none;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 600;
  color: var(--ink-2);
  text-decoration: underline;
  cursor: pointer;
}

.actions__dirty {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--amber-ink);
}

/* ---------- 768–1279: panel above the form, full width ---------- */

@media (max-width: 1279px) {
  .body {
    grid-template-columns: minmax(0, 1fr);
    gap: 48px;
  }

  .form {
    max-width: none;
  }
}

/* ---------- Phone ---------- */

@media (max-width: 767px) {
  .band {
    position: relative;
    overflow: hidden;
    background: var(--forest);
    color: var(--paper);
    padding: 16px 20px 32px;
    display: flex;
    flex-direction: column;
    gap: 24px;
  }

  .band__ring {
    position: absolute;
    width: 420px;
    height: 420px;
    border-radius: 50%;
    right: -210px;
    top: -170px;
    background: repeating-radial-gradient(circle at 50% 50%, rgba(243, 237, 224, 0) 0 8px, rgba(243, 237, 224, 0.1) 8px 9px);
  }

  .acct .band__back,
  .acct .band__back:hover {
    position: relative;
    color: var(--paper);
  }

  .band__h1 {
    position: relative;
  }

  .band__avatar {
    position: relative;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 18px;
  }

  .picker {
    gap: 10px;
  }

  .picker__label {
    font-size: 11px;
    letter-spacing: 0.12em;
  }

  .body {
    padding-top: 8px;
    padding-bottom: 40px;
  }

  .frow {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 28px 0;
    border-top: 0;
    border-bottom: 1px solid rgba(18, 20, 16, 0.18);
  }

  .frow--first {
    border-top: 0;
  }

  .frow--last {
    border-bottom: 0;
  }

  .frow__intro {
    gap: 4px;
  }

  .frow__title {
    font-size: 19px;
  }

  .frow__hint {
    font-size: 13px;
  }

  .frow__pair {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 14px;
  }

  .phone {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
    height: auto;
    padding: 16px;
  }

  .phone__num {
    justify-content: space-between;
  }

  .phone__ok {
    font-size: 10px;
  }

  .acct .phone__change {
    height: 44px;
  }

  .form__error {
    margin: 0 0 20px;
  }

  .actions {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
    padding-top: 0;
  }

  .actions__save {
    order: 2;
    width: 100%;
    padding: 0;
  }

  .actions__cancel {
    order: 3;
    height: 48px;
  }

  .actions__dirty {
    order: 1;
    margin: 0;
    text-align: center;
  }

  .actions__dirty:empty {
    display: none;
  }
}
</style>
