<template>
  <div class="q-pa-md">
    <div class="row items-center justify-between q-mb-md">
      <div>
        <h2 class="text-h5 text-weight-bold q-my-none">Contabilità Generale & Partita Doppia</h2>
        <div class="text-caption text-grey-7">Prima Nota, Libro Giornale, Schede Mastro e Bilancio di Verifica (export CSV)</div>
      </div>
      <div class="q-gutter-sm">
        <q-btn 
          color="primary" 
          icon="add" 
          label="Nuova Registrazione" 
          @click="openNewEntryDialog()"
        />
      </div>
    </div>

    <!-- Schede Contabili -->
    <q-tabs v-model="activeTab" dense class="text-grey" active-color="primary" indicator-color="primary" align="left">
      <q-tab name="entries" label="Prima Nota" icon="menu_book" />
      <q-tab name="giornale" label="Libro Giornale" icon="history_edu" />
      <q-tab name="mastro" label="Schede Mastro" icon="account_balance_wallet" />
      <q-tab name="bilancio" label="Bilancio di Verifica" icon="balance" />
      <q-tab name="conti" label="Piano dei Conti" icon="list_alt" />
    </q-tabs>

    <q-separator class="q-mb-md" />

    <q-tab-panels v-model="activeTab" animated>
      <!-- TAB 1: PRIMA NOTA -->
      <q-tab-panel name="entries" class="q-pa-none">
        <div class="row q-gutter-sm items-center q-mb-md">
          <q-input 
            v-model="searchTerm" 
            dense 
            outlined 
            placeholder="Cerca causale scrittura..." 
            @update:model-value="fetchEntries"
            style="min-width: 300px"
          >
            <template v-slot:append>
              <q-icon name="search" />
            </template>
          </q-input>
        </div>

        <q-table
          :rows="entries"
          :columns="entryColumns"
          row-key="id"
          :loading="loading"
          flat
          bordered
        >
          <template v-slot:body-cell-numero_completo="props">
            <q-td :props="props">
              <span class="text-weight-bold text-primary">{{ props.row.numero_completo }}</span>
            </q-td>
          </template>

          <template v-slot:body-cell-totali="props">
            <q-td :props="props" align="right">
              <span class="text-weight-bold">€ {{ Number(props.row.totale_dare).toFixed(2) }}</span>
            </q-td>
          </template>

          <template v-slot:body-cell-stato="props">
            <q-td :props="props" align="center">
              <q-chip color="positive" text-color="white" dense size="sm">
                {{ props.row.stato.toUpperCase() }}
              </q-chip>
            </q-td>
          </template>

          <template v-slot:body-cell-actions="props">
            <q-td :props="props" align="right">
              <q-btn flat round dense color="primary" icon="visibility" @click="viewEntry(props.row)" />
            </q-td>
          </template>
        </q-table>
      </q-tab-panel>

      <!-- TAB 2: LIBRO GIORNALE -->
      <q-tab-panel name="giornale" class="q-pa-none">
        <div class="row justify-between items-center q-mb-md">
          <div class="row items-center q-gutter-md">
            <div class="text-subtitle1 text-weight-bold">Registro Cronologico Scritture</div>
            <q-chip color="positive" text-color="white" dense>
              Totale Pareggio: € {{ Number(giornaleReport.totale_dare || 0).toFixed(2) }}
            </q-chip>
          </div>
          <q-btn 
            color="secondary" 
            icon="download" 
            label="Esporta CSV Libro Giornale" 
            @click="exportCsv('/api/accounting/reports/libro-giornale?format=csv', 'libro_giornale.csv')" 
          />
        </div>

        <q-table
          :rows="giornaleReport.righe || []"
          :columns="giornaleColumns"
          row-key="entry_id"
          flat
          bordered
        >
          <template v-slot:body-cell-dare="props">
            <q-td :props="props" align="right">
              <span v-if="props.row.dare > 0" class="text-weight-medium">€ {{ Number(props.row.dare).toFixed(2) }}</span>
              <span v-else class="text-grey-4">-</span>
            </q-td>
          </template>
          <template v-slot:body-cell-avere="props">
            <q-td :props="props" align="right">
              <span v-if="props.row.avere > 0" class="text-weight-medium">€ {{ Number(props.row.avere).toFixed(2) }}</span>
              <span v-else class="text-grey-4">-</span>
            </q-td>
          </template>
        </q-table>
      </q-tab-panel>

      <!-- TAB 3: SCHEDE MASTRO -->
      <q-tab-panel name="mastro" class="q-pa-none">
        <div class="row justify-between items-center q-mb-md">
          <div class="row items-center q-gutter-sm" style="min-width: 400px">
            <q-select
              v-model="selectedMastroAccountId"
              :options="accounts"
              option-label="nome"
              option-value="id"
              emit-value
              map-options
              label="Seleziona Conto di Mastro *"
              outlined
              dense
              style="min-width: 350px"
              @update:model-value="fetchMastro"
            >
              <template v-slot:option="scope">
                <q-item v-bind="scope.itemProps">
                  <q-item-section>
                    <q-item-label>{{ scope.opt.codice }} - {{ scope.opt.nome }}</q-item-label>
                    <q-item-label caption>{{ scope.opt.tipo.toUpperCase() }}</q-item-label>
                  </q-item-section>
                </q-item>
              </template>
            </q-select>
          </div>
          <q-btn 
            v-if="selectedMastroAccountId"
            color="secondary" 
            icon="download" 
            label="Esporta CSV Mastro" 
            @click="exportCsv(`/api/accounting/reports/mastro?account_id=${selectedMastroAccountId}&format=csv`, `mastro_${selectedMastroAccountId}.csv`)" 
          />
        </div>

        <div v-if="mastroReport.conto" class="q-pa-sm bg-blue-1 rounded-borders row justify-between items-center q-mb-md">
          <div>
            Conto: <strong>{{ mastroReport.conto.codice }} - {{ mastroReport.conto.nome }}</strong> ({{ mastroReport.conto.tipo.toUpperCase() }})
          </div>
          <div class="text-subtitle1 text-primary text-weight-bolder">
            Saldo Progressivo Attuale: € {{ Number(mastroReport.saldo_finale).toFixed(2) }}
          </div>
        </div>

        <q-table
          :rows="mastroReport.movimenti || []"
          :columns="mastroColumns"
          row-key="id"
          flat
          bordered
        >
          <template v-slot:body-cell-dare="props">
            <q-td :props="props" align="right">
              <span v-if="props.row.dare > 0">€ {{ Number(props.row.dare).toFixed(2) }}</span>
              <span v-else class="text-grey-4">-</span>
            </q-td>
          </template>
          <template v-slot:body-cell-avere="props">
            <q-td :props="props" align="right">
              <span v-if="props.row.avere > 0">€ {{ Number(props.row.avere).toFixed(2) }}</span>
              <span v-else class="text-grey-4">-</span>
            </q-td>
          </template>
          <template v-slot:body-cell-saldo_progressivo="props">
            <q-td :props="props" align="right">
              <span class="text-weight-bold">€ {{ Number(props.row.saldo_progressivo).toFixed(2) }}</span>
            </q-td>
          </template>
        </q-table>
      </q-tab-panel>

      <!-- TAB 4: BILANCIO DI VERIFICA -->
      <q-tab-panel name="bilancio" class="q-pa-none">
        <div class="row justify-between items-center q-mb-md">
          <div class="text-subtitle1 text-weight-bold">Prospetto Generale Conti (Trial Balance)</div>
          <q-btn 
            color="secondary" 
            icon="download" 
            label="Esporta CSV Bilancio" 
            @click="exportCsv('/api/accounting/reports/bilancio-verifica?format=csv', 'bilancio_verifica.csv')" 
          />
        </div>

        <q-table
          :rows="bilancioReport.conti || []"
          :columns="bilancioColumns"
          row-key="account_id"
          flat
          bordered
        >
          <template v-slot:body-cell-tipo="props">
            <q-td :props="props" align="center">
              <q-badge color="grey-3" text-color="grey-9">{{ props.row.tipo.toUpperCase() }}</q-badge>
            </q-td>
          </template>
          <template v-slot:body-cell-totale_dare="props">
            <q-td :props="props" align="right">
              € {{ Number(props.row.totale_dare).toFixed(2) }}
            </q-td>
          </template>
          <template v-slot:body-cell-totale_avere="props">
            <q-td :props="props" align="right">
              € {{ Number(props.row.totale_avere).toFixed(2) }}
            </q-td>
          </template>
          <template v-slot:body-cell-saldo_netto="props">
            <q-td :props="props" align="right">
              <span class="text-weight-bold">€ {{ Number(props.row.saldo_netto).toFixed(2) }}</span>
            </q-td>
          </template>
        </q-table>

        <div class="q-pa-md bg-grey-2 rounded-borders row justify-between items-center q-mt-md">
          <div class="text-subtitle2">Quadratura Totale Movimenti:</div>
          <div class="row q-gutter-lg">
            <div>Totale Dare: <strong>€ {{ Number(bilancioReport.totale_dare || 0).toFixed(2) }}</strong></div>
            <div>Totale Avere: <strong>€ {{ Number(bilancioReport.totale_avere || 0).toFixed(2) }}</strong></div>
            <div>
              <q-badge :color="bilancioReport.quadratura ? 'positive' : 'negative'">
                {{ bilancioReport.quadratura ? 'BILANCIO QUADRATO A PAREGGIO' : 'SBILANCIO RILEVATO' }}
              </q-badge>
            </div>
          </div>
        </div>
      </q-tab-panel>

      <!-- TAB 5: PIANO DEI CONTI -->
      <q-tab-panel name="conti" class="q-pa-none">
        <q-table
          :rows="accounts"
          :columns="accountColumns"
          row-key="id"
          flat
          bordered
        >
          <template v-slot:body-cell-tipo="props">
            <q-td :props="props" align="center">
              <q-chip dense size="sm" :color="getTipoColor(props.row.tipo)" text-color="white">
                {{ props.row.tipo.toUpperCase() }}
              </q-chip>
            </q-td>
          </template>
        </q-table>
      </q-tab-panel>
    </q-tab-panels>

    <!-- DIALOG NUOVA REGISTRAZIONE PRIMA NOTA A PAREGGIO -->
    <q-dialog v-model="newEntryDialogOpen" persistent full-width>
      <q-card style="max-width: 950px; margin: auto">
        <q-card-section class="row items-center justify-between">
          <div class="text-h6">Nuova Scrittura di Prima Nota (Partita Doppia)</div>
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>
        <q-separator />

        <q-card-section class="q-gutter-md">
          <div class="row q-col-gutter-sm">
            <div class="col-12 col-md-3">
              <q-input v-model="formEntry.data_registrazione" type="date" label="Data Registrazione *" outlined dense />
            </div>
            <div class="col-12 col-md-3">
              <q-input v-model="formEntry.data_competenza" type="date" label="Data Competenza *" outlined dense />
            </div>
            <div class="col-12 col-md-6">
              <q-input v-model="formEntry.causale" label="Causale Operazione *" outlined dense placeholder="Es. Pagamento fattura, Giroconto..." />
            </div>
          </div>

          <!-- Righe Contabili Dare / Avere -->
          <div class="q-mt-md">
            <div class="row justify-between items-center q-mb-sm">
              <div class="text-subtitle2 text-weight-bold">Righe Scrittura Contabile</div>
              <q-btn color="secondary" icon="add" label="Aggiungi Riga" size="sm" @click="addEntryRow()" />
            </div>

            <div v-for="(row, idx) in formEntry.items" :key="idx" class="row q-col-gutter-xs items-center q-mb-xs">
              <div class="col-12 col-md-4">
                <q-select
                  v-model="row.account_id"
                  :options="accounts"
                  option-label="nome"
                  option-value="id"
                  emit-value
                  map-options
                  label="Conto *"
                  outlined
                  dense
                >
                  <template v-slot:option="scope">
                    <q-item v-bind="scope.itemProps">
                      <q-item-section>
                        <q-item-label>{{ scope.opt.codice }} - {{ scope.opt.nome }}</q-item-label>
                      </q-item-section>
                    </q-item>
                  </template>
                </q-select>
              </div>
              <div class="col-12 col-md-3">
                <q-select
                  v-model="row.partner_id"
                  :options="partners"
                  option-label="ragione_sociale"
                  option-value="id"
                  emit-value
                  map-options
                  label="Partner (opzionale)"
                  outlined
                  dense
                  clearable
                />
              </div>
              <div class="col-5 col-md-2">
                <q-input v-model.number="row.dare" type="number" step="0.01" label="Dare (€)" outlined dense />
              </div>
              <div class="col-5 col-md-2">
                <q-input v-model.number="row.avere" type="number" step="0.01" label="Avere (€)" outlined dense />
              </div>
              <div class="col-2 col-md-1 text-center">
                <q-btn flat round dense color="negative" icon="delete" @click="removeEntryRow(idx)" :disabled="formEntry.items.length <= 2" />
              </div>
            </div>
          </div>

          <!-- BOX CONTROLLO BILANCIAMENTO REAL-TIME -->
          <div class="q-pa-md rounded-borders row justify-between items-center q-mt-md" :class="isBalanced ? 'bg-green-1' : 'bg-red-1'">
            <div>
              Totale Dare: <strong>€ {{ sumDare.toFixed(2) }}</strong> | Totale Avere: <strong>€ {{ sumAvere.toFixed(2) }}</strong>
            </div>
            <div>
              <q-badge :color="isBalanced ? 'positive' : 'negative'" class="q-pa-xs">
                {{ isBalanced ? 'SCRITTURA BILANCIATA (PAREGGIO PERFETTO)' : `SBILANCIO: € ${Math.abs(sumDare - sumAvere).toFixed(2)}` }}
              </q-badge>
            </div>
          </div>
        </q-card-section>

        <q-card-actions align="right" class="q-pa-md">
          <q-btn flat label="Annulla" color="grey" v-close-popup />
          <q-btn 
            label="Salva Registrazione" 
            color="primary" 
            icon="save" 
            :disabled="!isBalanced || !formEntry.causale"
            :loading="savingEntry"
            @click="saveEntry"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- DIALOG DETTAGLIO REGISTRAZIONE -->
    <q-dialog v-model="detailDialogOpen">
      <q-card style="min-width: 600px">
        <q-card-section class="row items-center justify-between">
          <div>
            <div class="text-h6">{{ selectedEntry?.numero_completo }}</div>
            <div class="text-caption">{{ selectedEntry?.causale }} - Data: {{ selectedEntry?.data_registrazione }}</div>
          </div>
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>
        <q-separator />
        <q-card-section>
          <div v-for="it in selectedEntry?.items" :key="it.id" class="row justify-between items-center q-pa-sm bg-grey-1 rounded-borders q-mb-xs">
            <div>
              <strong>{{ it.account_codice }} - {{ it.account_nome }}</strong>
              <div v-if="it.partner_nome" class="text-caption text-grey-7">{{ it.partner_nome }}</div>
            </div>
            <div class="text-right">
              <span v-if="it.dare > 0" class="text-positive text-weight-bold">DARE: € {{ Number(it.dare).toFixed(2) }}</span>
              <span v-if="it.avere > 0" class="text-primary text-weight-bold">AVERE: € {{ Number(it.avere).toFixed(2) }}</span>
            </div>
          </div>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Chiudi" color="grey" v-close-popup />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const activeTab = ref('entries')
const entries = ref([])
const accounts = ref([])
const partners = ref([])
const giornaleReport = ref({})
const mastroReport = ref({})
const bilancioReport = ref({})
const selectedMastroAccountId = ref(null)

const loading = ref(false)
const savingEntry = ref(false)
const newEntryDialogOpen = ref(false)
const detailDialogOpen = ref(false)
const selectedEntry = ref(null)
const searchTerm = ref('')

const formEntry = ref({
  data_registrazione: new Date().toISOString().split('T')[0],
  data_competenza: new Date().toISOString().split('T')[0],
  causale: '',
  items: [
    { account_id: null, partner_id: null, dare: 0.0, avere: 0.0 },
    { account_id: null, partner_id: null, dare: 0.0, avere: 0.0 }
  ]
})

const entryColumns = [
  { name: 'numero_completo', label: 'Numero Scrittura', field: 'numero_completo', align: 'left', sortable: true },
  { name: 'data_registrazione', label: 'Data', field: 'data_registrazione', align: 'center', sortable: true },
  { name: 'causale', label: 'Causale', field: 'causale', align: 'left' },
  { name: 'totali', label: 'Totale Dare/Avere', field: 'totale_dare', align: 'right' },
  { name: 'stato', label: 'Stato', field: 'stato', align: 'center' },
  { name: 'actions', label: 'Dettaglio', align: 'right' }
]

const giornaleColumns = [
  { name: 'data', label: 'Data', field: 'data', align: 'center', sortable: true },
  { name: 'numero', label: 'Numero PN', field: 'numero', align: 'left' },
  { name: 'causale', label: 'Causale', field: 'causale', align: 'left' },
  { name: 'account_nome', label: 'Conto Imputato', field: row => `${row.account_codice} - ${row.account_nome}`, align: 'left' },
  { name: 'partner_nome', label: 'Partner', field: 'partner_nome', align: 'left' },
  { name: 'dare', label: 'Dare (€)', field: 'dare', align: 'right' },
  { name: 'avere', label: 'Avere (€)', field: 'avere', align: 'right' }
]

const mastroColumns = [
  { name: 'data', label: 'Data', field: 'data', align: 'center' },
  { name: 'numero', label: 'Numero PN', field: 'numero', align: 'left' },
  { name: 'causale', label: 'Causale', field: 'causale', align: 'left' },
  { name: 'partner_nome', label: 'Partner', field: 'partner_nome', align: 'left' },
  { name: 'dare', label: 'Dare (€)', field: 'dare', align: 'right' },
  { name: 'avere', label: 'Avere (€)', field: 'avere', align: 'right' },
  { name: 'saldo_progressivo', label: 'Saldo Progressivo (€)', field: 'saldo_progressivo', align: 'right' }
]

const bilancioColumns = [
  { name: 'codice', label: 'Codice', field: 'codice', align: 'left', sortable: true },
  { name: 'nome', label: 'Denominazione Conto', field: 'nome', align: 'left', sortable: true },
  { name: 'tipo', label: 'Mastro', field: 'tipo', align: 'center', sortable: true },
  { name: 'totale_dare', label: 'Totale Dare (€)', field: 'totale_dare', align: 'right' },
  { name: 'totale_avere', label: 'Totale Avere (€)', field: 'totale_avere', align: 'right' },
  { name: 'saldo_netto', label: 'Saldo Netto (€)', field: 'saldo_netto', align: 'right', sortable: true }
]

const accountColumns = [
  { name: 'codice', label: 'Codice Conto', field: 'codice', align: 'left', sortable: true },
  { name: 'nome', label: 'Descrizione', field: 'nome', align: 'left', sortable: true },
  { name: 'tipo', label: 'Tipologia CEE', field: 'tipo', align: 'center', sortable: true }
]

const sumDare = computed(() => formEntry.value.items.reduce((s, it) => s + (Number(it.dare) || 0), 0))
const sumAvere = computed(() => formEntry.value.items.reduce((s, it) => s + (Number(it.avere) || 0), 0))
const isBalanced = computed(() => {
  return sumDare.value > 0 && Math.abs(sumDare.value - sumAvere.value) < 0.001
})

const getTipoColor = (tipo) => {
  if (tipo === 'attivo') return 'primary'
  if (tipo === 'passivo') return 'purple'
  if (tipo === 'costi') return 'orange'
  return 'positive'
}

const fetchEntries = async () => {
  loading.value = true
  try {
    const params = {}
    if (searchTerm.value) params.search = searchTerm.value
    const res = await axios.get('/api/accounting/entries', { params })
    entries.value = res.data
  } catch (err) {
    console.error('Error fetching entries:', err)
  } finally {
    loading.value = false
  }
}

const fetchAccounts = async () => {
  try {
    const res = await axios.get('/api/accounting/accounts')
    accounts.value = res.data
    if (accounts.value.length && !selectedMastroAccountId.value) {
      selectedMastroAccountId.value = accounts.value[0].id
      fetchMastro()
    }
  } catch (err) {
    console.error('Error fetching accounts:', err)
  }
}

const fetchPartners = async () => {
  try {
    const res = await axios.get('/api/partners')
    partners.value = res.data
  } catch (err) {
    console.error('Error fetching partners:', err)
  }
}

const fetchGiornale = async () => {
  try {
    const res = await axios.get('/api/accounting/reports/libro-giornale')
    giornaleReport.value = res.data
  } catch (err) {
    console.error('Error fetching libro giornale:', err)
  }
}

const fetchMastro = async () => {
  if (!selectedMastroAccountId.value) return
  try {
    const res = await axios.get(`/api/accounting/reports/mastro?account_id=${selectedMastroAccountId.value}`)
    mastroReport.value = res.data
  } catch (err) {
    console.error('Error fetching mastro:', err)
  }
}

const fetchBilancio = async () => {
  try {
    const res = await axios.get('/api/accounting/reports/bilancio-verifica')
    bilancioReport.value = res.data
  } catch (err) {
    console.error('Error fetching bilancio:', err)
  }
}

const exportCsv = (url, filename) => {
  window.open(url, '_blank')
}

const openNewEntryDialog = () => {
  formEntry.value = {
    data_registrazione: new Date().toISOString().split('T')[0],
    data_competenza: new Date().toISOString().split('T')[0],
    causale: '',
    items: [
      { account_id: null, partner_id: null, dare: 0.0, avere: 0.0 },
      { account_id: null, partner_id: null, dare: 0.0, avere: 0.0 }
    ]
  }
  newEntryDialogOpen.value = true
}

const addEntryRow = () => {
  formEntry.value.items.push({ account_id: null, partner_id: null, dare: 0.0, avere: 0.0 })
}

const removeEntryRow = (idx) => {
  formEntry.value.items.splice(idx, 1)
}

const saveEntry = async () => {
  if (!isBalanced.value) return
  savingEntry.value = true
  try {
    await axios.post('/api/accounting/entries', formEntry.value)
    newEntryDialogOpen.value = false
    await fetchEntries()
    await fetchGiornale()
    await fetchMastro()
    await fetchBilancio()
  } catch (err) {
    alert(err.response?.data?.error || 'Errore salvataggio scrittura contabile')
  } finally {
    savingEntry.value = false
  }
}

const viewEntry = (entry) => {
  selectedEntry.value = entry
  detailDialogOpen.value = true
}

onMounted(() => {
  fetchEntries()
  fetchAccounts()
  fetchPartners()
  fetchGiornale()
  fetchBilancio()
})
</script>
