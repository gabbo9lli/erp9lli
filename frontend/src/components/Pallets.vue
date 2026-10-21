<template>
  <div class="q-pa-md">
    <div class="row items-center justify-between q-mb-md">
      <div>
        <h2 class="text-h5 text-weight-bold q-my-none">Interscambio Pallet & Buoni Pallet (L. 182/2025)</h2>
        <div class="text-caption text-grey-7">Titoli di credito imballaggi, partitario Dare/Avere e fatturazione mancata resa in Reverse Charge</div>
      </div>
      <div>
        <q-btn 
          color="primary" 
          icon="add" 
          label="Nuovo Buono Pallet" 
          @click="openNewReceiptDialog()"
        />
      </div>
    </div>

    <!-- Schede di Navigazione -->
    <q-tabs v-model="activeTab" dense class="text-grey" active-color="primary" indicator-color="primary" align="left">
      <q-tab name="receipts" label="Buoni Pallet (BP)" icon="confirmation_number" />
      <q-tab name="ledger" label="Partitario Saldi" icon="account_balance_wallet" />
      <q-tab name="types" label="Tipologie Pallet" icon="category" />
    </q-tabs>

    <q-separator class="q-mb-md" />

    <q-tab-panels v-model="activeTab" animated>
      <!-- TAB 1: BUONI PALLET -->
      <q-tab-panel name="receipts" class="q-pa-none">
        <div class="row q-gutter-sm items-center q-mb-md">
          <q-btn-toggle
            v-model="receiptsFilter"
            toggle-color="primary"
            :options="[
              { label: 'Tutti', value: 'tutti' },
              { label: 'Aperti', value: 'aperto' },
              { label: 'Saldati', value: 'saldato' },
              { label: 'Fatturati', value: 'fatturato' }
            ]"
            @update:model-value="fetchReceipts"
          />
          <q-space />
          <q-input 
            v-model="searchTerm" 
            dense 
            outlined 
            placeholder="Cerca numero o partner..." 
            @update:model-value="fetchReceipts"
            style="min-width: 280px"
          >
            <template v-slot:append>
              <q-icon name="search" />
            </template>
          </q-input>
        </div>

        <q-table
          :rows="receipts"
          :columns="receiptColumns"
          row-key="id"
          :loading="loadingReceipts"
          flat
          bordered
        >
          <template v-slot:body-cell-numero_completo="props">
            <q-td :props="props">
              <span class="text-weight-bold text-primary">{{ props.row.numero_completo }}</span>
              <div v-if="props.row.delivery_note_numero" class="text-caption text-grey-7">DDT: {{ props.row.delivery_note_numero }}</div>
            </q-td>
          </template>

          <template v-slot:body-cell-partner="props">
            <q-td :props="props">
              <span class="text-weight-medium">{{ props.row.partner ? props.row.partner.ragione_sociale : '-' }}</span>
              <div class="text-caption text-grey-7">{{ props.row.partner?.tipo?.toUpperCase() }}</div>
            </q-td>
          </template>

          <template v-slot:body-cell-scadenza="props">
            <q-td :props="props">
              <div>{{ props.row.data_limite_restituzione }}</div>
              <q-badge v-if="props.row.stato === 'aperto'" :color="props.row.scaduto ? 'negative' : 'warning'" :text-color="props.row.scaduto ? 'white' : 'black'">
                {{ props.row.scaduto ? 'TERMINE SCADUTO' : `${props.row.giorni_rimanenti} gg rimasti` }}
              </q-badge>
            </q-td>
          </template>

          <template v-slot:body-cell-saldo_netto="props">
            <q-td :props="props" align="right">
              <span class="text-weight-bold text-subtitle2" :class="props.row.saldo_netto > 0 ? 'text-negative' : 'text-positive'">
                {{ props.row.saldo_netto }} pz
              </span>
              <div class="text-caption text-grey-7">{{ props.row.totale_consegnati }} ceduti / {{ props.row.totale_restituiti }} resi</div>
            </q-td>
          </template>

          <template v-slot:body-cell-stato="props">
            <q-td :props="props" align="center">
              <q-chip :color="getStatusColor(props.row.stato)" text-color="white" dense size="sm">
                {{ props.row.stato.toUpperCase() }}
              </q-chip>
            </q-td>
          </template>

          <template v-slot:body-cell-actions="props">
            <q-td :props="props" align="right" class="q-gutter-xs">
              <q-btn flat round dense color="primary" icon="visibility" @click="viewReceipt(props.row)">
                <q-tooltip>Dettaglio Righe</q-tooltip>
              </q-btn>
              <q-btn 
                v-if="props.row.stato === 'aperto'" 
                color="secondary" 
                icon="keyboard_return" 
                label="Reso" 
                dense 
                size="sm"
                @click="openReturnDialog(props.row)"
              >
                <q-tooltip>Registra restituzione pallet</q-tooltip>
              </q-btn>
              <q-btn 
                v-if="props.row.stato === 'aperto'" 
                color="negative" 
                icon="receipt" 
                label="Fattura Mancata Resa" 
                dense 
                size="sm"
                @click="invoiceUnreturned(props.row)"
              >
                <q-tooltip>Fattura in Reverse Charge</q-tooltip>
              </q-btn>
            </q-td>
          </template>
        </q-table>
      </q-tab-panel>

      <!-- TAB 2: PARTITARIO SALDI -->
      <q-tab-panel name="ledger" class="q-pa-none">
        <q-table
          :rows="ledger"
          :columns="ledgerColumns"
          row-key="partner_id"
          :loading="loadingLedger"
          flat
          bordered
        >
          <template v-slot:body-cell-totale_bancali_debito="props">
            <q-td :props="props" align="right">
              <span class="text-weight-bold text-subtitle2 text-negative">
                {{ props.row.totale_bancali_debito }} pz
              </span>
            </q-td>
          </template>

          <template v-slot:body-cell-saldi_dettaglio="props">
            <q-td :props="props">
              <div class="row q-gutter-xs">
                <q-badge v-for="(val, code) in props.row.saldi" :key="code" color="grey-3" text-color="grey-9">
                  {{ code }}: <strong>{{ val }}</strong>
                </q-badge>
              </div>
            </q-td>
          </template>

          <template v-slot:body-cell-buoni_scaduti="props">
            <q-td :props="props" align="center">
              <q-badge :color="props.row.buoni_scaduti_count > 0 ? 'negative' : 'positive'">
                {{ props.row.buoni_scaduti_count }} scaduti (su {{ props.row.buoni_aperti_count }} aperti)
              </q-badge>
            </q-td>
          </template>
        </q-table>
      </q-tab-panel>

      <!-- TAB 3: TIPOLOGIE PALLET -->
      <q-tab-panel name="types" class="q-pa-none">
        <q-table
          :rows="palletTypes"
          :columns="typeColumns"
          row-key="id"
          flat
          bordered
        >
          <template v-slot:body-cell-valore="props">
            <q-td :props="props" align="right">
              <span class="text-weight-bold">€ {{ Number(props.row.valore_risarcimento).toFixed(2) }}</span>
            </q-td>
          </template>
        </q-table>
      </q-tab-panel>
    </q-tab-panels>

    <!-- DIALOG NUOVO BUONO PALLET -->
    <q-dialog v-model="newReceiptDialogOpen" persistent full-width>
      <q-card style="max-width: 900px; margin: auto">
        <q-card-section class="row items-center justify-between">
          <div class="text-h6">Emissione Buono Pallet (Legge 182/2025)</div>
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>
        <q-separator />

        <q-card-section class="q-gutter-md">
          <div class="row q-col-gutter-sm">
            <div class="col-12 col-md-6">
              <q-select
                v-model="formReceipt.partner_id"
                :options="partners"
                option-label="ragione_sociale"
                option-value="id"
                emit-value
                map-options
                label="Cliente o Vettore *"
                outlined
                dense
              />
            </div>
            <div class="col-6 col-md-3">
              <q-input v-model="formReceipt.data_emissione" type="date" label="Data Emissione *" outlined dense />
            </div>
            <div class="col-6 col-md-3">
              <q-input v-model.number="formReceipt.termini_giorni" type="number" label="Termini Restituzione (gg)" outlined dense />
            </div>
          </div>

          <!-- Righe Tipologie Pallet -->
          <div class="q-mt-md">
            <div class="row justify-between items-center q-mb-sm">
              <div class="text-subtitle2 text-weight-bold">Bancali / Imballi Movimentati</div>
              <q-btn color="secondary" icon="add" label="Aggiungi Formato" size="sm" @click="addReceiptRow()" />
            </div>

            <div v-for="(row, idx) in formReceipt.items" :key="idx" class="row q-col-gutter-xs items-center q-mb-xs">
              <div class="col-12 col-md-5">
                <q-select
                  v-model="row.pallet_type_id"
                  :options="palletTypes"
                  option-label="descrizione"
                  option-value="id"
                  emit-value
                  map-options
                  label="Tipo Pallet *"
                  outlined
                  dense
                />
              </div>
              <div class="col-5 col-md-3">
                <q-input v-model.number="row.quantita_consegnata" type="number" label="Consegnati (pz)" outlined dense />
              </div>
              <div class="col-5 col-md-3">
                <q-input v-model.number="row.quantita_restituita" type="number" label="Resi Contestuali (pz)" outlined dense />
              </div>
              <div class="col-2 col-md-1 text-center">
                <q-btn flat round dense color="negative" icon="delete" @click="removeReceiptRow(idx)" :disabled="formReceipt.items.length <= 1" />
              </div>
            </div>
          </div>
        </q-card-section>

        <q-card-actions align="right" class="q-pa-md">
          <q-btn flat label="Annulla" color="grey" v-close-popup />
          <q-btn 
            label="Emetti Buono Pallet" 
            color="primary" 
            icon="confirmation_number" 
            :disabled="!formReceipt.partner_id || !formReceipt.items.length"
            :loading="savingReceipt"
            @click="saveReceipt"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- DIALOG REGISTRA RESO -->
    <q-dialog v-model="returnDialogOpen">
      <q-card style="min-width: 500px">
        <q-card-section class="row items-center justify-between">
          <div class="text-h6">Registrazione Reso Pallet Vuoti</div>
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>
        <q-separator />
        <q-card-section class="q-gutter-sm">
          <div class="text-caption text-grey-8">{{ selectedReceiptForReturn?.numero_completo }} - {{ selectedReceiptForReturn?.partner?.ragione_sociale }}</div>
          <div v-for="it in returnItems" :key="it.pallet_type_id" class="row justify-between items-center q-pa-sm bg-grey-1 rounded-borders">
            <div>
              <strong>{{ it.pallet_type_codice }}</strong>
              <div class="text-caption">A debito: {{ it.saldo_riga }} pz</div>
            </div>
            <div style="width: 120px">
              <q-input v-model.number="it.quantita_restituita" type="number" label="Pezzi Resi" outlined dense />
            </div>
          </div>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Annulla" color="grey" v-close-popup />
          <q-btn label="Conferma Reso" color="secondary" icon="check" @click="submitReturn" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- DIALOG DETTAGLIO BUONO -->
    <q-dialog v-model="detailDialogOpen">
      <q-card style="min-width: 550px">
        <q-card-section class="row items-center justify-between">
          <div>
            <div class="text-h6">{{ selectedReceipt?.numero_completo }}</div>
            <div class="text-caption">{{ selectedReceipt?.partner?.ragione_sociale }} - Emesso il: {{ selectedReceipt?.data_emissione }}</div>
          </div>
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>
        <q-separator />
        <q-card-section>
          <div v-for="it in selectedReceipt?.items" :key="it.id" class="q-pa-sm bg-grey-1 rounded-borders q-mb-xs row justify-between items-center">
            <div>
              <strong>{{ it.pallet_type_codice }} - {{ it.pallet_type_descrizione }}</strong>
              <div class="text-caption">Valore: € {{ Number(it.valore_risarcimento).toFixed(2) }} cad.</div>
            </div>
            <div class="text-right">
              <div>Consegnati: {{ it.quantita_consegnata }} | Resi: {{ it.quantita_restituita }}</div>
              <div :class="it.saldo_riga > 0 ? 'text-negative text-weight-bold' : 'text-positive'">
                Saldo: {{ it.saldo_riga }} pz
              </div>
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
import { ref, onMounted } from 'vue'
import axios from 'axios'

const activeTab = ref('receipts')
const receipts = ref([])
const ledger = ref([])
const palletTypes = ref([])
const partners = ref([])

const loadingReceipts = ref(false)
const loadingLedger = ref(false)
const savingReceipt = ref(false)
const newReceiptDialogOpen = ref(false)
const returnDialogOpen = ref(false)
const detailDialogOpen = ref(false)
const selectedReceipt = ref(null)
const selectedReceiptForReturn = ref(null)
const returnItems = ref([])

const receiptsFilter = ref('tutti')
const searchTerm = ref('')

const formReceipt = ref({
  partner_id: null,
  data_emissione: new Date().toISOString().split('T')[0],
  termini_giorni: 60,
  items: [
    { pallet_type_id: null, quantita_consegnata: 10, quantita_restituita: 0 }
  ]
})

const receiptColumns = [
  { name: 'numero_completo', label: 'Numero BP', field: 'numero_completo', align: 'left', sortable: true },
  { name: 'data_emissione', label: 'Data Emissione', field: 'data_emissione', align: 'center', sortable: true },
  { name: 'partner', label: 'Cliente / Vettore', field: row => row.partner?.ragione_sociale || '', align: 'left' },
  { name: 'scadenza', label: 'Termine di Legge (60gg)', field: 'data_limite_restituzione', align: 'center' },
  { name: 'saldo_netto', label: 'Saldo Debito', field: 'saldo_netto', align: 'right', sortable: true },
  { name: 'stato', label: 'Stato', field: 'stato', align: 'center' },
  { name: 'actions', label: 'Azioni', align: 'right' }
]

const ledgerColumns = [
  { name: 'partner_nome', label: 'Soggetto Debitore', field: 'partner_nome', align: 'left', sortable: true },
  { name: 'partner_tipo', label: 'Ruolo', field: row => row.partner_tipo?.toUpperCase(), align: 'center' },
  { name: 'saldi_dettaglio', label: 'Saldi per Formato', align: 'left' },
  { name: 'totale_bancali_debito', label: 'Totale Pallet a Debito', field: 'totale_bancali_debito', align: 'right', sortable: true },
  { name: 'buoni_scaduti', label: 'Stato Scadenze Legali', align: 'center' }
]

const typeColumns = [
  { name: 'codice', label: 'Codice Formato', field: 'codice', align: 'left', sortable: true },
  { name: 'descrizione', label: 'Descrizione Imballo', field: 'descrizione', align: 'left' },
  { name: 'materiale', label: 'Materiale', field: row => row.materiale?.toUpperCase(), align: 'center' },
  { name: 'valore', label: 'Valore Risarcimento (€)', field: 'valore_risarcimento', align: 'right', sortable: true }
]

const getStatusColor = (st) => {
  if (st === 'saldato') return 'positive'
  if (st === 'fatturato') return 'primary'
  return 'orange'
}

const fetchReceipts = async () => {
  loadingReceipts.value = true
  try {
    const params = {}
    if (receiptsFilter.value && receiptsFilter.value !== 'tutti') {
      params.stato = receiptsFilter.value
    }
    if (searchTerm.value) {
      params.search = searchTerm.value
    }
    const res = await axios.get('/api/pallets/receipts', { params })
    receipts.value = res.data
  } catch (err) {
    console.error('Error fetching pallet receipts:', err)
  } finally {
    loadingReceipts.value = false
  }
}

const fetchLedger = async () => {
  loadingLedger.value = true
  try {
    const res = await axios.get('/api/pallets/ledger')
    ledger.value = res.data
  } catch (err) {
    console.error('Error fetching pallet ledger:', err)
  } finally {
    loadingLedger.value = false
  }
}

const fetchPalletTypes = async () => {
  try {
    const res = await axios.get('/api/pallets/types')
    palletTypes.value = res.data
  } catch (err) {
    console.error('Error fetching pallet types:', err)
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

const openNewReceiptDialog = () => {
  formReceipt.value = {
    partner_id: null,
    data_emissione: new Date().toISOString().split('T')[0],
    termini_giorni: 60,
    items: [
      { pallet_type_id: palletTypes.value[0]?.id || null, quantita_consegnata: 10, quantita_restituita: 0 }
    ]
  }
  newReceiptDialogOpen.value = true
}

const addReceiptRow = () => {
  formReceipt.value.items.push({
    pallet_type_id: palletTypes.value[0]?.id || null,
    quantita_consegnata: 10,
    quantita_restituita: 0
  })
}

const removeReceiptRow = (idx) => {
  formReceipt.value.items.splice(idx, 1)
}

const saveReceipt = async () => {
  savingReceipt.value = true
  try {
    await axios.post('/api/pallets/receipts', formReceipt.value)
    newReceiptDialogOpen.value = false
    await fetchReceipts()
    await fetchLedger()
  } catch (err) {
    alert(err.response?.data?.error || 'Errore salvataggio Buono Pallet')
  } finally {
    savingReceipt.value = false
  }
}

const viewReceipt = (r) => {
  selectedReceipt.value = r
  detailDialogOpen.value = true
}

const openReturnDialog = (r) => {
  selectedReceiptForReturn.value = r
  returnItems.value = r.items
    .filter(it => it.saldo_riga > 0)
    .map(it => ({
      pallet_type_id: it.pallet_type_id,
      pallet_type_codice: it.pallet_type_codice,
      saldo_riga: it.saldo_riga,
      quantita_restituita: it.saldo_riga
    }))
  returnDialogOpen.value = true
}

const submitReturn = async () => {
  try {
    await axios.post(`/api/pallets/receipts/${selectedReceiptForReturn.value.id}/return`, {
      items: returnItems.value
    })
    returnDialogOpen.value = false
    await fetchReceipts()
    await fetchLedger()
  } catch (err) {
    alert(err.response?.data?.error || 'Errore durante registrazione reso')
  }
}

const invoiceUnreturned = async (r) => {
  if (confirm(`Confermare l'emissione della fattura in Reverse Charge per i bancali non restituiti del buono ${r.numero_completo}?`)) {
    try {
      await axios.post(`/api/pallets/receipts/${r.id}/invoice-unreturned`)
      await fetchReceipts()
      await fetchLedger()
    } catch (err) {
      alert(err.response?.data?.error || 'Errore durante fatturazione mancata resa')
    }
  }
}

onMounted(() => {
  fetchReceipts()
  fetchLedger()
  fetchPalletTypes()
  fetchPartners()
})
</script>
