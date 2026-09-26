// Client-side checks shared by the auth and account forms.

// The live password checklist. Must match the backend validators
// (backend/apps/users/validators.py and AUTH_PASSWORD_VALIDATORS).
export function passwordRules(password) {
  return [
    { label: '8+ characters', met: password.length >= 8 },
    { label: 'A number', met: /\d/.test(password) },
    { label: 'A capital letter', met: /[A-Z]/.test(password) },
  ]
}

/** 'Password needs a number, a capital letter.' or '' when every rule is met. */
export function passwordRulesError(rules) {
  const missing = rules.filter((r) => !r.met)
  return missing.length ? `Password needs ${missing.map((r) => r.label.toLowerCase()).join(', ')}.` : ''
}

// Names: letters in any script, with spaces, hyphens and apostrophes between.
// Mirrors backend/apps/users/serializers.py (validate_name).
const NAME_RE = /^[\p{L}]+(?:[ '’-]+[\p{L}]+)*['’]?$/u

export function nameError(value, label) {
  const v = value.trim().replace(/\s+/g, ' ')
  if (v.length < 2 || v.length > 50 || !NAME_RE.test(v)) return `Enter your ${label} (2–50 letters).`
  return ''
}
