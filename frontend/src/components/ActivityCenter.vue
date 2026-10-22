<template>
  <div class="q-pa-md">
    <div class="row items-center justify-between q-mb-md">
      <div>
        <h2 class="text-h5 text-weight-bold q-my-none">Centro Attività, Code & Comunicazioni</h2>
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
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const activeTab = ref('audit')
const events = ref([])
const channels = ref([])
const loading = ref(false)
const searchTerm = ref('')

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

const fetchData = () => {
  fetchEvents()
  fetchChannels()
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
})
</script>
