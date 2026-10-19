import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import Settings from '../../frontend/src/components/Settings.vue'

describe('Settings.vue', () => {
  let mockStorage = {}

  beforeEach(() => {
    mockStorage = {}
    vi.stubGlobal('localStorage', {
      getItem: vi.fn((key) => mockStorage[key] || null),
      setItem: vi.fn((key, value) => { mockStorage[key] = String(value) }),
      removeItem: vi.fn((key) => { delete mockStorage[key] }),
      clear: vi.fn(() => { mockStorage = {} })
    })
    window.alert = vi.fn()
  })

  it('renders user session and default theme', () => {
    mockStorage['user_session'] = 'admin@example.com'

    const wrapper = mount(Settings)
    const emailInput = wrapper.find('input[type="text"]')
    expect(emailInput.element.value).toBe('admin@example.com')

    const select = wrapper.find('select')
    expect(select.element.value).toBe('light')
  })

  it('saves updated theme configuration to localStorage', async () => {
    mockStorage['user_session'] = 'user@example.com'
    const wrapper = mount(Settings)

    const select = wrapper.find('select')
    await select.setValue('dark')

    const button = wrapper.find('button.save-btn')
    await button.trigger('click')

    const savedConfig = JSON.parse(mockStorage['user_config'])
    expect(savedConfig.theme).toBe('dark')
    expect(window.alert).toHaveBeenCalledWith('Settings saved locally!')
  })
})
