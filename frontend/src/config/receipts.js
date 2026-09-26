// ReceiptProgress props for each step of the auth flows.
const stamp = (text, top) => ({ text, color: 'var(--released)', top })

const rows = (labels, nowIndex) =>
  labels.map((label, i) => ({ label, state: i < nowIndex ? 'done' : i === nowIndex ? 'now' : 'next' }))

const SIGNUP_STEPS = ['Your details', 'Verify your phone']

export const SIGNUP_RECEIPT = {
  1: { title: 'NEW ACCOUNT', counter: 'STEP 1 OF 2', rows: rows(SIGNUP_STEPS, 0), label: 'New account, step 1 of 2' },
  2: {
    title: 'NEW ACCOUNT',
    counter: 'STEP 2 OF 2',
    rows: rows(SIGNUP_STEPS, 1),
    stamp: stamp('ALMOST IN', 40),
    label: 'New account, step 2 of 2',
  },
}

const RESET_STEPS = ['Your number', 'SMS code', 'New password']

// Steps 1–3, then 4 = done (every row done, counter stays STEP 3 OF 3, RESET stamp).
export function resetReceipt(step) {
  const done = step > 3
  return {
    title: 'PASSWORD RESET',
    counter: `STEP ${Math.min(step, 3)} OF 3`,
    rows: rows(RESET_STEPS, step - 1),
    nextTag: '—',
    nextDotSize: 14,
    stamp: done ? stamp('RESET', 44) : null,
    label: done ? 'Password reset, done' : `Password reset, step ${step} of 3`,
  }
}
