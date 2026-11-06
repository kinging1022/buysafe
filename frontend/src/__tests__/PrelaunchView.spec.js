import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import PrelaunchView from '@/views/PrelaunchView.vue'

describe('PrelaunchView', () => {
  it('renders the waitlist form in the hero and the final section', () => {
    const wrapper = mount(PrelaunchView)
    expect(wrapper.find('#join form').exists()).toBe(true)
    expect(wrapper.find('#join-2 form').exists()).toBe(true)
  })

  it('gives the two forms unique, labelled ids', () => {
    const wrapper = mount(PrelaunchView)
    const ids = wrapper.findAll('input, select').map((el) => el.attributes('id')).filter(Boolean)
    expect(ids).toHaveLength(6) // phone, state, honeypot × 2
    expect(new Set(ids).size).toBe(6)
    for (const host of ['#join', '#join-2']) {
      const phoneId = wrapper.find(`${host} input[name="phone"]`).attributes('id')
      const stateId = wrapper.find(`${host} select`).attributes('id')
      expect(wrapper.find(`label[for="${phoneId}"]`).text()).toBe('Phone number')
      expect(wrapper.find(`label[for="${stateId}"]`).text()).toBe('Your state')
    }
  })

  it('"Join as a vendor" preselects the vendor role in the hero form only', async () => {
    const wrapper = mount(PrelaunchView)
    const link = wrapper.find('a.dark-link')
    expect(link.attributes('href')).toBe('#join')
    await link.trigger('click')
    expect(wrapper.find('#join input[value="vendor"]').element.checked).toBe(true)
    expect(wrapper.find('#join-2 input[value="buy"]').element.checked).toBe(true)
  })

  it('shows the text fallback when the PS5 photo is missing or fails', async () => {
    const wrapper = mount(PrelaunchView)
    const img = wrapper.find('.photo img')
    if (img.exists()) {
      expect(img.attributes()).toMatchObject({ width: '824', height: '618', loading: 'eager' })
      await img.trigger('error')
    }
    expect(wrapper.find('.photo img').exists()).toBe(false)
    expect(wrapper.find('.photo .ph').text()).toBe('PlayStation 5 Slim')
  })

  it('hides the footer contact links when their env values are empty', () => {
    const wrapper = mount(PrelaunchView)
    expect(wrapper.find('footer').text()).toContain('© 2026 buysafe')
    expect(wrapper.find('footer a').exists()).toBe(false)
  })
})
