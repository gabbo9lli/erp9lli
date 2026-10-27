<template>
  <div class="q-pa-md">
    <div class="row items-center justify-between q-mb-md">
      <div>
        <div class="row items-center">
          <h2 class="text-h5 text-weight-bold q-my-none">Centro Attività, Code & Comunicazioni</h2>
          <q-badge :color="wsConnected ? 'positive' : 'grey-6'" :label="wsConnected ? 'LIVE WS' : 'OFFLINE'" class="q-ml-sm" />
        </div>
        <div class="text-caption text-grey-7">Audit Trail delle operazioni, Coda task asincroni in background e Registro Comunicazioni Outbox</div>
      </div>
      <div>
        <q-btn color="primary" icon="refresh" label="Aggiorna" @click="fetchData" />
      </div>
    </div>

    <!-- Schede di Navigazione -->
    <q-tabs v-model="activeTab" dense class="text-grey" active-color="primary" indicator-color="primary" align="left">
      <q-tab name="audit" label="Registro Attività (Audit)" icon="history" />
      <q-tab name="queue" label="Coda Task in Background" icon="pending_actions" />
      <q-tab name="outbox" label="Comunicazioni & Email" icon="forward_to_inbox" />
      <q-tab name="channels" label="Anagrafica Canali" icon="settings_input_component" />
      <q-tab name="types" label="Catalogo Eventi & Code" icon="tune" />
      <q-tab name="metrics" label="Metriche & Ops" icon="insights" />
    </q-tabs>

    <q-separator class="q-mb-md" />

    <q-tab-panels v-model="activeTab" animated>
      <!-- TAB 1: AUDIT TRAIL -->
      <q-tab-panel name="audit" class="q-pa-none">
        <div class="row q-gutter-sm items-center q-mb-md">
          <q-input 
            v-model="searchTerm" 
            dense 
            outlined 
            placeholder="Cerca attività per titolo o azione..." 
            @update:model-value="fetchEvents"
            style="min-width: 320px"
          >
            <template v-slot:append>
              <q-icon name="search" />
            </template>
          </q-input>
        </div>

        <q-table
          :rows="auditEvents"
          :columns="auditColumns"
          row-key="id"
          :loading="loading"
          flat
          bordered
        >
          <template v-slot:body-cell-categoria="props">
            <q-td :props="props">
              <q-chip dense :color="props.row.category_colore || 'primary'" text-color="white" :icon="props.row.category_icona || 'info'">
                {{ props.row.category_nome || props.row.category_codice || 'SISTEMA' }}
              </q-chip>
            </q-td>
          </template>

          <template v-slot:body-cell-titolo="props">
            <q-td :props="props">
              <div class="text-weight-bold">{{ props.row.titolo }}</div>
              <div v-if="props.row.descrizione" class="text-caption text-grey-7">{{ props.row.descrizione }}</div>
            </q-td>
          </template>

          <template v-slot:body-cell-stato="props">
            <q-td :props="props" align="center">
              <q-chip dense :color="getStatusColor(props.row.stato)" text-color="white" size="sm">
                {{ props.row.stato.toUpperCase() }}
              </q-chip>
            </q-td>
          </template>

          <template v-slot:body-cell-actions="props">
            <q-td :props="props" align="right">
              <q-btn flat round dense color="primary" icon="visibility" @click="viewEvent(props.row)" />
            </q-td>
          </template>
        </q-table>
      </q-tab-panel>

      <!-- TAB 2: CODA TASK IN BACKGROUND -->
      <q-tab-panel name="queue" class="q-pa-none">
        <q-table
          :rows="queueTasks"
          :columns="queueColumns"
          row-key="id"
          :loading="loading"
          flat
          bordered
        >
          <template v-slot:body-cell-titolo="props">
            <q-td :props="props">
              <div class="text-weight-bold">{{ props.row.titolo }}</div>
              <div class="text-caption text-grey-7">Azione: {{ props.row.azione }}</div>
            </q-td>
          </template>

          <template v-slot:body-cell-progresso="props">
            <q-td :props="props" style="min-width: 180px">
              <div class="row items-center q-gutter-xs">
                <div class="col">
                  <q-linear-progress 
                    :value="props.row.progresso / 100" 
                    :color="props.row.stato === 'errore' ? 'negative' : (props.row.progresso === 100 ? 'positive' : 'primary')" 
                    rounded 
                    size="8px"
                  />
                </div>
                <div class="text-caption text-weight-bold">{{ props.row.progresso }}%</div>
              </div>
            </q-td>
          </template>

          <template v-slot:body-cell-stato="props">
            <q-td :props="props" align="center">
              <q-chip dense :color="getStatusColor(props.row.stato)" text-color="white" size="sm">
                {{ props.row.stato.toUpperCase() }}
              </q-chip>
            </q-td>
          </template>

          <template v-slot:body-cell-actions="props">
            <q-td :props="props" align="right">
              <q-btn 
                v-if="props.row.stato === 'errore'" 
                color="negative" 
                icon="refresh" 
                label="Riprova" 
                dense 
                size="sm" 
                @click="retryTask(props.row)"
              />
              <q-btn flat round dense color="primary" icon="visibility" @click="viewEvent(props.row)" class="q-ml-xs" />
            </q-td>
          </template>
        </q-table>
      </q-tab-panel>

      <!-- TAB 3: COMUNICAZIONI OUTBOX -->
      <q-tab-panel name="outbox" class="q-pa-none">
        <q-table
          :rows="outboxMessages"
          :columns="outboxColumns"
          row-key="id"
          :loading="loading"
          flat
          bordered
        >
          <template v-slot:body-cell-canale="props">
            <q-td :props="props">
              <q-badge color="indigo-8" text-color="white">{{ props.row.channel_codice }}</q-badge>
            </q-td>
          </template>

          <template v-slot:body-cell-destinatario="props">
            <q-td :props="props">
              <div class="text-weight-bold">{{ props.row.destinatario_recapito || 'N.D.' }}</div>
              <div v-if="props.row.partner_nome" class="text-caption text-grey-7">{{ props.row.partner_nome }}</div>
            </q-td>
          </template>

          <template v-slot:body-cell-stato="props">
            <q-td :props="props" align="center">
              <q-badge :color="getStatusColor(props.row.stato)">
                {{ props.row.stato === 'test' ? 'TEST (DB SIMULATO)' : props.row.stato.toUpperCase() }}
              </q-badge>
            </q-td>
          </template>

          <template v-slot:body-cell-actions="props">
            <q-td :props="props" align="right">
              <q-btn flat round dense color="primary" icon="visibility" @click="viewEvent(props.row)" />
            </q-td>
          </template>
        </q-table>
      </q-tab-panel>

      <!-- TAB 4: ANAGRAFICA CANALI -->
      <q-tab-panel name="channels" class="q-pa-none">
        <div class="row justify-between items-center q-mb-md">
          <div class="text-subtitle1 text-weight-bold">Canali di Comunicazione Estendibili</div>
          <q-btn color="secondary" icon="add" label="Nuovo Canale" size="sm" @click="openNewChannelDialog()" />
        </div>

        <q-table
          :rows="channels"
          :columns="channelColumns"
          row-key="id"
          flat
          bordered
        >
          <template v-slot:body-cell-attivo="props">
            <q-td :props="props" align="center">
              <q-badge :color="props.row.attivo ? 'positive' : 'grey'">
                {{ props.row.attivo ? 'ATTIVO' : 'DISATTIVATO' }}
              </q-badge>
            </q-td>
          </template>
        </q-table>
      </q-tab-panel>

      <!-- TAB 5: CATALOGO EVENTI & CODE REDIS -->
      <q-tab-panel name="types" class="q-pa-none">
        <!-- Widget Monitor Code Redis -->
        <div class="row q-col-gutter-sm q-mb-md">
          <div v-for="q in queues" :key="q.name" class="col-12 col-sm-6 col-md-3">
            <div class="bg-white q-pa-sm rounded-borders border-grey shadow-1">
              <div class="text-caption text-uppercase text-grey-7">Coda: <strong>{{ q.name }}</strong></div>
              <div class="row items-center justify-between q-mt-xs">
                <span class="text-h6 text-weight-bold" :class="q.count > 0 ? 'text-primary' : 'text-grey-6'">
                  {{ q.count }} job
                </span>
                <q-badge :color="q.active ? 'positive' : 'grey'">
                  {{ q.active ? 'REDIS ATTIVO' : 'MOCK' }}
                </q-badge>
              </div>
            </div>
          </div>
        </div>

        <div class="row justify-between items-center q-mb-sm">
          <div>
            <div class="text-subtitle1 text-weight-bold">Policy di Esecuzione Eventi di Sistema</div>
            <div class="text-caption text-grey-7">Configura se l'evento deve essere Sincrono o Asincrono e su quale Coda Redis instradarlo</div>
          </div>
        </div>

        <q-table
          :rows="eventTypes"
          :columns="eventTypeColumns"
          row-key="id"
          flat
          bordered
        >
          <template v-slot:body-cell-modalita="props">
            <q-td :props="props" align="center">
              <q-select
                v-model="props.row.modalita_esecuzione"
                :options="['sincrono', 'asincrono']"
                dense
                outlined
                style="min-width: 140px"
                @update:model-value="updatePolicy(props.row)"
              />
            </q-td>
          </template>

          <template v-slot:body-cell-coda="props">
            <q-td :props="props" align="center">
              <q-select
                v-model="props.row.coda_nome"
                :options="['critical', 'emails', 'batch', 'default']"
                dense
                outlined
                style="min-width: 130px"
                @update:model-value="updatePolicy(props.row)"
              />
            </q-td>
          </template>
        </q-table>
      </q-tab-panel>

      <!-- TAB 6: METRICHE & OPS -->
      <q-tab-panel name="metrics" class="q-pa-none">
        <div class="row items-center justify-between q-mb-md">
          <div class="text-subtitle1 text-weight-bold">
            Monitoraggio Operativo & Prestazioni di Sistema
          </div>
          <div class="row q-gutter-sm">
            <q-btn
              color="secondary"
              icon="refresh"
              label="Ricarica Dati"
              outline
              :loading="loadingMetrics"
              @click="fetchMetricsSummary"
            />
            <q-btn
              color="primary"
              icon="open_in_new"
              label="Apri Grafana Dashboard ↗"
              unelevated
              @click="openGrafana"
            />
          </div>
        </div>

        <!-- 4 Card KPI Riassuntive -->
        <div class="row q-col-gutter-md q-mb-lg">
          <!-- KPI 1: Latenza Media API -->
          <div class="col-12 col-sm-6 col-md-3">
            <q-card class="bg-blue-1 text-blue-9" flat bordered>
              <q-card-section>
                <div class="row items-center justify-between no-wrap">
                  <div class="text-caption text-weight-medium">LATENZA MEDIA API</div>
                  <q-icon name="speed" size="24px" color="blue-7" />
                </div>
                <div class="text-h4 text-weight-bolder q-mt-sm">
                  {{ metricsSummary.http?.avg_latency_ms || 0 }} <span class="text-caption">ms</span>
                </div>
                <div class="text-caption text-grey-8 q-mt-xs">
                  Tempo medio di risposta endpoint
                </div>
              </q-card-section>
            </q-card>
          </div>

          <!-- KPI 2: Client WebSockets Live -->
          <div class="col-12 col-sm-6 col-md-3">
            <q-card class="bg-green-1 text-green-9" flat bordered>
              <q-card-section>
                <div class="row items-center justify-between no-wrap">
                  <div class="text-caption text-weight-medium">WEBSOCKET CONNESSI</div>
                  <q-icon name="wifi" size="24px" color="green-7" />
                </div>
                <div class="text-h4 text-weight-bolder q-mt-sm">
                  {{ metricsSummary.websockets?.active_clients || 0 }} <span class="text-caption">client</span>
                </div>
                <div class="text-caption text-grey-8 q-mt-xs">
                  {{ metricsSummary.websockets?.total_broadcasts || 0 }} notifiche broadcast totali
                </div>
              </q-card-section>
            </q-card>
          </div>

          <!-- KPI 3: Richieste & Affidabilità -->
          <div class="col-12 col-sm-6 col-md-3">
            <q-card class="bg-purple-1 text-purple-9" flat bordered>
              <q-card-section>
                <div class="row items-center justify-between no-wrap">
                  <div class="text-caption text-weight-medium">TRAFFICO & AFFIDABILITÀ</div>
                  <q-icon name="check_circle" size="24px" color="purple-7" />
                </div>
                <div class="text-h4 text-weight-bolder q-mt-sm">
                  {{ metricsSummary.http?.success_rate_pct || 100 }}%
                </div>
                <div class="text-caption text-grey-8 q-mt-xs">
                  {{ metricsSummary.http?.total_requests || 0 }} richieste elaborate
                </div>
              </q-card-section>
            </q-card>
          </div>

          <!-- KPI 4: Code Background RQ -->
          <div class="col-12 col-sm-6 col-md-3">
            <q-card class="bg-amber-1 text-amber-10" flat bordered>
              <q-card-section>
                <div class="row items-center justify-between no-wrap">
                  <div class="text-caption text-weight-medium">CODE REDIS (RQ)</div>
                  <q-icon name="queue" size="24px" color="amber-8" />
                </div>
                <div class="text-h4 text-weight-bolder q-mt-sm">
                  {{ metricsSummary.queues_rq?.total_pending || 0 }} <span class="text-caption">in coda</span>
                </div>
                <div class="text-caption text-grey-8 q-mt-xs">
                  {{ metricsSummary.queues_rq?.total_failed || 0 }} job falliti
                </div>
              </q-card-section>
            </q-card>
          </div>
        </div>

        <!-- Sezioni Dettaglio: Contatori Business e Ripartizione HTTP -->
        <div class="row q-col-gutter-md">
          <div class="col-12 col-md-6">
            <q-card flat bordered>
              <q-card-section class="bg-grey-2 text-weight-bold">
                <q-icon name="inventory_2" class="q-mr-xs" /> Volumi Operativi ERP
              </q-card-section>
              <q-separator />
              <q-card-section>
                <div class="row q-col-gutter-sm text-center">
                  <div class="col-4">
                    <div class="text-h5 text-weight-bold text-primary">{{ metricsSummary.business_totals?.orders || 0 }}</div>
                    <div class="text-caption text-grey-7">Ordini Inseriti</div>
                  </div>
                  <div class="col-4">
                    <div class="text-h5 text-weight-bold text-teal">{{ metricsSummary.business_totals?.invoices || 0 }}</div>
                    <div class="text-caption text-grey-7">Fatture Emesse</div>
                  </div>
                  <div class="col-4">
                    <div class="text-h5 text-weight-bold text-deep-orange">{{ metricsSummary.business_totals?.pos_sales || 0 }}</div>
                    <div class="text-caption text-grey-7">Vendite Cassa POS</div>
                  </div>
                </div>
              </q-card-section>
            </q-card>
          </div>

          <div class="col-12 col-md-6">
            <q-card flat bordered>
              <q-card-section class="bg-grey-2 text-weight-bold">
                <q-icon name="http" class="q-mr-xs" /> Ripartizione Esito Chiamate HTTP
              </q-card-section>
              <q-separator />
              <q-card-section>
                <div class="row q-col-gutter-sm text-center">
                  <div class="col-4">
                    <div class="text-h5 text-weight-bold text-positive">{{ metricsSummary.http?.status_2xx || 0 }}</div>
                    <div class="text-caption text-grey-7">Status 2xx (Successo)</div>
                  </div>
                  <div class="col-4">
                    <div class="text-h5 text-weight-bold text-warning">{{ metricsSummary.http?.status_4xx || 0 }}</div>
                    <div class="text-caption text-grey-7">Status 4xx (Client Error)</div>
                  </div>
                  <div class="col-4">
                    <div class="text-h5 text-weight-bold text-negative">{{ metricsSummary.http?.status_5xx || 0 }}</div>
                    <div class="text-caption text-grey-7">Status 5xx (Server Error)</div>
                  </div>
                </div>
              </q-card-section>
            </q-card>
          </div>
        </div>
      </q-tab-panel>
    </q-tab-panels>

    <!-- DIALOG DETTAGLIO EVENTO -->
    <q-dialog v-model="detailDialogOpen">
      <q-card style="min-width: 600px; max-width: 800px">
        <q-card-section class="row items-center justify-between">
          <div class="text-h6">{{ selectedEvent?.titolo }}</div>
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>
        <q-separator />

        <q-card-section class="q-gutter-sm">
          <div class="row justify-between">
            <div>Canale: <strong>{{ selectedEvent?.channel_codice }} ({{ selectedEvent?.channel_nome }})</strong></div>
            <div>Stato: <q-badge :color="getStatusColor(selectedEvent?.stato)">{{ selectedEvent?.stato?.toUpperCase() }}</q-badge></div>
          </div>
          <div v-if="selectedEvent?.destinatario_recapito">
            Destinatario: <strong>{{ selectedEvent?.destinatario_recapito }}</strong>
          </div>
          <div v-if="selectedEvent?.note_esito" class="q-pa-sm bg-grey-2 rounded-borders text-caption">
            Esito: {{ selectedEvent?.note_esito }}
          </div>
          <div class="text-subtitle2 text-weight-bold q-mt-sm">Contenuto / Descrizione</div>
          <div class="q-pa-md bg-grey-1 rounded-borders scroll" style="max-height: 250px; white-space: pre-wrap">
            {{ selectedEvent?.descrizione || 'Nessuna descrizione' }}
          </div>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Chiudi" color="grey" v-close-popup />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- DIALOG NUOVO CANALE -->
    <q-dialog v-model="newChannelDialogOpen">
      <q-card style="min-width: 500px">
        <q-card-section class="row items-center justify-between">
          <div class="text-h6">Nuovo Canale di Comunicazione</div>
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>
        <q-separator />

        <q-card-section class="q-gutter-md">
          <q-input v-model="newChannelForm.codice" label="Codice (es. TELEGRAM, SMS) *" outlined dense />
          <q-input v-model="newChannelForm.nome" label="Nome Descrittivo *" outlined dense />
          <q-select 
            v-model="newChannelForm.tipo_dispatcher" 
            :options="['internal', 'smtp', 'webhook']" 
            label="Tipo Dispatcher *" 
            outlined 
            dense 
          />
          <q-input v-model="newChannelForm.descrizione" label="Descrizione Funzionale" outlined dense />
          <q-toggle v-model="newChannelForm.richiede_destinatario" label="Richiede Indirizzo / Recapito" />
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat label="Annulla" color="grey" v-close-popup />
          <q-btn label="Salva Canale" color="primary" @click="saveChannel" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import wsService from '../services/websocket.js'

const activeTab = ref('audit')
const events = ref([])
const channels = ref([])
const loading = ref(false)
const searchTerm = ref('')
const wsConnected = wsService.isConnected
let unsubscribeWs = null

const handleWsMessage = (msg) => {
  if (msg.type === 'SYSTEM_EVENT' && msg.event) {
    const ev = msg.event
    const existingIndex = events.value.findIndex(e => e.id === ev.id)
    if (existingIndex >= 0) {
      events.value[existingIndex] = { ...events.value[existingIndex], ...ev }
    } else {
      events.value.unshift(ev)
    }
  }
}

const detailDialogOpen = ref(false)
const selectedEvent = ref(null)

const newChannelDialogOpen = ref(false)
const newChannelForm = ref({
  codice: '',
  nome: '',
  tipo_dispatcher: 'internal',
  descrizione: '',
  richiede_destinatario: false
})

const auditEvents = computed(() => events.value.filter(e => !e.is_async && e.channel_codice === 'AUDIT'))
const queueTasks = computed(() => events.value.filter(e => e.is_async))
const outboxMessages = computed(() => events.value.filter(e => e.channel_codice !== 'AUDIT'))

const auditColumns = [
  { name: 'data_creazione', label: 'Data/Ora', field: 'data_creazione', align: 'left', sortable: true },
  { name: 'categoria', label: 'Area', align: 'left' },
  { name: 'titolo', label: 'Operazione', align: 'left' },
  { name: 'utente_email', label: 'Operatore', field: 'utente_email', align: 'left' },
  { name: 'stato', label: 'Stato', align: 'center' },
  { name: 'actions', label: 'Dettaglio', align: 'right' }
]

const queueColumns = [
  { name: 'titolo', label: 'Attività a Lunga Durata', align: 'left' },
  { name: 'progresso', label: 'Avanzamento', align: 'left' },
  { name: 'stato', label: 'Stato', align: 'center' },
  { name: 'data_creazione', label: 'Inizio', field: 'data_creazione', align: 'center' },
  { name: 'actions', label: 'Azioni', align: 'right' }
]

const outboxColumns = [
  { name: 'canale', label: 'Canale', align: 'center' },
  { name: 'destinatario', label: 'Destinatario', align: 'left' },
  { name: 'titolo', label: 'Oggetto', field: 'titolo', align: 'left' },
  { name: 'data_creazione', label: 'Data', field: 'data_creazione', align: 'center' },
  { name: 'stato', label: 'Stato', align: 'center' },
  { name: 'actions', label: 'Dettaglio', align: 'right' }
]

const channelColumns = [
  { name: 'codice', label: 'Codice', field: 'codice', align: 'left', sortable: true },
  { name: 'nome', label: 'Nome Canale', field: 'nome', align: 'left' },
  { name: 'tipo_dispatcher', label: 'Tipo Dispatcher', field: 'tipo_dispatcher', align: 'center' },
  { name: 'attivo', label: 'Stato', align: 'center' }
]

const eventTypes = ref([])
const queues = ref([])

const eventTypeColumns = [
  { name: 'codice', label: 'Codice Evento', field: 'codice', align: 'left', sortable: true },
  { name: 'nome', label: 'Nome Descrittivo', field: 'nome', align: 'left' },
  { name: 'modalita', label: 'Modalità Esecuzione', align: 'center' },
  { name: 'coda', label: 'Coda Redis', align: 'center' }
]

const fetchEventTypes = async () => {
  try {
    const res = await axios.get('/api/events/types')
    eventTypes.value = res.data
  } catch (err) {
    console.error('Error fetching event types:', err)
  }
}

const fetchQueues = async () => {
  try {
    const res = await axios.get('/api/events/queues')
    queues.value = res.data.queues || []
  } catch (err) {
    console.error('Error fetching queues:', err)
  }
}

const updatePolicy = async (row) => {
  try {
    await axios.put(`/api/events/types/${row.id}`, {
      modalita_esecuzione: row.modalita_esecuzione,
      coda_nome: row.coda_nome
    })
    fetchQueues()
  } catch (err) {
    alert(err.response?.data?.error || 'Errore salvataggio policy')
  }
}

const getStatusColor = (st) => {
  if (st === 'completato') return 'positive'
  if (st === 'test') return 'teal'
  if (st === 'in_corso') return 'primary'
  if (st === 'in_coda') return 'orange'
  if (st === 'errore') return 'negative'
  return 'grey'
}

const fetchEvents = async () => {
  loading.value = true
  try {
    const params = {}
    if (searchTerm.value) params.search = searchTerm.value
    const res = await axios.get('/api/events', { params })
    events.value = res.data
  } catch (err) {
    console.error('Error fetching events:', err)
  } finally {
    loading.value = false
  }
}

const fetchChannels = async () => {
  try {
    const res = await axios.get('/api/events/channels')
    channels.value = res.data
  } catch (err) {
    console.error('Error fetching channels:', err)
  }
}

const metricsSummary = ref({
  http: { total_requests: 0, avg_latency_ms: 0, success_rate_pct: 100, status_2xx: 0, status_4xx: 0, status_5xx: 0 },
  websockets: { active_clients: 0, total_broadcasts: 0 },
  queues_rq: { critical: 0, emails: 0, reports: 0, default: 0, total_pending: 0, total_failed: 0 },
  business_totals: { orders: 0, invoices: 0, pos_sales: 0 }
})
const loadingMetrics = ref(false)

const fetchMetricsSummary = async () => {
  loadingMetrics.value = true
  try {
    const res = await axios.get('/api/metrics/summary')
    metricsSummary.value = res.data
  } catch (err) {
    console.error('Error fetching metrics summary:', err)
  } finally {
    loadingMetrics.value = false
  }
}

const openGrafana = () => {
  window.open('/grafana/d/erp9lli-ops-overview/', '_blank')
}

const fetchData = () => {
  fetchEvents()
  fetchChannels()
  fetchEventTypes()
  fetchQueues()
  fetchMetricsSummary()
}

const viewEvent = (ev) => {
  selectedEvent.value = ev
  detailDialogOpen.value = true
}

const retryTask = async (task) => {
  try {
    await axios.post(`/api/events/${task.id}/retry`)
    fetchEvents()
  } catch (err) {
    alert(err.response?.data?.error || 'Errore durante riavvio task')
  }
}

const openNewChannelDialog = () => {
  newChannelForm.value = {
    codice: '',
    nome: '',
    tipo_dispatcher: 'internal',
    descrizione: '',
    richiede_destinatario: false
  }
  newChannelDialogOpen.value = true
}

const saveChannel = async () => {
  try {
    await axios.post('/api/events/channels', newChannelForm.value)
    newChannelDialogOpen.value = false
    fetchChannels()
  } catch (err) {
    alert(err.response?.data?.error || 'Errore salvataggio canale')
  }
}

onMounted(() => {
  fetchData()
  wsService.connect()
  unsubscribeWs = wsService.subscribe(handleWsMessage)
})

onUnmounted(() => {
  if (unsubscribeWs) {
    unsubscribeWs()
  }
})
</script>
