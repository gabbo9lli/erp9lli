import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import axios from 'axios'
import Orders from '../../frontend/src/components/Orders.vue'

describe('Orders.vue', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders correctly and loads orders list', async () => {
    const mockOrders = [
      {
        id: 1,
        numero: 1,
        anno: 2026,
        numero_completo: 'ORD-2026-0001',
        data_ordine: '2026-10-20',
        data_richiesta: '2026-10-25',
        cliente: { ragione_sociale: 'EcorNaturaSì' },
        stato: 'aperto',
        totale_imponibile: 400.0,
        items: [
          {
            id: 1,
            sequenza: 5,
            descrizione: 'Mele Bio',
            colli_ordinati: 10,
            quantita_ordinata: 100.0,
            colli_consegnati: 0,
            quantita_consegnata: 0.0,
            colli_residui: 10,
            quantita_residua: 100.0
          }
        ]
      }
    ]

    vi.spyOn(axios, 'get').mockImplementation((url) => {
      if (url.includes('/api/orders')) {
        return Promise.resolve({ data: mockOrders })
      }
      if (url.includes('/api/partners')) {
        return Promise.resolve({ data: [] })
      }
      if (url.includes('/api/products')) {
        return Promise.resolve({ data: [] })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mount(Orders, {
      global: {
        stubs: {
          'q-table': {
            props: ['rows'],
            template: `
              <div class="q-table-stub">
                <div v-for="row in rows" :key="row.id" class="row-stub">
                  <span>{{ row.numero_completo }}</span>
                  <span>{{ row.cliente ? row.cliente.ragione_sociale : '' }}</span>
                  <span>{{ row.totale_imponibile }}</span>
                  <span>{{ row.stato }}</span>
                </div>
              </div>
            `
          },
          'q-btn': true,
          'q-btn-toggle': true,
          'q-input': true,
          'q-icon': true,
          'q-dialog': true,
          'q-card': true,
          'q-card-section': true,
          'q-card-actions': true,
          'q-space': true,
          'q-chip': true,
          'q-badge': true,
          'q-select': true,
          'q-separator': true,
          'q-linear-progress': true
        }
      }
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Gestione Ordini Clienti')
    expect(wrapper.text()).toContain('ORD-2026-0001')
    expect(wrapper.text()).toContain('EcorNaturaSì')
  })
})
