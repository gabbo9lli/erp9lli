import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import axios from 'axios'
import Accounting from '../../frontend/src/components/Accounting.vue'

describe('Accounting.vue', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders correctly and loads accounting entries', async () => {
    const mockEntries = [
      {
        id: 1,
        numero: 1,
        anno: 2026,
        numero_completo: 'PN-2026-0001',
        data_registrazione: '2026-10-20',
        causale: 'Vendita ortofrutta incasso',
        totale_dare: 150.0,
        totale_avere: 150.0,
        stato: 'confermata'
      }
    ]

    const mockAccounts = [
      { id: 1, codice: '1002', nome: 'Banca c/c Principale', tipo: 'attivo' },
      { id: 2, codice: '4101', nome: 'Ricavi Vendite Bio', tipo: 'ricavi' }
    ]

    vi.spyOn(axios, 'get').mockImplementation((url) => {
      if (url.includes('/api/accounting/entries')) {
        return Promise.resolve({ data: mockEntries })
      }
      if (url.includes('/api/accounting/accounts')) {
        return Promise.resolve({ data: mockAccounts })
      }
      if (url.includes('/api/accounting/reports/libro-giornale')) {
        return Promise.resolve({ data: { righe: [], totale_dare: 150.0, totale_avere: 150.0 } })
      }
      if (url.includes('/api/accounting/reports/bilancio-verifica')) {
        return Promise.resolve({ data: { conti: [], totale_dare: 150.0, totale_avere: 150.0 } })
      }
      if (url.includes('/api/partners')) {
        return Promise.resolve({ data: [] })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mount(Accounting, {
      global: {
        stubs: {
          'q-table': {
            props: ['rows'],
            template: `
              <div class="q-table-stub">
                <div v-for="row in rows" :key="row.id" class="row-stub">
                  <span>{{ row.numero_completo || row.codice }}</span>
                  <span>{{ row.causale || row.nome }}</span>
                  <span>{{ row.totale_dare }}</span>
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

    expect(wrapper.text()).toContain('Contabilità Generale & Partita Doppia')
    expect(wrapper.text()).toContain('PN-2026-0001')
    expect(wrapper.text()).toContain('Vendita ortofrutta incasso')
  })

  it('renders Causali Contabili & Automatismi tab and list', async () => {
    const mockCausals = [
      { id: 1, codice: 'VEND_FATT', descrizione: 'Fattura di Vendita a Cliente', tipo_registro: 'vendite', conto_dare_codice: '1101', conto_avere_codice: '4101', conto_iva_codice: '2201' },
      { id: 2, codice: 'INCASSO_RATA', descrizione: 'Incasso Rata Fattura Cliente', tipo_registro: 'generale', conto_dare_codice: '1002', conto_avere_codice: '1101' }
    ]

    vi.spyOn(axios, 'get').mockImplementation((url) => {
      if (url.includes('/api/accounting/causals')) {
        return Promise.resolve({ data: mockCausals })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mount(Accounting, {
      global: {
        stubs: {
          'q-table': {
            props: ['rows'],
            template: `
              <div class="q-table-stub">
                <div v-for="row in rows" :key="row.id" class="row-stub">
                  <span>{{ row.codice }}</span>
                  <span>{{ row.descrizione }}</span>
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

    expect(wrapper.text()).toContain('Causali Contabili & Automatismi')
    expect(wrapper.text()).toContain('VEND_FATT')
    expect(wrapper.text()).toContain('Fattura di Vendita a Cliente')
  })
})
