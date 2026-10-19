import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import axios from 'axios'
import PartnerManagement from '../../frontend/src/components/PartnerManagement.vue'

describe('PartnerManagement.vue', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders correctly and loads partners list', async () => {
    const mockPartners = [
      {
        id: 1,
        ragione_sociale: 'Cooperativa Bio Rete',
        tipo: 'fornitore',
        partita_iva: 'IT01234567890',
        citta: 'Reggio Emilia',
        provincia: 'RE',
        codice_sdi: 'M5UXCR1',
        attivo: true
      }
    ]

    vi.spyOn(axios, 'get').mockResolvedValue({ data: mockPartners })

    const wrapper = mount(PartnerManagement, {
      global: {
        stubs: {
          'q-table': {
            props: ['rows'],
            template: `
              <div class="q-table-stub">
                <div v-for="row in rows" :key="row.id" class="row-stub">
                  <span>{{ row.ragione_sociale }}</span>
                  <span>{{ row.codice_sdi }}</span>
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

    expect(wrapper.text()).toContain('Anagrafica Soggetti')
    expect(wrapper.text()).toContain('Cooperativa Bio Rete')
    expect(wrapper.text()).toContain('M5UXCR1')
  })
})
