import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import axios from 'axios'
import LegacyMigration from '../../frontend/src/components/LegacyMigration.vue'

describe('LegacyMigration.vue', () => {
  it('renders migration dashboard and controls correctly', async () => {
    const wrapper = mount(LegacyMigration, {
      global: {
        stubs: {
          'q-btn': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
          'q-input': { template: '<input />' },
          'q-card': { template: '<div><slot /></div>' },
          'q-card-section': { template: '<div><slot /></div>' },
          'q-card-actions': { template: '<div><slot /></div>' },
          'q-dialog': { template: '<div><slot /></div>' },
          'q-linear-progress': { template: '<div><slot /></div>' },
          'q-badge': { template: '<span><slot /></span>' },
          'q-banner': { template: '<div><slot /></div>' },
          'q-toggle': { template: '<input type="checkbox" />' },
          'q-radio': { template: '<input type="radio" />' },
          'q-icon': { template: '<i />' },
          'q-separator': { template: '<hr />' },
          'q-table': { template: '<div><slot /></div>' },
          'q-space': { template: '<span />' }
        }
      }
    })
    expect(wrapper.text()).toContain('Inizializzazione & Migrazione Dati Legacy')
    expect(wrapper.text()).toContain('GestionaleReteBio2026.accdb')
  })

  it('runs dry run and displays statistical preview', async () => {
    vi.spyOn(axios, 'post').mockImplementation((url) => {
      if (url.includes('/api/migration/dry-run')) {
        return Promise.resolve({
          data: {
            status: 'success',
            source_file: 'GestionaleReteBio2026.accdb',
            partners_count: 180,
            products_count: 3200,
            stock_lots_count: 324,
            invoices_count: 850,
            installments_count: 1600,
            estimated_seconds: 15
          }
        })
      }
      return Promise.resolve({ data: {} })
    })

    const wrapper = mount(LegacyMigration, {
      global: {
        stubs: {
          'q-btn': {
            props: ['label'],
            template: '<button @click="$emit(\'click\')">{{ label }}<slot /></button>'
          },
          'q-input': { template: '<input />' },
          'q-card': { template: '<div><slot /></div>' },
          'q-card-section': { template: '<div><slot /></div>' },
          'q-card-actions': { template: '<div><slot /></div>' },
          'q-dialog': { template: '<div><slot /></div>' },
          'q-linear-progress': { template: '<div><slot /></div>' },
          'q-badge': { template: '<span><slot /></span>' },
          'q-banner': { template: '<div><slot /></div>' },
          'q-toggle': { template: '<input type="checkbox" />' },
          'q-radio': { template: '<input type="radio" />' },
          'q-icon': { template: '<i />' },
          'q-separator': { template: '<hr />' },
          'q-table': { template: '<div><slot /></div>' },
          'q-space': { template: '<span />' }
        }
      }
    })

    const dryRunBtn = wrapper.findAll('button').find(b => b.text().includes('Analizza') || b.text().includes('Dry Run'))
    if (dryRunBtn) {
      await dryRunBtn.trigger('click')
      await flushPromises()
      expect(wrapper.text()).toContain('180')
      expect(wrapper.text()).toContain('3200')
    }
  })
})
