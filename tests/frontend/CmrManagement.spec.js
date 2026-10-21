import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import axios from 'axios'
import CmrManagement from '../../frontend/src/components/CmrManagement.vue'

describe('CmrManagement.vue', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders correctly and loads international CMR list', async () => {
    const mockCmrs = [
      {
        id: 1,
        numero: 1,
        anno: 2026,
        numero_completo: 'CMR-2026-0001',
        data_documento: '2026-10-21',
        cliente: { ragione_sociale: "Bio c' Bon Bruxelles", nazione: 'BE' },
        vettore: { ragione_sociale: 'LD Trasporti Srl' },
        luogo_carico: 'ALESSANDRIA (AL)',
        luogo_consegna: 'Rue de la Loi 15, Bruxelles (BE)',
        totale_colli: 50,
        peso_totale_netto: 500.0,
        peso_totale_lordo: 525.0,
        ha_allegato_righe: false,
        stato: 'emesso'
      }
    ]

    vi.spyOn(axios, 'get').mockImplementation((url) => {
      if (url.includes('/api/cmr')) {
        return Promise.resolve({ data: mockCmrs })
      }
      if (url.includes('/api/partners')) {
        return Promise.resolve({ data: [] })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mount(CmrManagement, {
      global: {
        stubs: {
          'q-table': {
            props: ['rows'],
            template: `
              <div class="q-table-stub">
                <div v-for="row in rows" :key="row.id" class="row-stub">
                  <span>{{ row.numero_completo }}</span>
                  <span>{{ row.cliente ? row.cliente.ragione_sociale : '' }}</span>
                  <span>{{ row.luogo_carico }}</span>
                  <span>{{ row.totale_colli }}</span>
                </div>
              </div>
            `
          },
          'q-btn': true,
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
          'q-tooltip': true
        }
      }
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Spedizioni Internazionali & Lettere di Vettura CMR')
    expect(wrapper.text()).toContain('CMR-2026-0001')
    expect(wrapper.text()).toContain("Bio c' Bon Bruxelles")
    expect(wrapper.text()).toContain('ALESSANDRIA (AL)')
  })
})
