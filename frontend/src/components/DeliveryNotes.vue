<template>
  <div class="q-pa-md">
    <div class="row items-center justify-between q-mb-md">
      <div>
        <h2 class="text-h5 text-weight-bold q-my-none">Documenti di Trasporto (DDT)</h2>
        <div class="text-caption text-grey-7">Gestione spedizioni, tracciabilità lotti biologici e vettori (ReteBio standard)</div>
      </div>
      <q-btn 
        color="primary" 
        icon="add" 
        label="Nuovo DDT" 
        @click="openEditor()"
      />
    </div>

    <!-- Filtri rapidi per Stato -->
    <div class="row q-gutter-sm items-center q-mb-md">
      <q-btn-toggle
        v-model="statusFilter"
        toggle-color="primary"
        :options="[
          { label: 'Tutti', value: 'tutti' },
          { label: 'Bozze', value: 'bozza' },
          { label: 'Confermati', value: 'confermato' },
          { label: 'Fatturati', value: 'fatturato' }
        ]"
        @update:model-value="fetchDdts"
      />
      <q-space />
      <q-input 
        v-model="searchTerm" 
        dense 
        outlined 
        placeholder="Cerca numero DDT o cliente..." 
        @update:model-value="fetchDdts"
        style="min-width: 280px"
      >
        <template v-slot:append>
          <q-icon name="search" />
        </template>
      </q-input>
    </div>

    <!-- Tabella Quasar Elenco DDT -->
    <q-table
      :rows="ddts"
      :columns="columns"
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

      <template v-slot:body-cell-cliente="props">
        <q-td :props="props">
          <span class="text-weight-medium">{{ props.row.cliente ? props.row.cliente.ragione_sociale : '-' }}</span>
          <div v-if="props.row.vettore" class="text-caption text-grey-7">
            Vettore: {{ props.row.vettore.ragione_sociale }}
          </div>
        </q-td>
      </template>

      <template v-slot:body-cell-totali="props">
        <q-td :props="props" align="right">
          <div><strong>{{ props.row.colli_totali }}</strong> colli ({{ Number(props.row.peso_totale_netto).toFixed(1) }} Kg)</div>
          <div class="text-caption text-grey-8">€ {{ Number(props.row.totale_imponibile).toFixed(2) }}</div>
        </q-td>
      </template>

      <template v-slot:body-cell-stato="props">
        <q-td :props="props" align="center">
          <q-chip 
            :color="getStatusColor(props.row.stato)" 
            text-color="white" 
            dense 
            size="sm"
          >
            {{ props.row.stato.toUpperCase() }}
          </q-chip>
        </q-td>
      </template>

      <template v-slot:body-cell-actions="props">
        <q-td :props="props" align="right">
          <q-btn flat round dense color="primary" icon="visibility" @click="openEditor(props.row)" />
          <q-btn 
            v-if="props.row.stato === 'bozza'" 
            flat 
            round 
            dense 
            color="positive" 
            icon="check_circle" 
            @click="confirmDdt(props.row)" 
            title="Conferma DDT"
          />
          <q-btn 
            v-if="props.row.stato === 'bozza'" 
            flat 
            round 
            dense 
            color="negative" 
            icon="delete" 
            @click="deleteDdt(props.row)" 
          />
          <q-btn 
            v-if="props.row.cliente?.nazione && props.row.cliente?.nazione !== 'IT'" 
            color="indigo" 
            dense 
            size="sm"
            icon="public" 
            label="CMR" 
            class="q-ml-xs"
            @click="generateCmr(props.row)" 
            title="Emetti Lettera di Vettura CMR Export"
          />
          <q-btn 
            flat 
            round 
            dense 
            color="teal" 
            icon="qr_code_2" 
            @click="openLabelsForDdt(props.row)" 
            title="Stampa Etichette Barcode Bancale"
          />
        </q-td>
      </template>
    </q-table>

    <!-- Dialog Editor DDT (Testata + Righe Merci) -->
    <q-dialog v-model="editorOpen" persistent full-width>
      <q-card style="max-width: 1000px; margin: auto">
        <q-card-section class="row items-center justify-between">
          <div>
            <div class="text-h6">
              {{ form.id ? `DDT ${form.numero_completo}` : 'Nuovo Documento di Trasporto' }}
            </div>
            <div class="text-caption" v-if="form.stato">
              Stato: <q-badge :color="getStatusColor(form.stato)">{{ form.stato.toUpperCase() }}</q-badge>
            </div>
          </div>
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>

        <q-separator />

        <q-card-section class="q-gutter-md">
          <!-- Sezione Testata -->
          <div class="row q-col-gutter-sm">
            <div class="col-12 col-md-4">
              <q-select
                v-model="form.cliente_id"
                :options="customerOptions"
                option-label="ragione_sociale"
                option-value="id"
                emit-value
                map-options
                label="Cliente Destinatario *"
                outlined
                dense
                :disable="form.stato !== 'bozza'"
              />
            </div>
            <div class="col-12 col-md-4">
              <q-select
                v-model="form.vettore_id"
                :options="carrierOptions"
                option-label="ragione_sociale"
                option-value="id"
                emit-value
                map-options
                label="Vettore di Trasporto"
                outlined
                dense
                clearable
                :disable="form.stato !== 'bozza'"
              />
            </div>
            <div class="col-12 col-md-4">
              <q-input
                v-model="form.data_documento"
                type="date"
                label="Data Documento *"
                outlined
                dense
                :disable="form.stato !== 'bozza'"
              />
            </div>
          </div>

          <div class="row q-col-gutter-sm">
            <div class="col-12 col-md-4">
              <q-select
                v-model="form.causale_trasporto"
                :options="['Vendita', 'Conto Lavorazione', 'Conto Visione', 'Reso', 'Omaggio']"
                label="Causale Trasporto"
                outlined
                dense
                :disable="form.stato !== 'bozza'"
              />
            </div>
            <div class="col-12 col-md-4">
              <q-select
                v-model="form.porto"
                :options="['Franco', 'Assegnato']"
                label="Porto"
                outlined
                dense
                :disable="form.stato !== 'bozza'"
              />
            </div>
            <div class="col-12 col-md-4">
              <q-select
                v-model="form.aspetto_beni"
                :options="['Colli', 'Pallet', 'Casse CPR', 'A vista']"
                label="Aspetto dei Beni"
                outlined
                dense
                :disable="form.stato !== 'bozza'"
              />
            </div>
          </div>

          <!-- Sezione Righe Merci -->
          <div class="q-mt-md">
            <div class="row items-center justify-between q-mb-sm">
              <div class="text-subtitle1 text-weight-bold">Righe Merci & Tracciabilità Biologica</div>
              <q-btn 
                v-if="form.stato === 'bozza'"
                color="secondary" 
                icon="add" 
                label="Aggiungi Riga Articolo" 
                dense 
                size="sm" 
                @click="addItemRow" 
              />
            </div>

            <div v-for="(item, idx) in form.items" :key="idx" class="q-pa-sm q-mb-sm bg-grey-1 rounded-borders bordered">
              <div class="row q-col-gutter-xs items-center">
                <div class="col-12 col-md-3">
                  <q-select
                    v-model="item.product_id"
                    :options="productOptions"
                    option-label="descrizione"
                    option-value="id"
                    emit-value
                    map-options
                    label="Articolo *"
                    dense
                    outlined
                    @update:model-value="(val) => onProductSelect(val, item)"
                    :disable="form.stato !== 'bozza'"
                  />
                </div>
                <div class="col-4 col-md-1">
                  <q-input v-model.number="item.colli" type="number" label="Colli" dense outlined :disable="form.stato !== 'bozza'" />
                </div>
                <div class="col-4 col-md-1">
                  <q-input v-model.number="item.quantita" type="number" step="0.1" :label="`Q.tà (${item.unita_misura || 'Kg'}) *`" dense outlined :disable="form.stato !== 'bozza'" />
                </div>
                <div class="col-4 col-md-1">
                  <q-input v-model.number="item.prezzo_unitario" type="number" step="0.01" label="Prezzo €" dense outlined :disable="form.stato !== 'bozza'" />
                </div>
                <!-- Campi Tracciabilità Biologica -->
                <div class="col-6 col-md-2">
                  <q-input 
                    v-model="item.lotto" 
                    label="Lotto Bio" 
                    dense 
                    outlined 
                    :bg-color="item.in_scadenza && !item.lotto ? 'red-1' : ''"
                    :placeholder="item.in_scadenza ? 'Obbligatorio Bio' : 'Lotto'"
                    :disable="form.stato !== 'bozza'"
                  />
                  <q-btn
                    v-if="item.fefo_suggestion && form.stato === 'bozza'"
                    flat
                    dense
                    size="xs"
                    color="positive"
                    icon="auto_awesome"
                    :label="`FEFO: ${item.fefo_suggestion.lotto}`"
                    @click="applyFefo(item)"
                    class="q-mt-xs"
                  >
                    <q-tooltip>Usa consigliato FEFO (Scad: {{ item.fefo_suggestion.data_scadenza }}, Giac: {{ item.fefo_suggestion.giacenza_kg }} Kg)</q-tooltip>
                  </q-btn>
                </div>
                <div class="col-5 col-md-2">
                  <q-input 
                    v-model="item.data_scadenza" 
                    type="date" 
                    label="Scadenza Bio" 
                    dense 
                    outlined 
                    :bg-color="item.in_scadenza && !item.data_scadenza ? 'red-1' : ''"
                    :disable="form.stato !== 'bozza'"
                  />
                </div>
                <div class="col-1 col-md-1 text-right">
                  <span class="text-weight-bold text-caption">€ {{ (item.quantita * item.prezzo_unitario).toFixed(2) }}</span>
                </div>
                <div class="col-1 col-md-1 text-center" v-if="form.stato === 'bozza'">
                  <q-btn flat round dense color="negative" icon="delete" size="sm" @click="removeItemRow(idx)" />
                </div>
              </div>
            </div>
          </div>

          <!-- Box Riepilogo Totali -->
          <div class="q-pa-md bg-blue-1 rounded-borders row justify-between items-center q-mt-md">
            <div>
              Totale Colli: <strong>{{ computedTotalColli }}</strong>
              <span class="q-ml-md">Peso Netto Stimato: <strong>{{ computedTotalQty.toFixed(1) }} Kg</strong></span>
            </div>
            <div class="text-h6 text-primary">
              Totale Imponibile: <strong>€ {{ computedTotalAmount.toFixed(2) }}</strong>
            </div>
          </div>
        </q-card-section>

        <q-card-actions align="right" class="q-pa-md">
          <q-btn flat label="Chiudi" color="grey" v-close-popup />
          <q-btn 
            v-if="form.stato === 'bozza'" 
            outline 
            label="Salva Bozza" 
            color="primary" 
            @click="saveDdt(false)" 
            :loading="saving" 
          />
          <q-btn 
            v-if="form.stato === 'bozza'" 
            label="Conferma DDT" 
            color="positive" 
            icon="check_circle" 
            @click="saveDdt(true)" 
            :loading="saving" 
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Dialog Etichette Barcode Termiche -->
    <BarcodeLabelsDialog v-model="labelsDialogOpen" :labels="currentDdtLabels" :title="labelsDialogTitle" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import BarcodeLabelsDialog from './BarcodeLabelsDialog.vue'

const ddts = ref([])
const partners = ref([])
const products = ref([])
const loading = ref(false)
const saving = ref(false)
const editorOpen = ref(false)
const statusFilter = ref('tutti')
const searchTerm = ref('')

const labelsDialogOpen = ref(false)
const currentDdtLabels = ref([])
const labelsDialogTitle = ref('')

const openLabelsForDdt = async (ddt) => {
  try {
    const res = await axios.get(`/api/delivery-notes/${ddt.id}/labels?type=pallet`)
    currentDdtLabels.value = res.data.labels || []
    labelsDialogTitle.value = `Etichette Bancale DDT ${ddt.numero_completo}`
    labelsDialogOpen.value = true
  } catch (err) {
    alert(err.response?.data?.error || 'Errore caricamento etichette')
  }
}

const defaultForm = () => ({
  id: null,
  numero_completo: '',
  cliente_id: null,
  vettore_id: null,
  data_documento: new Date().toISOString().split('T')[0],
  causale_trasporto: 'Vendita',
  porto: 'Franco',
  aspetto_beni: 'Colli',
  note: '',
  stato: 'bozza',
  items: []
})

const form = ref(defaultForm())

const columns = [
  { name: 'numero_completo', label: 'Numero DDT', field: 'numero_completo', align: 'left', sortable: true },
  { name: 'data_documento', label: 'Data', field: 'data_documento', align: 'center', sortable: true },
  { name: 'cliente', label: 'Cliente & Vettore', field: row => row.cliente ? row.cliente.ragione_sociale : '', align: 'left' },
  { name: 'causale_trasporto', label: 'Causale', field: 'causale_trasporto', align: 'center' },
  { name: 'totali', label: 'Colli & Imponibile', field: 'totale_imponibile', align: 'right' },
  { name: 'stato', label: 'Stato', field: 'stato', align: 'center' },
  { name: 'actions', label: 'Azioni', align: 'right' }
]

const customerOptions = computed(() => partners.value.filter(p => p.tipo === 'cliente' || p.tipo === 'entrambi'))
const carrierOptions = computed(() => partners.value.filter(p => p.tipo === 'vettore'))
const productOptions = computed(() => products.value)

const computedTotalColli = computed(() => form.value.items.reduce((sum, item) => sum + (Number(item.colli) || 0), 0))
const computedTotalQty = computed(() => form.value.items.reduce((sum, item) => sum + (Number(item.quantita) || 0), 0))
const computedTotalAmount = computed(() => form.value.items.reduce((sum, item) => sum + ((Number(item.quantita) || 0) * (Number(item.prezzo_unitario) || 0)), 0))

const getStatusColor = (stato) => {
  switch (stato) {
    case 'bozza': return 'orange'
    case 'confermato': return 'positive'
    case 'fatturato': return 'blue'
    default: return 'grey'
  }
}

const fetchDdts = async () => {
  loading.value = true
  try {
    const params = {}
    if (statusFilter.value && statusFilter.value !== 'tutti') {
      params.stato = statusFilter.value
    }
    if (searchTerm.value) {
      params.search = searchTerm.value
    }
    const res = await axios.get('/api/delivery-notes', { params })
    ddts.value = res.data
  } catch (err) {
    console.error('Error fetching DDTs:', err)
  } finally {
    loading.value = false
  }
}

const fetchDependencies = async () => {
  try {
    const [pRes, prodRes] = await Promise.all([
      axios.get('/api/partners'),
      axios.get('/api/products')
    ])
    partners.value = pRes.data
    products.value = prodRes.data
  } catch (err) {
    console.error('Error fetching dependencies:', err)
  }
}

const openEditor = async (ddt = null) => {
  if (ddt) {
    try {
      const res = await axios.get(`/api/delivery-notes/${ddt.id}`)
      form.value = res.data
    } catch (err) {
      form.value = { ...ddt }
    }
  } else {
    form.value = defaultForm()
    addItemRow()
  }
  editorOpen.value = true
}

const addItemRow = () => {
  form.value.items.push({
    product_id: null,
    descrizione: '',
    unita_misura: 'KG',
    colli: 1,
    quantita: 1.0,
    prezzo_unitario: 0.0,
    aliquota_iva: 4,
    lotto: '',
    data_scadenza: '',
    in_scadenza: false
  })
}

const removeItemRow = (idx) => {
  form.value.items.splice(idx, 1)
}

const fefoSuggestions = ref([])

const loadFefoSuggestions = async (productId, item = null) => {
  try {
    const res = await axios.get(`/api/warehouse/fefo-suggestions?product_id=${productId}`)
    fefoSuggestions.value = res.data
    if (item && res.data.length > 0) {
      item.fefo_suggestion = res.data[0]
    }
  } catch (err) {
    fefoSuggestions.value = []
  }
}

const applyFefo = (item) => {
  if (item.fefo_suggestion) {
    item.lotto = item.fefo_suggestion.lotto
    item.data_scadenza = item.fefo_suggestion.data_scadenza
  }
}

const onProductSelect = async (productId, item = {}) => {
  const prod = products.value.find(p => p.id === productId) || (typeof item === 'object' && item.in_scadenza !== undefined ? item : null)
  if (prod) {
    item.descrizione = prod.descrizione || item.descrizione
    item.unita_misura = prod.unita_misura || item.unita_misura
    item.prezzo_unitario = prod.prezzo_vendita ?? item.prezzo_unitario
    item.aliquota_iva = prod.aliquota_iva ?? item.aliquota_iva
    item.in_scadenza = prod.in_scadenza ?? item.in_scadenza

    if (item.in_scadenza) {
      await loadFefoSuggestions(productId, item)
    }
  }
}

const onProductSelected = onProductSelect

const saveDdt = async (confirmImmediately = false) => {
  if (!form.value.cliente_id) {
    alert('Seleziona il cliente destinatario.')
    return
  }
  if (!form.value.items.length) {
    alert('Aggiungi almeno una riga merce.')
    return
  }

  saving.value = true
  try {
    let ddtId = form.value.id
    if (ddtId) {
      await axios.put(`/api/delivery-notes/${ddtId}`, form.value)
    } else {
      const res = await axios.post('/api/delivery-notes', form.value)
      ddtId = res.data.id
    }

    if (confirmImmediately && ddtId) {
      await axios.post(`/api/delivery-notes/${ddtId}/confirm`)
    }

    editorOpen.value = false
    await fetchDdts()
  } catch (err) {
    alert(err.response?.data?.error || 'Errore durante il salvataggio del DDT')
  } finally {
    saving.value = false
  }
}

const confirmDdt = async (ddt) => {
  if (confirm(`Confermare formalmente il DDT ${ddt.numero_completo}? Il documento non sarà più modificabile.`)) {
    try {
      await axios.post(`/api/delivery-notes/${ddt.id}/confirm`)
      await fetchDdts()
    } catch (err) {
      alert(err.response?.data?.error || 'Errore durante la conferma del DDT')
    }
  }
}

const deleteDdt = async (ddt) => {
  if (confirm(`Eliminare la bozza del DDT ${ddt.numero_completo}?`)) {
    try {
      await axios.delete(`/api/delivery-notes/${ddt.id}`)
      await fetchDdts()
    } catch (err) {
      alert(err.response?.data?.error || 'Errore durante l\'eliminazione')
    }
  }
}

const generateCmr = async (row) => {
  if (confirm(`Emettere la Lettera di Vettura Internazionale CMR per il DDT ${row.numero_completo}?`)) {
    try {
      const res = await axios.post(`/api/cmr/from-ddt/${row.id}`)
      alert(`Lettera di Vettura ${res.data.numero_completo} emessa con successo per ${row.cliente?.ragione_sociale || 'cliente'}!`)
    } catch (err) {
      alert(err.response?.data?.error || 'Errore durante la generazione del CMR')
    }
  }
}

onMounted(() => {
  fetchDdts()
  fetchDependencies()
})
</script>
