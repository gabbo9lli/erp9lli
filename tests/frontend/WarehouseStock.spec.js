import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import axios from 'axios'
import WarehouseStock from '../../frontend/src/components/WarehouseStock.vue'

describe('WarehouseStock.vue', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders correctly and loads stock lots list', async () => {
    const mockStock = [
      {
        product_id: 1,
        product_codice: 'BIO-MELA',
        product_descrizione: 'Mele Golden Bio',
        lotto: 'LOTTO-2026-MELA',
        data_scadenza: '2026-11-20',
        giorni_a_scadere: 30,
        stato_scadenza: 'fresco',
        giacenza_kg: 140.0,
        colli_disponibili: 14
      }
    ]

    vi.spyOn(axios, 'get').mockImplementation((url) => {
      if (url.includes('/api/warehouse/stock')) {
        return Promise.resolve({ data: mockStock })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mount(WarehouseStock, {
      global: {
        stubs: {
          'q-table': {
            props: ['rows'],
            template: `
              <div class="q-table-stub">
                <div v-for="row in rows" :key="row.lotto" class="row-stub">
                  <span>{{ row.product_codice }}</span>
                  <span>{{ row.product_descrizione }}</span>
                  <span>{{ row.lotto }}</span>
                  <span>{{ row.giacenza_kg }}</span>
                  <span>{{ row.stato_scadenza }}</span>
                </div>
              </div>
            `
          },
          'q-btn': true,
          'q-input': true,
          'q-icon': true,
          'q-space': true,
          'q-chip': true,
          'q-badge': true
        }
      }
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Giacenze Magazzino & Tracciabilità FEFO')
    expect(wrapper.text()).toContain('BIO-MELA')
    expect(wrapper.text()).toContain('LOTTO-2026-MELA')
    expect(wrapper.text()).toContain('140')
  })
})
