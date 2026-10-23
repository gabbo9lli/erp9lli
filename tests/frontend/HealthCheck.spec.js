import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import HealthCheck from '../../frontend/src/components/HealthCheck.vue'

describe('HealthCheck.vue', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders correctly and fetches health status on mount', async () => {
    const mockHealth = {
      status: 'UP',
      fastapi_status: 'UP',
      database: {
        status: 'UP',
        type: 'postgresql',
        connection_error: null
      }
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockHealth
    })

    const wrapper = mount(HealthCheck)

    expect(wrapper.find('h3').text()).toBe('System Health Check')
    expect(wrapper.find('button').text()).toBe('Refresh Status')

    await flushPromises()

    expect(global.fetch).toHaveBeenCalledWith('/api/health')
    expect(wrapper.text()).toContain('UP')
    expect(wrapper.text()).toContain('postgresql')
  })

  it('handles backend offline error gracefully', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'))

    const wrapper = mount(HealthCheck)
    await flushPromises()

    expect(wrapper.text()).toContain('DOWN')
  })
})
