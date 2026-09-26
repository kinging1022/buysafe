import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/http'

// Only the pending sign-up phone and resend time survive a refresh
// (sessionStorage). Passwords, OTPs and the password-reset token are never
// stored anywhere on the client: the reset flow lives in memory only.
const PENDING_KEY = 'buysafe.pendingVerification'

function readPending() {
  try {
    return JSON.parse(sessionStorage.getItem(PENDING_KEY)) || {}
  } catch {
    return {}
  }
}

function writePending(value) {
  try {
    if (value) sessionStorage.setItem(PENDING_KEY, JSON.stringify(value))
    else sessionStorage.removeItem(PENDING_KEY)
  } catch {
    // storage unavailable (private mode etc.): state still lives in memory
  }
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const loaded = ref(false)

  const saved = typeof window === 'undefined' ? {} : readPending()
  const pendingPhone = ref(saved.phone || null) // E.164
  const maskedPhone = ref(saved.masked || null)
  const resendAvailableAt = ref(saved.resendAvailableAt || 0) // epoch ms

  // Sign-up form values kept for "Change it" (never the passwords).
  const signupDraft = ref({ firstName: '', lastName: '', phoneDigits: '' })

  // Edit profile previews an avatar colour in the header before it's saved.
  const avatarPreview = ref(null)
  // One-off confirmation shown at the top of the next page (e.g. /profile).
  const flash = ref('')

  // Password reset, in memory only: a refresh restarts the flow.
  const reset = ref({ phone: null, masked: null, resendAvailableAt: 0, token: null })

  function setPending(phone, masked, resendIn) {
    pendingPhone.value = phone
    maskedPhone.value = masked
    resendAvailableAt.value = Date.now() + (resendIn || 0) * 1000
    writePending({ phone, masked, resendAvailableAt: resendAvailableAt.value })
  }

  function setResendIn(seconds) {
    setPending(pendingPhone.value, maskedPhone.value, seconds)
  }

  function clearPending() {
    pendingPhone.value = null
    maskedPhone.value = null
    resendAvailableAt.value = 0
    writePending(null)
  }

  async function ensureLoaded() {
    if (loaded.value) return
    const res = await api('/me/')
    user.value = res.ok ? res.data : null
    loaded.value = true
  }

  function signedIn(data) {
    user.value = data.user
    loaded.value = true
    clearPending()
    signupDraft.value = { firstName: '', lastName: '', phoneDigits: '' }
  }

  const register = (payload) => api('/auth/register/', { method: 'POST', body: payload })
  const verify = (code) =>
    api('/auth/verify-otp/', { method: 'POST', body: { phone: pendingPhone.value, code } })
  const resend = () => api('/auth/resend-otp/', { method: 'POST', body: { phone: pendingPhone.value } })
  const login = (phone, password) => api('/auth/login/', { method: 'POST', body: { phone, password } })

  async function logout() {
    await api('/auth/logout/', { method: 'POST' })
    user.value = null
  }

  // ---- Profile ----

  async function updateProfile(payload) {
    const res = await api('/me/', { method: 'PATCH', body: payload })
    if (res.ok) user.value = res.data
    return res
  }

  async function changePassword(payload) {
    const res = await api('/me/password/', { method: 'POST', body: payload })
    if (res.ok) user.value = res.data
    return res
  }

  // ---- Password reset ----

  async function requestReset(phone) {
    const res = await api('/auth/password-reset/request/', { method: 'POST', body: { phone } })
    if (res.ok) {
      reset.value = {
        phone,
        masked: res.data.masked_phone,
        resendAvailableAt: Date.now() + res.data.resend_available_in * 1000,
        token: null,
      }
    }
    return res
  }

  async function verifyReset(code) {
    const res = await api('/auth/password-reset/verify/', {
      method: 'POST',
      body: { phone: reset.value.phone, code },
    })
    if (res.ok) reset.value.token = res.data.reset_token
    return res
  }

  async function confirmReset(newPassword, confirm) {
    const res = await api('/auth/password-reset/confirm/', {
      method: 'POST',
      body: { reset_token: reset.value.token, new_password: newPassword, new_password_confirm: confirm },
    })
    if (res.ok) {
      // Every session was signed out, this one included.
      user.value = null
      reset.value.token = null
    }
    return res
  }

  function clearReset() {
    reset.value = { phone: null, masked: null, resendAvailableAt: 0, token: null }
  }

  return {
    user,
    loaded,
    pendingPhone,
    maskedPhone,
    resendAvailableAt,
    signupDraft,
    avatarPreview,
    flash,
    reset,
    setPending,
    setResendIn,
    clearPending,
    ensureLoaded,
    signedIn,
    register,
    verify,
    resend,
    login,
    logout,
    updateProfile,
    changePassword,
    requestReset,
    verifyReset,
    confirmReset,
    clearReset,
  }
})
