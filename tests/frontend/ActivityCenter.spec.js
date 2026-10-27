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

  it('renders Event Types and Redis queues catalog', async () => {
    const mockTypes = [
      { id: 1, codice: 'EMISSIONE_DDT', nome: 'Emissione DDT', modalita_esecuzione: 'sincrono', coda_nome: 'default' },
      { id: 2, codice: 'SOLLECITO_PALLET', nome: 'Sollecito Pallet', modalita_esecuzione: 'asincrono', coda_nome: 'emails' }
    ]

    const mockQueues = {
      queues: [
        { name: 'critical', count: 0, active: true },
        { name: 'emails', count: 2, active: true },
        { name: 'batch', count: 1, active: true },
        { name: 'default', count: 0, active: true }
      ]
    }

    vi.spyOn(axios, 'get').mockImplementation((url) => {
      if (url.includes('/api/events/types')) {
        return Promise.resolve({ data: mockTypes })
      }
      if (url.includes('/api/events/queues')) {
        return Promise.resolve({ data: mockQueues })
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
                <div v-for="row in rows" :key="row.id || row.name" class="row-stub">
                  <span>{{ row.nome || row.name }}</span>
                  <span>{{ row.modalita_esecuzione }}</span>
                  <span>{{ row.coda_nome }}</span>
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

    expect(wrapper.text()).toContain('Policy di Esecuzione Eventi di Sistema')
    expect(wrapper.text()).toContain('Emissione DDT')
    expect(wrapper.text()).toContain('Sollecito Pallet')
  })

  it('updates events in real-time when websocket broadcast is received', async () => {
    const mockEvents = [
      {
        id: 10,
        channel_codice: 'AUDIT',
        titolo: 'Evento Iniziale',
        stato: 'completato',
        progresso: 100,
        is_async: false
      }
    ]

    vi.spyOn(axios, 'get').mockImplementation((url) => {
      if (url.includes('/api/events')) return Promise.resolve({ data: mockEvents })
      return Promise.resolve({ data: [] })
    })

    const { wsService } = await import('../../frontend/src/services/websocket.js')

    const wrapper = mount(ActivityCenter, {
      global: {
        stubs: {
          'q-table': {
            props: ['rows'],
            template: `
              <div class="q-table-stub">
                <div v-for="row in rows" :key="row.id" class="row-stub">
                  <span>{{ row.titolo }}</span>
                  <span>{{ row.stato }}</span>
                  <span>{{ row.progresso }}</span>
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
          'q-linear-progress': true,
          'q-tabs': { template: '<div><slot /></div>' },
          'q-tab': true,
          'q-tab-panels': { template: '<div><slot /></div>' },
          'q-tab-panel': { template: '<div><slot /></div>' }
        }
      }
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Evento Iniziale')

    // Simulate incoming real-time websocket event
    wsService.notifyListeners({
      type: 'SYSTEM_EVENT',
      action: 'created',
      event: {
        id: 99,
        channel_codice: 'AUDIT',
        titolo: 'Nuovo Ordine RealTime #99',
        stato: 'completato',
        progresso: 100,
        is_async: false
      }
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Nuovo Ordine RealTime #99')

    // Simulate progress update on existing event
    wsService.notifyListeners({
      type: 'SYSTEM_EVENT',
      action: 'progress',
      event: {
        id: 99,
        channel_codice: 'AUDIT',
        titolo: 'Nuovo Ordine RealTime #99 (Aggiornato)',
        stato: 'in_corso',
        progresso: 75,
        is_async: false
      }
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Nuovo Ordine RealTime #99 (Aggiornato)')
    expect(wrapper.text()).toContain('75')
  })

  it('renders metrics & monitoring tab with KPI cards and Grafana button', async () => {
    vi.spyOn(axios, 'get').mockImplementation((url) => {
      if (url === '/api/events') return Promise.resolve({ data: [] })
      if (url === '/api/events/channels') return Promise.resolve({ data: [] })
      if (url === '/api/events/types') return Promise.resolve({ data: [] })
      if (url === '/api/events/queues') return Promise.resolve({ data: [] })
      if (url === '/api/metrics/summary') {
        return Promise.resolve({
          data: {
            http: { total_requests: 1250, avg_latency_ms: 3.5, success_rate_pct: 99.8, status_2xx: 1248, status_4xx: 2, status_5xx: 0 },
            websockets: { active_clients: 3, total_broadcasts: 42 },
            queues_rq: { total_pending: 1, total_failed: 0, critical: 0, emails: 1, reports: 0, default: 0 },
            business_totals: { orders: 15, invoices: 8, pos_sales: 24 }
          }
        })
      }
      return Promise.resolve({ data: {} })
    })

    const wrapper = mount(ActivityCenter, {
      global: {
        stubs: {
          'q-btn': { template: '<button>{{ label }}<slot /></button>', props: ['label'] },
          'q-badge': { template: '<span><slot /></span>' },
          'q-tabs': { template: '<div><slot /></div>' },
          'q-tab': { template: '<div>{{ label }}<slot /></div>', props: ['label'] },
          'q-tab-panels': { template: '<div><slot /></div>' },
          'q-tab-panel': { template: '<div><slot /></div>' },
          'q-card': { template: '<div><slot /></div>' },
          'q-card-section': { template: '<div><slot /></div>' },
          'q-icon': { template: '<i></i>' },
          'q-separator': { template: '<hr />' }
        }
      }
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Metriche & Ops')
    expect(wrapper.text()).toContain('Apri Grafana Dashboard ↗')
    expect(wrapper.text()).toContain('LATENZA MEDIA API')
    expect(wrapper.text()).toContain('3.5')
    expect(wrapper.text()).toContain('WEBSOCKET CONNESSI')
    expect(wrapper.text()).toContain('3')
    expect(wrapper.text()).toContain('TRAFFICO & AFFIDABILITÀ')
    expect(wrapper.text()).toContain('99.8%')
  })
})

