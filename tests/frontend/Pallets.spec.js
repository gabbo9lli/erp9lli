import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import axios from 'axios'
import Pallets from '../../frontend/src/components/Pallets.vue'

describe('Pallets.vue', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders correctly and loads pallet receipts list', async () => {
    const mockReceipts = [
      {
        id: 1,
        numero: 1,
        anno: 2026,
        numero_completo: 'BP-2026-0001',
        data_emissione: '2026-10-21',
        data_limite_restituzione: '2026-12-20',
        partner: { ragione_sociale: 'EcorNaturaSì SpA' },
        totale_consegnati: 20,
        totale_restituiti: 5,
        saldo_netto: 15,
        stato: 'aperto',
        scaduto: false,
        giorni_rimanenti: 60
      }
    ]

    const mockLedger = [
      {
        partner_id: 1,
        partner_nome: 'EcorNaturaSì SpA',
        partner_tipo: 'cliente',
        saldi: { 'EPAL': 15 },
        totale_bancali_debito: 15,
        buoni_aperti_count: 1,
        buoni_scaduti_count: 0
      }
    ]

    vi.spyOn(axios, 'get').mockImplementation((url) => {
      if (url.includes('/api/pallets/receipts')) {
        return Promise.resolve({ data: mockReceipts })
      }
      if (url.includes('/api/pallets/ledger')) {
        return Promise.resolve({ data: mockLedger })
      }
      if (url.includes('/api/pallets/types')) {
        return Promise.resolve({ data: [] })
      }
      if (url.includes('/api/partners')) {
        return Promise.resolve({ data: [] })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mount(Pallets, {
      global: {
        stubs: {
          'q-table': {
            props: ['rows'],
            template: `
              <div class="q-table-stub">
                <div v-for="row in rows" :key="row.id || row.partner_id" class="row-stub">
                  <span>{{ row.numero_completo || row.partner_nome }}</span>
                  <span>{{ row.partner ? row.partner.ragione_sociale : '' }}</span>
                  <span>{{ row.saldo_netto || row.totale_bancali_debito }}</span>
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
          'q-tabs': { template: '<div><slot /></div>' },
          'q-tab': true,
          'q-tab-panels': { template: '<div><slot /></div>' },
          'q-tab-panel': { template: '<div><slot /></div>' }
        }
      }
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Interscambio Pallet & Buoni Pallet (L. 182/2025)')
    expect(wrapper.text()).toContain('BP-2026-0001')
    expect(wrapper.text()).toContain('EcorNaturaSì SpA')
  })
})
