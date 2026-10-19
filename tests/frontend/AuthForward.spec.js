import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import Auth from '../../frontend/src/components/Auth.vue'
import App from '../../frontend/src/App.vue'

describe('AuthForward & SSO Integration', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders SSO / OIDC button on Auth.vue with proper link', () => {
    const wrapper = mount(Auth)
    const ssoBtn = wrapper.find('.sso-btn')
    expect(ssoBtn.exists()).toBe(true)
    expect(ssoBtn.text()).toContain('Accedi con SSO / OIDC')
    expect(ssoBtn.attributes('href')).toBe('/oauth2/start?rd=/dashboard')
  })

  it('calls /api/me on App.vue mount and populates user session when authenticated', async () => {
    const mockUser = {
      authenticated: true,
      id: 1,
      email: 'test@company.com',
      username: 'testuser',
      role: 'Admin'
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockUser
    })

    const wrapper = mount(App, {
      global: {
        stubs: {
          'router-link': { template: '<a><slot /></a>' },
          'router-view': true
        }
      }
    })

    await flushPromises()

    expect(global.fetch).toHaveBeenCalledWith('/api/me')
    expect(wrapper.text()).toContain('testuser')
    expect(wrapper.text()).toContain('Admin')
  })
})
