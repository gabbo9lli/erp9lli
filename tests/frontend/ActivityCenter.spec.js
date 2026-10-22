import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import axios from 'axios'
import ActivityCenter from '../../frontend/src/components/ActivityCenter.vue'

describe('ActivityCenter.vue', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders correctly and displays audit trail and background jobs', async () => {
    const mockEvents = [
      {
        id: 1,
        channel_codice: 'AUDIT',
        channel_nome: 'Audit Log Attività',
        category_codice: 'LOGISTICA',
        category_nome: 'Logistica & Magazzino',
        category_colore: 'teal',
        category_icona: 'inventory_2',
        azione: 'emissione_ddt',
        titolo: 'Emesso DDT-2026-0001',
        descrizione: 'Bolla vendita per EcorNaturaSì',
        stato: 'completato',
        progresso: 100,
        is_async: false,
        data_creazione: '2026-10-22T08:00:00'
      },
      {
        id: 2,
        channel_codice: 'EMAIL',
        channel_nome: 'Posta Elettronica Ordinaria',
        category_codice: 'PALLET',
        category_nome: 'Interscambio Pallet L.182',
        category_colore: 'deep-orange',
        category_icona: 'layers',
        azione: 'sollecito_pallet',
        titolo: 'Sollecito Buono Pallet BP-2026-0001',
        destinatario_recapito: 'cliente@bio.it',
        stato: 'test',
        progresso: 100,
        is_async: false,
        data_creazione: '2026-10-22T08:15:00'
      },
      {
        id: 3,
        channel_codice: 'EMAIL',
        channel_nome: 'Posta Elettronica Ordinaria',
        category_codice: 'PALLET',
        category_nome: 'Interscambio Pallet L.182',
        category_colore: 'deep-orange',
        category_icona: 'layers',
        azione: 'sollecito_massivo_pallet',
        titolo: 'Sollecito Massivo Buoni Pallet Scaduti',
        stato: 'in_corso',
        progresso: 50,
        is_async: true,
        data_creazione: '2026-10-22T08:30:00'
      }
    ]

    const mockChannels = [
      { id: 1, codice: 'AUDIT', nome: 'Audit Log Attività', tipo_dispatcher: 'internal', attivo: true },
      { id: 2, codice: 'EMAIL', nome: 'Posta Elettronica Ordinaria', tipo_dispatcher: 'smtp', attivo: true }
    ]

    vi.spyOn(axios, 'get').mockImplementation((url) => {
      if (url.includes('/api/events/channels')) {
        return Promise.resolve({ data: mockChannels })
      }
      if (url.includes('/api/events/categories')) {
        return Promise.resolve({ data: [] })
      }
      if (url.includes('/api/events')) {
        return Promise.resolve({ data: mockEvents })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mount(ActivityCenter, {
      global: {
        stubs: {
          'q-table': {
            props: ['rows'],
            template: `
              <div class="q-table-stub">
                <div v-for="row in rows" :key="row.id" class="row-stub">
                  <span>{{ row.titolo || row.nome }}</span>
                  <span>{{ row.stato }}</span>
                  <span>{{ row.progresso }}</span>
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
          'q-linear-progress': true,
          'q-tabs': { template: '<div><slot /></div>' },
          'q-tab': true,
          'q-tab-panels': { template: '<div><slot /></div>' },
          'q-tab-panel': { template: '<div><slot /></div>' }
        }
      }
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Centro Attività, Code & Comunicazioni')
    expect(wrapper.text()).toContain('Emesso DDT-2026-0001')
    expect(wrapper.text()).toContain('Sollecito Buono Pallet BP-2026-0001')
  })
})
