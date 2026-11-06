import { describe, expect, it } from 'vitest'
import { WAITLIST_STATES, attribution, normalizeWaitlistPhone } from '@/components/prelaunch/waitlist'

describe('normalizeWaitlistPhone', () => {
  it.each(['08031234567', '8031234567', '+2348031234567', '2348031234567', '0803 123 4567', '0803-123-4567', '+234 0803 123 4567'])(
    'normalises %s',
    (raw) => expect(normalizeWaitlistPhone(raw)).toBe('+2348031234567'),
  )

  it.each(['01 234 5678', '0803123456', '6031234567', '08231234567', ''])('rejects %s', (raw) => {
    expect(normalizeWaitlistPhone(raw)).toBeNull()
  })
})

it('lists the 36 states and FCT Abuja in the reference order', () => {
  expect(WAITLIST_STATES).toHaveLength(37)
  const labels = WAITLIST_STATES.map(([, label]) => label)
  expect(labels.slice(13, 16)).toEqual(['Enugu', 'FCT Abuja', 'Gombe'])
  expect(labels.at(-1)).toBe('Zamfara')
})

it('reads utm params and falls back to the host for source', () => {
  const loc = { search: '?utm_source=ig&utm_medium=story&utm_campaign=launch', hostname: 'buysafe.ng' }
  expect(attribution(loc, '')).toEqual({ source: 'buysafe.ng', utm_source: 'ig', utm_medium: 'story', utm_campaign: 'launch' })
  expect(attribution(loc, 'https://t.co/').source).toBe('https://t.co/')
})
