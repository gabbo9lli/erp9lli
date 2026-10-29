<template>
  <div class="q-pa-md">
    <div class="row items-center justify-between q-mb-md">
      <div>
        <h2 class="text-h5 text-weight-bold q-my-none">Inizializzazione & Migrazione Dati Legacy</h2>
        <div class="text-caption text-grey-7">
          Acquisizione dati dal gestionale Microsoft Access (GestionaleReteBio2026.accdb). Modalità incrementale e reset completo.
        </div>
      </div>
      <div>
        <q-badge :color="wsConnected ? 'positive' : 'grey-6'" :label="wsConnected ? 'LIVE WS' : 'OFFLINE'" />
      </div>
    </div>

    <!-- Banner informativo -->
    <q-banner dense class="bg-blue-1 text-primary q-mb-md rounded-borders" rounded>
      <template v-slot:avatar>
        <q-icon name="info" color="primary" />
      </template>
      Questa procedura consente di inizializzare l'intero sistema importando anagrafiche, listini, giacenze e storico fatture/rate.
      La modalità <strong>Incrementale</strong> riconcilia automaticamente i record esistenti (zero duplicazioni).
    </q-banner>

    <div class="row q-col-gutter-md">
      <!-- Colonna Sinistra: Configurazione & Azioni -->
      <div class="col-12 col-md-6">
        <q-card flat bordered class="q-mb-md">
          <q-card-section>
            <div class="text-subtitle1 text-weight-bold q-mb-sm">1. File Sorgente da Windows & Modalità</div>
            
            <q-file
              v-model="selectedFile"
              label="Seleziona file Access da Windows (.accdb, .mdb)"
              outlined
              dense
              accept=".accdb, .mdb"
              class="q-mb-md"
              hint="Carica il database Access salvato sul tuo computer Windows"
              :loading="uploadingFile"
              @update:model-value="uploadSelectedFile"
            >
              <template v-slot:prepend>
                <q-icon name="cloud_upload" />
              </template>
              <template v-slot:append v-if="selectedFile">
                <q-icon name="close" @click.stop.prevent="clearSelectedFile" class="cursor-pointer" />
              </template>
            </q-file>

            <div v-if="uploadedFileInfo" class="q-mb-md">
              <q-banner dense class="bg-green-1 text-positive rounded-borders">
                <template v-slot:avatar>
                  <q-icon name="check_circle" color="positive" />
                </template>
                <div class="text-caption text-weight-medium">
                  File pronto: <strong>{{ uploadedFileInfo.filename }}</strong> ({{ uploadedFileInfo.file_size_mb }} MB)
                  <br />
                  <span class="text-grey-7">Caricato sul server: {{ uploadedFileInfo.file_path }}</span>
                </div>
              </q-banner>
            </div>

            <div class="text-caption text-weight-medium q-mb-xs">Tipo di Operazione:</div>
            <div class="q-gutter-sm q-mb-md">
              <q-radio v-model="migrationMode" val="incremental" label="Importazione Incrementale (Consigliata - non cancella nulla)" color="positive" />
              <q-radio v-model="migrationMode" val="reset" label="Inizializzazione da Zero (Wipe tabelle e ricaricamento completo)" color="negative" />
            </div>

            <div class="row q-gutter-sm">
              <q-btn
                color="secondary"
                icon="analytics"
                label="Analizza File (Dry Run)"
                :loading="loadingDryRun"
                :disable="!sourceFile || uploadingFile"
                @click="runDryRun"
              />
              <q-btn
                :color="migrationMode === 'reset' ? 'negative' : 'primary'"
                :icon="migrationMode === 'reset' ? 'delete_forever' : 'play_arrow'"
                :label="migrationMode === 'reset' ? 'Svuota & Inizializza' : 'Avvia Importazione'"
                :loading="loadingExecute"
                :disable="!dryRunResult || !sourceFile || uploadingFile"
                @click="onStartMigrationClicked"
              />
            </div>
          </q-card-section>
        </q-card>

        <!-- Card Anteprima Dry Run -->
        <q-card v-if="dryRunResult" flat bordered class="bg-grey-1">
          <q-card-section>
            <div class="row items-center justify-between q-mb-sm">
              <div class="text-subtitle1 text-weight-bold">2. Anteprima Dati Rilevati</div>
              <q-badge color="positive">Valido</q-badge>
            </div>
            
            <div class="row q-col-gutter-sm text-center">
              <div class="col-6 col-sm-4">
                <q-card flat bordered class="bg-white q-pa-sm">
                  <div class="text-h6 text-primary">{{ dryRunResult.partners_count }}</div>
                  <div class="text-caption text-grey-7">Clienti & Fornitori</div>
                </q-card>
              </div>
              <div class="col-6 col-sm-4">
                <q-card flat bordered class="bg-white q-pa-sm">
                  <div class="text-h6 text-primary">{{ dryRunResult.products_count }}</div>
                  <div class="text-caption text-grey-7">Articoli Biologici</div>
                </q-card>
              </div>
              <div class="col-6 col-sm-4">
                <q-card flat bordered class="bg-white q-pa-sm">
                  <div class="text-h6 text-teal">{{ dryRunResult.stock_lots_count }}</div>
                  <div class="text-caption text-grey-7">Lotti & Giacenze</div>
                </q-card>
              </div>
              <div class="col-6 col-sm-4">
                <q-card flat bordered class="bg-white q-pa-sm">
                  <div class="text-h6 text-indigo">{{ dryRunResult.invoices_count }}</div>
                  <div class="text-caption text-grey-7">Fatture Storiche</div>
                </q-card>
              </div>
              <div class="col-6 col-sm-4">
                <q-card flat bordered class="bg-white q-pa-sm">
                  <div class="text-h6 text-deep-purple">{{ dryRunResult.installments_count }}</div>
                  <div class="text-caption text-grey-7">Rate Scadenzario</div>
                </q-card>
              </div>
              <div class="col-6 col-sm-4">
                <q-card flat bordered class="bg-white q-pa-sm">
                  <div class="text-h6 text-orange-9">~{{ dryRunResult.estimated_seconds }}s</div>
                  <div class="text-caption text-grey-7">Stima Tempo</div>
                </q-card>
              </div>
            </div>
          </q-card-section>
        </q-card>
      </div>

      <!-- Colonna Destra: Avanzamento & Log Console -->
      <div class="col-12 col-md-6">
        <q-card flat bordered style="height: 100%; display: flex; flex-direction: column;">
          <q-card-section>
            <div class="row items-center justify-between q-mb-sm">
              <div class="text-subtitle1 text-weight-bold">3. Avanzamento & Monitoraggio Live</div>
              <div v-if="executionStatus" class="text-caption text-weight-bold text-primary">
                {{ executionStatus.toUpperCase() }} ({{ progressPercent }}%)
              </div>
            </div>

            <q-linear-progress
              :value="progressPercent / 100"
              color="primary"
              track-color="grey-3"
              rounded
              size="16px"
              class="q-mb-md"
            >
              <div class="absolute-full flex flex-center">
                <q-badge color="white" text-color="primary" :label="`${progressPercent}%`" />
              </div>
            </q-linear-progress>
          </q-card-section>

          <q-separator />

          <q-card-section class="col bg-black text-green-4 text-mono q-pa-sm" style="overflow-y: auto; max-height: 400px; font-family: monospace; font-size: 12px; border-radius: 0 0 4px 4px;">
            <div v-if="logs.length === 0" class="text-grey-6 text-italic">
              Nessuna operazione in corso. Clicca su 'Analizza File' per iniziare.
            </div>
            <div v-for="(log, i) in logs" :key="i" class="q-mb-xs">
              <span class="text-grey-5">[{{ log.time }}]</span> {{ log.message }}
            </div>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <!-- Dialog di Sicurezza per il Reset Completo -->
    <q-dialog v-model="resetConfirmDialogOpen" persistent>
      <q-card style="min-width: 400px;">
        <q-card-section class="bg-negative text-white row items-center">
          <q-icon name="warning" size="24px" class="q-mr-sm" />
          <div class="text-h6">ATTENZIONE: Reset Integrale Database</div>
        </q-card-section>

        <q-card-section class="q-pt-md">
          <p class="text-body2">
            Stai per svuotare completamente tutte le tabelle transazionali e di anagrafica di <strong>erp9lli</strong>
            (Ordini, DDT, Magazzino, Fatture, Contabilità, Partner e Prodotti).
          </p>
          <p class="text-caption text-weight-bold text-negative">
            L'account amministratore di sistema NON verrà cancellato. Per confermare, digita esattamente:
            <code>RESET_ERP9LLI</code>
          </p>
          <q-input
            v-model="resetConfirmationInput"
            outlined
            dense
            placeholder="RESET_ERP9LLI"
            class="q-mt-sm"
          />
        </q-card-section>

        <q-card-actions align="right" class="bg-grey-1">
          <q-btn flat label="Annulla" color="grey-7" v-close-popup />
          <q-btn
            label="Conferma & Svuota"
            color="negative"
            :disable="resetConfirmationInput !== 'RESET_ERP9LLI'"
            @click="executeResetAndMigrate"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import wsService from '../services/websocket.js'

const selectedFile = ref(null)
const uploadingFile = ref(false)
const uploadedFileInfo = ref(null)
const sourceFile = ref('')
const migrationMode = ref('incremental')
const loadingDryRun = ref(false)
const loadingExecute = ref(false)
const dryRunResult = ref(null)
const executionStatus = ref(null)
const progressPercent = ref(0)
const logs = ref([])
const wsConnected = wsService.isConnected

const resetConfirmDialogOpen = ref(false)
const resetConfirmationInput = ref('')
let unsubWs = null

const addLog = (msg) => {
  const time = new Date().toLocaleTimeString()
  logs.value.push({ time, message: msg })
}

const uploadSelectedFile = async (file) => {
  if (!file) return
  uploadingFile.value = true
  addLog(`Caricamento file ${file.name} dal computer Windows in corso...`)
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await axios.post('/api/migration/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    uploadedFileInfo.value = res.data
    sourceFile.value = res.data.file_path
    dryRunResult.value = null
    addLog(`Caricato sul server con successo: ${res.data.filename} (${res.data.file_size_mb} MB).`)
  } catch (err) {
    addLog(`ERRORE durante l'upload del file: ${err.response?.data?.detail || err.message}`)
    alert(err.response?.data?.detail || 'Errore durante il caricamento del file da Windows')
    selectedFile.value = null
    sourceFile.value = ''
    uploadedFileInfo.value = null
  } finally {
    uploadingFile.value = false
  }
}

const clearSelectedFile = () => {
  selectedFile.value = null
  sourceFile.value = ''
  uploadedFileInfo.value = null
  dryRunResult.value = null
  addLog('File rimosso. Selezionare un nuovo file per continuare.')
}

const runDryRun = async () => {
  if (!sourceFile.value) {
    alert('Seleziona prima un file da caricare dal tuo computer Windows.')
    return
  }
  loadingDryRun.value = true
  addLog(`Avvio analisi e dry-run del file: ${sourceFile.value}`)
  try {
    const res = await axios.post('/api/migration/dry-run', { source_file: sourceFile.value })
    dryRunResult.value = res.data
    addLog(`Analisi completata con successo! Trovati ${res.data.partners_count} soggetti, ${res.data.products_count} articoli, ${res.data.stock_lots_count} lotti.`)
  } catch (err) {
    addLog(`ERRORE nell'analisi: ${err.response?.data?.error || err.message}`)
    alert(err.response?.data?.error || 'Errore durante la scansione del file Access')
  } finally {
    loadingDryRun.value = false
  }
}

const onStartMigrationClicked = () => {
  if (migrationMode.value === 'reset') {
    resetConfirmationInput.value = ''
    resetConfirmDialogOpen.value = true
  } else {
    executeMigration()
  }
}

const executeResetAndMigrate = async () => {
  resetConfirmDialogOpen.value = false
  loadingExecute.value = true
  addLog('Esecuzione RESET atomico del database operativo in corso...')
  try {
    await axios.post('/api/migration/reset', { confirm_wipe: 'RESET_ERP9LLI' })
    addLog('Database azzerato con successo! Avvio importazione pulita da zero...')
    await executeMigration()
  } catch (err) {
    addLog(`ERRORE durante il reset: ${err.response?.data?.detail || err.message}`)
    alert(err.response?.data?.detail || 'Errore durante il reset del database')
    loadingExecute.value = false
  }
}

const executeMigration = async () => {
  loadingExecute.value = true
  executionStatus.value = 'in_corso'
  progressPercent.value = 10
  addLog(`Avvio caricamento dati in modalità [${migrationMode.value.toUpperCase()}]...`)

  try {
    const res = await axios.post('/api/migration/execute', {
      source_file: sourceFile.value,
      is_async: false
    })
    const d = res.data
    progressPercent.value = 100
    executionStatus.value = 'completato'
    addLog(`MIGRAZIONE COMPLETATA! Inseriti/Aggiornati: ${d.migrated_partners} partner, ${d.migrated_products} articoli, ${d.migrated_stock_lots} carichi lotto, ${d.migrated_invoices} fatture.`)
  } catch (err) {
    executionStatus.value = 'errore'
    addLog(`ERRORE durante l'importazione: ${err.response?.data?.detail || err.message}`)
    alert(err.response?.data?.detail || 'Errore durante la migrazione')
  } finally {
    loadingExecute.value = false
  }
}

const handleWsMessage = (msg) => {
  if (msg.type === 'SYSTEM_EVENT' && msg.event?.azione === 'migrazione_legacy') {
    const ev = msg.event
    progressPercent.value = ev.progresso || 0
    executionStatus.value = ev.stato
    if (ev.descrizione) {
      addLog(ev.descrizione)
    }
  }
}

onMounted(() => {
  wsService.connect()
  unsubWs = wsService.subscribe(handleWsMessage)
})

onUnmounted(() => {
  if (unsubWs) unsubWs()
})
</script>

<style scoped>
.text-mono {
  font-family: 'Courier New', Courier, monospace;
}
</style>
