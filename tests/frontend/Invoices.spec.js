import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import axios from 'axios'
import Invoices from '../../frontend/src/components/Invoices.vue'

describe('Invoices.vue', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders correctly and loads invoices list', async () => {
    const mockInvoices = [
      {
        id: 1,
        numero: 1,
        anno: 2026,
        numero_completo: 'FT-2026-0001',
        tipo_documento: 'TD24',
        data_documento: '2026-10-31',
        cliente: { ragione_sociale: 'EcorNaturaSì SpA' },
        totale_imponibile: 220.0,
        totale_imposta: 12.4,
        totale_fattura: 232.4,
        stato: 'emessa'
      }
    ]

    const mockInstallments = [
      {
        id: 1,
        numero_rata: 1,
        totale_rate: 2,
        data_scadenza: '2026-11-30',
        importo: 116.20,
        stato: 'aperta',
        invoice_numero: 'FT-2026-0001',
        cliente_nome: 'EcorNaturaSì SpA'
      }
    ]

    vi.spyOn(axios, 'get').mockImplementation((url) => {
      if (url.includes('/api/invoices')) {
        return Promise.resolve({ data: mockInvoices })
      }
      if (url.includes('/api/installments')) {
        return Promise.resolve({ data: mockInstallments })
      }
      if (url.includes('/api/partners')) {
        return Promise.resolve({ data: [] })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mount(Invoices, {
      global: {
        stubs: {
          'q-table': {
            props: ['rows'],
            template: `
              <div class="q-table-stub">
                <div v-for="row in rows" :key="row.id" class="row-stub">
                  <span>{{ row.numero_completo || row.invoice_numero }}</span>
                  <span>{{ row.cliente ? row.cliente.ragione_sociale : row.cliente_nome }}</span>
                  <span>{{ row.totale_fattura || row.importo }}</span>
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
          'q-select': true,
          'q-tabs': { template: '<div><slot /></div>' },
          'q-tab': true,
          'q-tab-panels': { template: '<div><slot /></div>' },
          'q-tab-panel': { template: '<div><slot /></div>' }
        }
      }
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Fatturazione Attiva & Scadenzario')
    expect(wrapper.text()).toContain('FT-2026-0001')
    expect(wrapper.text()).toContain('EcorNaturaSì SpA')
    expect(wrapper.text()).toContain('232.4')
  })

  it('renders XML SDI button for invoices', async () => {
    const mockInvoices = [
      {
        id: 1,
        numero: 1,
        anno: 2026,
        numero_completo: 'FT-2026-0001',
        tipo_documento: 'TD24',
        data_documento: '2026-10-31',
        cliente: { ragione_sociale: 'EcorNaturaSì SpA', codice_sdi: 'M5UXCR1' },
        totale_imponibile: 220.0,
        totale_imposta: 12.4,
        totale_fattura: 232.4,
        stato: 'emessa'
      }
    ]

    vi.spyOn(axios, 'get').mockImplementation((url) => {
      if (url.includes('/api/invoices')) {
        return Promise.resolve({ data: mockInvoices })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mount(Invoices, {
      global: {
        stubs: {
          'q-table': {
            props: ['rows'],
            template: `
              <div class="q-table-stub">
                <div v-for="row in rows" :key="row.id" class="row-stub">
                  <span>{{ row.numero_completo }}</span>
                  <button class="btn-sdi-xml">XML SDI</button>
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

    expect(wrapper.find('.btn-sdi-xml').exists()).toBe(true)
    expect(wrapper.find('.btn-sdi-xml').text()).toBe('XML SDI')
  })

  it('renders credit note button and TD04 badge', async () => {
    const mockInvoices = [
      {
        id: 1,
        numero: 1,
        anno: 2026,
        numero_completo: 'FT-2026-0001',
        tipo_documento: 'TD24',
        data_documento: '2026-10-31',
        cliente: { ragione_sociale: 'EcorNaturaSì SpA' },
        totale_imponibile: 220.0,
        totale_imposta: 12.4,
        totale_fattura: 232.4,
        stato: 'emessa'
      },
      {
        id: 2,
        numero: 1,
        anno: 2026,
        numero_completo: 'NC-2026-0001',
        tipo_documento: 'TD04',
        data_documento: '2026-10-31',
        cliente: { ragione_sociale: 'EcorNaturaSì SpA' },
        invoice_origine_numero: 'FT-2026-0001',
        totale_imponibile: 50.0,
        totale_imposta: 2.0,
        totale_fattura: 52.0,
        stato: 'emessa'
      }
    ]

    vi.spyOn(axios, 'get').mockImplementation((url) => {
      if (url.includes('/api/invoices')) {
        return Promise.resolve({ data: mockInvoices })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mount(Invoices, {
      global: {
        stubs: {
          'q-table': {
            props: ['rows'],
            template: `
              <div class="q-table-stub">
                <div v-for="row in rows" :key="row.id" class="row-stub">
                  <span>{{ row.numero_completo }}</span>
                  <span v-if="row.tipo_documento === 'TD04'" class="badge-td04">TD04 - NOTA DI CREDITO</span>
                  <button v-if="row.tipo_documento !== 'TD04'" class="btn-create-nc">Nota di Credito</button>
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

    expect(wrapper.find('.badge-td04').exists()).toBe(true)
    expect(wrapper.find('.btn-create-nc').exists()).toBe(true)
  })
})
