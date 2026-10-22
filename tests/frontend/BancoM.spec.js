import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import BancoM from '../../frontend/src/components/BancoM.vue'
import axios from 'axios'

vi.mock('axios')

describe('BancoM.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders POS touch interface, products catalog and cart', async () => {
    const mockProducts = [
      { id: 1, codice: 'BIO-MELA', descrizione: 'Mele Golden Bio', prezzo_vendita: 2.50, aliquota_iva: 4 },
      { id: 2, codice: 'BIO-PERA', descrizione: 'Pere Abate Bio', prezzo_vendita: 3.00, aliquota_iva: 4 }
    ]

    const mockStations = [
      { id: 1, codice: 'CASSA_01', nome: 'Cassa Banco Principale', driver_tipo: 'simulator' }
    ]

    const mockSales = []

    vi.spyOn(axios, 'get').mockImplementation((url) => {
      if (url.includes('/api/products')) {
        return Promise.resolve({ data: mockProducts })
      }
      if (url.includes('/api/pos/stations')) {
        return Promise.resolve({ data: mockStations })
      }
      if (url.includes('/api/pos/sales')) {
        return Promise.resolve({ data: mockSales })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mount(BancoM, {
      global: {
        stubs: {
          'q-btn': true,
          'q-btn-toggle': true,
          'q-input': true,
          'q-icon': true,
          'q-dialog': true,
          'q-card': { template: '<div><slot /></div>' },
          'q-card-section': true,
          'q-card-actions': true,
          'q-space': true,
          'q-chip': true,
          'q-badge': true,
          'q-select': true,
          'q-separator': true,
          'q-table': true,
          'q-tabs': { template: '<div><slot /></div>' },
          'q-tab': true,
          'q-tab-panels': { template: '<div><slot /></div>' },
          'q-tab-panel': { template: '<div><slot /></div>' }
        }
      }
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Vendita al Banco')
    expect(wrapper.text()).toContain('Mele Golden Bio')
    expect(wrapper.text()).toContain('Pere Abate Bio')
  })
})
