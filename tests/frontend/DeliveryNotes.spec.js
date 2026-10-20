import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import axios from 'axios'
import DeliveryNotes from '../../frontend/src/components/DeliveryNotes.vue'

describe('DeliveryNotes.vue', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders correctly and loads delivery notes list', async () => {
    const mockDdts = [
      {
        id: 1,
        numero: 1,
        anno: 2026,
        numero_completo: 'DDT-2026-0001',
        data_documento: '2026-10-20',
        cliente: { ragione_sociale: 'EcorNaturaSì SpA' },
        vettore: { ragione_sociale: 'LD Trasporti Srl' },
        colli_totali: 15,
        peso_totale_netto: 150.0,
        totale_imponibile: 400.0,
        stato: 'confermato'
      }
    ]

    vi.spyOn(axios, 'get').mockImplementation((url) => {
      if (url.includes('/api/delivery-notes')) {
        return Promise.resolve({ data: mockDdts })
      }
      if (url.includes('/api/partners')) {
        return Promise.resolve({ data: [] })
      }
      if (url.includes('/api/products')) {
        return Promise.resolve({ data: [] })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mount(DeliveryNotes, {
      global: {
        stubs: {
          'q-table': {
            props: ['rows'],
            template: `
              <div class="q-table-stub">
                <div v-for="row in rows" :key="row.id" class="row-stub">
                  <span>{{ row.numero_completo }}</span>
                  <span>{{ row.cliente ? row.cliente.ragione_sociale : '' }}</span>
                  <span>{{ row.colli_totali }}</span>
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
          'q-select': true
        }
      }
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Documenti di Trasporto (DDT)')
    expect(wrapper.text()).toContain('DDT-2026-0001')
    expect(wrapper.text()).toContain('EcorNaturaSì SpA')
    expect(wrapper.text()).toContain('confermato')
  })
})
