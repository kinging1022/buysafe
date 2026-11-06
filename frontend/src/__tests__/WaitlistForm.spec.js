import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import WaitlistForm from '@/components/prelaunch/WaitlistForm.vue'

const respond = (status) => ({ ok: status >= 200 && status < 300, status })

function deferred() {
  let resolve
  const promise = new Promise((r) => (resolve = r))
  return { promise, resolve }
}

async function fill(wrapper, { phone = '0803 123 4567', state = 'lagos' } = {}) {
  await wrapper.find('input[name="phone"]').setValue(phone)
  if (state) await wrapper.find('select').setValue(state)
}

async function submit(wrapper) {
  await wrapper.find('form').trigger('submit')
  await flushPromises()
}

describe('WaitlistForm', () => {
  let fetchMock

  beforeEach(() => {
    localStorage.clear()
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('shows the phone message and focuses the field for a bad number', async () => {
    const wrapper = mount(WaitlistForm, { attachTo: document.body })
    await fill(wrapper, { phone: '01 234 5678' })
    await submit(wrapper)
    expect(wrapper.find('.msg').text()).toBe('Enter a Nigerian mobile number, like 0803 123 4567.')
    expect(wrapper.find('.msg').classes()).toContain('err')
    expect(document.activeElement).toBe(wrapper.find('input[name="phone"]').element)
    expect(fetchMock).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('requires a state', async () => {
    const wrapper = mount(WaitlistForm, { attachTo: document.body })
    await fill(wrapper, { state: '' })
    await submit(wrapper)
    expect(wrapper.find('.msg').text()).toBe('Choose your state.')
    expect(document.activeElement).toBe(wrapper.find('select').element)
    expect(fetchMock).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('submits, shows "Joining…", then the success panel', async () => {
    const pending = deferred()
    fetchMock.mockReturnValue(pending.promise)
    const wrapper = mount(WaitlistForm)
    await fill(wrapper, { phone: '+234 803-123-4567', state: 'fct' })
    await wrapper.find('input[value="sell"]').setValue()
    await wrapper.find('form').trigger('submit')

    const btn = wrapper.find('button[type="submit"]')
    expect(btn.text()).toBe('Joining…')
    expect(btn.attributes('disabled')).toBeDefined()

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/waitlist/')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toMatchObject({ phone: '+2348031234567', state: 'fct', role: 'sell', company: '' })

    pending.resolve(respond(200))
    await flushPromises()
    expect(wrapper.classes()).toContain('is-done')
    expect(wrapper.find('.done-state').text()).toBe('FCT Abuja')
    expect(btn.text()).toBe('Join the waitlist')
    expect(btn.attributes('disabled')).toBeUndefined()
    expect(localStorage.getItem('bs_state')).toBe('fct')
  })

  it('shows the throttle message on 429', async () => {
    fetchMock.mockResolvedValue(respond(429))
    const wrapper = mount(WaitlistForm)
    await fill(wrapper)
    await submit(wrapper)
    expect(wrapper.find('.msg').text()).toBe('Too many tries. Please wait a minute and try again.')
    expect(wrapper.classes()).not.toContain('is-done')
  })

  it.each([
    ['a server error', () => Promise.resolve(respond(500))],
    ['a 400', () => Promise.resolve(respond(400))],
    ['a network failure', () => Promise.reject(new TypeError('offline'))],
  ])('shows the generic message on %s', async (_, impl) => {
    fetchMock.mockImplementation(impl)
    const wrapper = mount(WaitlistForm)
    await fill(wrapper)
    await submit(wrapper)
    expect(wrapper.find('.msg').text()).toBe('Something went wrong. Please try again.')
  })

  it('preselects the remembered state and defaults the role to buy', () => {
    localStorage.setItem('bs_state', 'rivers')
    const wrapper = mount(WaitlistForm)
    expect(wrapper.find('select').element.value).toBe('rivers')
    expect(wrapper.find('input[value="buy"]').element.checked).toBe(true)
  })

  it('still works when localStorage throws', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
    fetchMock.mockResolvedValue(respond(200))
    const wrapper = mount(WaitlistForm)
    await fill(wrapper)
    await submit(wrapper)
    expect(wrapper.classes()).toContain('is-done')
  })
})
