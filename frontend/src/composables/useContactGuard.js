import { computed, toValue } from 'vue'

// The live check for contact details while typing a question or an answer.
// A first pass only: the backend (listings/contact_guard.py) is the real gate
// and also catches spelled-out and letter-split numbers.
const PATTERNS = [
  // Nigerian numbers with spaces, dashes, dots or brackets: 0803 555 1234, +234 (803) 555-1234.
  ['phone', /(?:\+?234|\b0)?[\s\-.()]*[789][\s\-.()]*[01](?:[\s\-.()]*\d){8}\b/],
  ['email', /[\w.+-]+@[\w-]+(?:\.[\w-]+)+/i],
  ['link', /https?:\/\/|\bwww\s*\.|\b[\w-]+\.(?:com|ng|net|org|co|io|me|app|info|biz|ly|link|xyz|online|shop|store)\b/i],
  ['handle', /(?:^|[^\w.])@[a-z0-9_.]{2,}/i],
]

/** The warning label for each kind (design/qa-buyer-3-warning-*). */
export const CONTACT_LABELS = {
  phone: 'REMOVE PHONE NUMBER',
  email: 'REMOVE EMAIL ADDRESS',
  link: 'REMOVE LINK',
  handle: 'REMOVE @HANDLE',
}

export function findContact(text) {
  const value = text || ''
  for (const [kind, re] of PATTERNS) if (re.test(value)) return kind
  return null
}

/** { kind, hasContact } for a ref/getter of text. */
export function useContactGuard(text) {
  const kind = computed(() => findContact(toValue(text)))
  const hasContact = computed(() => kind.value !== null)
  return { kind, hasContact }
}
