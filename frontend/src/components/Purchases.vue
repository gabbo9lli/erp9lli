<template>
  <div class="q-pa-md">
    <div class="row items-center justify-between q-mb-md">
      <div>
        <h2 class="text-h5 text-weight-bold q-my-none">Entrata Merci da Fornitori</h2>
        <div class="text-caption text-grey-7">Registrazione bolle d'acquisto con tracciabilità lotti bio e scadenze (ReteBio standard)</div>
      </div>
      <div>
        <q-btn 
          color="primary" 
          icon="add" 
          label="Registra Carico Merci" 
          @click="openNewPurchaseDialog()"
        />
      </div>
    </div>

    <!-- Barra di Ricerca -->
    <div class="row q-mb-md">
      <q-input 
        v-model="searchTerm" 
        dense 
        outlined 
        placeholder="Cerca fornitore o numero documento..." 
        @update:model-value="fetchPurchases"
        style="min-width: 320px"
      >
        <template v-slot:append>
          <q-icon name="search" />
        </template>
      </q-input>
    </div>

    <!-- Tabella Carichi Fornitori -->
    <q-table
      :rows="purchases"
      :columns="purchaseColumns"
      row-key="id"
      :loading="loading"
      flat
      bordered
    >
      <template v-slot:body-cell-numero_documento_fornitore="props">
        <q-td :props="props">
          <span class="text-weight-bold text-primary">{{ props.row.numero_documento_fornitore }}</span>
        </q-td>
      </template>

      <template v-slot:body-cell-fornitore="props">
        <q-td :props="props">
          <span class="text-weight-medium">{{ props.row.fornitore ? props.row.fornitore.ragione_sociale : '-' }}</span>
        </q-td>
      </template>

      <template v-slot:body-cell-totale_imponibile="props">
        <q-td :props="props" align="right">
          <span class="text-weight-bold">€ {{ Number(props.row.totale_imponibile).toFixed(2) }}</span>
        </q-td>
      </template>

      <template v-slot:body-cell-actions="props">
        <q-td :props="props" align="right">
          <q-btn flat round dense color="primary" icon="visibility" @click="viewPurchase(props.row)">
            <q-tooltip>Dettaglio Righe e Lotti</q-tooltip>
          </q-btn>
        </q-td>
      </template>
    </q-table>

    <!-- DIALOG NUOVO CARICO FORNITORE -->
    <q-dialog v-model="newPurchaseDialogOpen" persistent full-width>
      <q-card style="max-width: 950px; margin: auto">
        <q-card-section class="row items-center justify-between">
          <div class="text-h6">Registrazione Carico Merci da Fornitore</div>
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>
        <q-separator />

        <q-card-section class="q-gutter-md">
          <div class="row q-col-gutter-sm">
            <div class="col-12 col-md-5">
              <q-select
                v-model="formPurchase.fornitore_id"
                :options="supplierOptions"
                option-label="ragione_sociale"
                option-value="id"
                emit-value
                map-options
                label="Fornitore *"
                outlined
                dense
              />
            </div>
            <div class="col-12 col-md-3">
              <q-input v-model="formPurchase.numero_documento_fornitore" label="N. DDT Fornitore *" outlined dense />
            </div>
            <div class="col-6 col-md-2">
              <q-input v-model="formPurchase.data_documento" type="date" label="Data Documento *" outlined dense />
            </div>
            <div class="col-6 col-md-2">
              <q-input v-model="formPurchase.data_ricezione" type="date" label="Data Arrivo *" outlined dense />
            </div>
          </div>

          <!-- Righe Merci e Lotti -->
          <div class="q-mt-md">
            <div class="row justify-between items-center q-mb-sm">
              <div class="text-subtitle2 text-weight-bold">Righe Merci Ricevute & Lotti Bio</div>
              <q-btn color="secondary" icon="add" label="Aggiungi Riga" size="sm" @click="addPurchaseRow()" />
            </div>

            <div v-for="(row, idx) in formPurchase.items" :key="idx" class="row q-col-gutter-xs items-center q-mb-xs">
              <div class="col-12 col-md-3">
                <q-select
                  v-model="row.product_id"
                  :options="products"
                  option-label="descrizione"
                  option-value="id"
                  emit-value
                  map-options
                  label="Articolo *"
                  outlined
                  dense
                  @update:model-value="val => onProductSelected(val, row)"
                />
              </div>
              <div class="col-3 col-md-1">
                <q-input v-model.number="row.colli" type="number" label="Colli *" outlined dense />
              </div>
              <div class="col-4 col-md-2">
                <q-input v-model.number="row.quantita" type="number" step="0.1" label="Kg Netti *" outlined dense />
              </div>
              <div class="col-5 col-md-2">
                <q-input v-model.number="row.prezzo_unitario" type="number" step="0.01" label="Prezzo Acq. €" outlined dense />
              </div>
              <div class="col-6 col-md-2">
                <q-input 
                  v-model="row.lotto" 
                  label="Lotto Fornitore" 
                  outlined 
                  dense 
                  :bg-color="row.in_scadenza && !row.lotto ? 'red-1' : ''"
                  :placeholder="row.in_scadenza ? 'Obbligatorio' : 'Lotto'" 
                />
              </div>
              <div class="col-5 col-md-1">
                <q-input 
                  v-model="row.data_scadenza" 
                  type="date" 
                  label="Scadenza" 
                  outlined 
                  dense 
                  :bg-color="row.in_scadenza && !row.data_scadenza ? 'red-1' : ''" 
                />
              </div>
              <div class="col-1 text-center">
                <q-btn flat round dense color="negative" icon="delete" @click="removePurchaseRow(idx)" :disabled="formPurchase.items.length <= 1" />
              </div>
            </div>
          </div>
        </q-card-section>

        <q-card-actions align="right" class="q-pa-md">
          <q-btn flat label="Annulla" color="grey" v-close-popup />
          <q-btn 
            label="Registra Carico" 
            color="primary" 
            icon="save" 
            :disabled="!formPurchase.fornitore_id || !formPurchase.numero_documento_fornitore || !formPurchase.items.length"
            :loading="savingPurchase"
            @click="savePurchase"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- DIALOG DETTAGLIO CARICO -->
    <q-dialog v-model="detailDialogOpen">
      <q-card style="min-width: 600px; max-width: 750px">
        <q-card-section class="row items-center justify-between">
          <div>
            <div class="text-h6">DDT {{ selectedPurchase?.numero_documento_fornitore }}</div>
            <div class="text-caption">{{ selectedPurchase?.fornitore?.ragione_sociale }} - Ricevuto il: {{ selectedPurchase?.data_ricezione }}</div>
          </div>
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>
        <q-separator />
        <q-card-section>
          <div v-for="it in selectedPurchase?.items" :key="it.id" class="q-pa-sm bg-grey-1 rounded-borders q-mb-xs">
            <div class="row justify-between items-center">
              <div>
                <strong>{{ it.product_codice }} - {{ it.descrizione }}</strong>
                <div class="text-caption text-grey-7">Lotto: <strong>{{ it.lotto || '-' }}</strong> | Scadenza: {{ it.data_scadenza || '-' }}</div>
              </div>
              <div class="text-right">
                <div><strong>{{ it.quantita }} {{ it.unita_misura }}</strong> ({{ it.colli }} colli)</div>
                <div class="text-caption">€ {{ Number(it.prezzo_unitario).toFixed(2) }} / {{ it.unita_misura }}</div>
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
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const purchases = ref([])
const partners = ref([])
const products = ref([])
const loading = ref(false)
const savingPurchase = ref(false)
const newPurchaseDialogOpen = ref(false)
const detailDialogOpen = ref(false)
const selectedPurchase = ref(null)
const searchTerm = ref('')

const formPurchase = ref({
  fornitore_id: null,
  numero_documento_fornitore: '',
  data_documento: new Date().toISOString().split('T')[0],
  data_ricezione: new Date().toISOString().split('T')[0],
  items: [
    { product_id: null, colli: 1, quantita: 10.0, prezzo_unitario: 0.0, lotto: '', data_scadenza: '', in_scadenza: false }
  ]
})

const purchaseColumns = [
  { name: 'numero_documento_fornitore', label: 'N. Doc Fornitore', field: 'numero_documento_fornitore', align: 'left', sortable: true },
  { name: 'data_ricezione', label: 'Data Arrivo', field: 'data_ricezione', align: 'center', sortable: true },
  { name: 'fornitore', label: 'Fornitore / Produttore', field: row => row.fornitore?.ragione_sociale || '', align: 'left' },
  { name: 'colli_totali', label: 'Colli', field: 'colli_totali', align: 'right' },
  { name: 'peso_totale_netto', label: 'Peso Netto (Kg)', field: 'peso_totale_netto', align: 'right', sortable: true },
  { name: 'totale_imponibile', label: 'Imponibile (€)', field: 'totale_imponibile', align: 'right', sortable: true },
  { name: 'actions', label: 'Azioni', align: 'right' }
]

const supplierOptions = computed(() => partners.value.filter(p => p.tipo === 'fornitore' || p.tipo === 'entrambi'))

const fetchPurchases = async () => {
  loading.value = true
  try {
    const params = {}
    if (searchTerm.value) params.search = searchTerm.value
    const res = await axios.get('/api/purchases', { params })
    purchases.value = res.data
  } catch (err) {
    console.error('Error fetching purchases:', err)
  } finally {
    loading.value = false
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

const fetchProducts = async () => {
  try {
    const res = await axios.get('/api/products')
    products.value = res.data
  } catch (err) {
    console.error('Error fetching products:', err)
  }
}

const openNewPurchaseDialog = () => {
  formPurchase.value = {
    fornitore_id: null,
    numero_documento_fornitore: '',
    data_documento: new Date().toISOString().split('T')[0],
    data_ricezione: new Date().toISOString().split('T')[0],
    items: [
      { product_id: null, colli: 1, quantita: 10.0, prezzo_unitario: 0.0, lotto: '', data_scadenza: '', in_scadenza: false }
    ]
  }
  newPurchaseDialogOpen.value = true
}

const addPurchaseRow = () => {
  formPurchase.value.items.push({
    product_id: null,
    colli: 1,
    quantita: 10.0,
    prezzo_unitario: 0.0,
    lotto: '',
    data_scadenza: '',
    in_scadenza: false
  })
}

const removePurchaseRow = (idx) => {
  formPurchase.value.items.splice(idx, 1)
}

const onProductSelected = (productId, row) => {
  const prod = products.value.find(p => p.id === productId)
  if (prod) {
    row.prezzo_unitario = prod.prezzo_acquisto || 0.0
    row.in_scadenza = prod.in_scadenza
  }
}

const savePurchase = async () => {
  savingPurchase.value = true
  try {
    await axios.post('/api/purchases', formPurchase.value)
    newPurchaseDialogOpen.value = false
    await fetchPurchases()
  } catch (err) {
    alert(err.response?.data?.error || 'Errore salvataggio carico merci')
  } finally {
    savingPurchase.value = false
  }
}

const viewPurchase = (purchase) => {
  selectedPurchase.value = purchase
  detailDialogOpen.value = true
}

onMounted(() => {
  fetchPurchases()
  fetchPartners()
  fetchProducts()
})
</script>
