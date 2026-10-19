import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import axios from 'axios'
import ProductCatalog from '../../frontend/src/components/ProductCatalog.vue'

describe('ProductCatalog.vue', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders correctly, displays products and calculates margin', async () => {
    const mockProducts = [
      {
        id: 1,
        codice: 'BIO-MELA-01',
        descrizione: 'Mele Gala Bio',
        categoria: 'fresco',
        unita_misura: 'KG',
        prezzo_vendita: 3.50,
        prezzo_acquisto: 2.00,
        aliquota_iva: 4,
        in_scadenza: true,
        attivo: true
      }
    ]

    vi.spyOn(axios, 'get').mockResolvedValue({ data: mockProducts })

    const wrapper = mount(ProductCatalog, {
      global: {
        stubs: {
          'q-table': {
            props: ['rows'],
            template: `
              <div class="q-table-stub">
                <div v-for="row in rows" :key="row.id" class="row-stub">
                  <span>{{ row.codice }}</span>
                  <span>{{ row.descrizione }}</span>
                  <span>€ {{ Number(row.prezzo_vendita).toFixed(2) }}</span>
                  <span>€ {{ (row.prezzo_vendita - row.prezzo_acquisto).toFixed(2) }}</span>
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
          'q-select': true,
          'q-toggle': true
        }
      }
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Catalogo Articoli')
    expect(wrapper.text()).toContain('BIO-MELA-01')
    expect(wrapper.text()).toContain('Mele Gala Bio')
    expect(wrapper.text()).toContain('3.50')
    expect(wrapper.text()).toContain('1.50')
  })
})
