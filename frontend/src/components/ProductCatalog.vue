<template>
  <div class="q-pa-md">
    <div class="row items-center justify-between q-mb-md">
      <div>
        <h2 class="text-h5 text-weight-bold q-my-none">Catalogo Articoli</h2>
        <div class="text-caption text-grey-7">Gestione articoli biologici, tracciabilità lotti e listini (ReteBio standard)</div>
      </div>
      <q-btn 
        color="primary" 
        icon="add" 
        label="Nuovo Articolo" 
        @click="openDialog()"
      />
    </div>

    <!-- Filtri rapidi per Categoria -->
    <div class="row q-gutter-sm items-center q-mb-md">
      <q-btn-toggle
        v-model="categoryFilter"
        toggle-color="primary"
        :options="[
          { label: 'Tutti', value: 'tutti' },
          { label: 'Fresco', value: 'fresco' },
          { label: 'Trasformato', value: 'trasformato' },
          { label: 'Imballo', value: 'imballo' }
        ]"
        @update:model-value="fetchProducts"
      />
      <q-space />
      <q-input 
        v-model="searchTerm" 
        dense 
        outlined 
        placeholder="Cerca codice o descrizione..." 
        @update:model-value="fetchProducts"
        style="min-width: 280px"
      >
        <template v-slot:append>
          <q-icon name="search" />
        </template>
      </q-input>
    </div>

    <!-- Tabella Quasar -->
    <q-table
      :rows="products"
      :columns="columns"
      row-key="id"
      :loading="loading"
      flat
      bordered
    >
      <template v-slot:body-cell-categoria="props">
        <q-td :props="props">
          <q-chip 
            :color="getCategoryColor(props.row.categoria)" 
            text-color="white" 
            dense 
            size="sm"
          >
            {{ props.row.categoria.toUpperCase() }}
          </q-chip>
          <q-chip 
            v-if="props.row.in_scadenza" 
            color="teal" 
            text-color="white" 
            dense 
            size="sm"
            icon="eco"
          >
            BIO / LOTTI
          </q-chip>
        </q-td>
      </template>

      <template v-slot:body-cell-prezzo_vendita="props">
        <q-td :props="props" align="right">
          <span class="text-weight-bold">€ {{ Number(props.row.prezzo_vendita).toFixed(2) }}</span>
          <div class="text-caption text-grey-6">IVA {{ props.row.aliquota_iva }}%</div>
        </q-td>
      </template>

      <template v-slot:body-cell-margine="props">
        <q-td :props="props" align="right">
          <span :class="getMarginClass(props.row)">
            € {{ (props.row.prezzo_vendita - props.row.prezzo_acquisto).toFixed(2) }}
          </span>
          <div class="text-caption text-grey-6">
            {{ calculateMarkup(props.row) }}
          </div>
        </q-td>
      </template>

      <template v-slot:body-cell-actions="props">
        <q-td :props="props" align="right">
          <q-btn flat round dense color="teal" icon="qr_code_2" @click="openProductLabel(props.row)">
            <q-tooltip>Stampa Etichetta Barcode</q-tooltip>
          </q-btn>
          <q-btn flat round dense color="primary" icon="edit" @click="openDialog(props.row)" />
          <q-btn flat round dense color="negative" icon="delete" @click="confirmDelete(props.row)" />
        </q-td>
      </template>
    </q-table>

    <!-- Dialog Creazione/Modifica -->
    <q-dialog v-model="dialogOpen">
      <q-card style="min-width: 500px; max-width: 600px">
        <q-card-section>
          <div class="text-h6">{{ form.id ? 'Modifica Articolo' : 'Nuovo Articolo' }}</div>
        </q-card-section>

        <q-card-section class="q-pt-none q-gutter-sm">
          <div class="row q-col-gutter-sm">
            <div class="col-5">
              <q-input v-model="form.codice" label="Codice Articolo *" outlined dense :disable="!!form.id" />
            </div>
            <div class="col-4">
              <q-select 
                v-model="form.categoria" 
                :options="['fresco', 'trasformato', 'imballo']" 
                label="Categoria *" 
                outlined 
                dense 
              />
            </div>
            <div class="col-3">
              <q-select 
                v-model="form.unita_misura" 
                :options="['KG', 'PZ', 'LT']" 
                label="UdM *" 
                outlined 
                dense 
              />
            </div>
          </div>

          <q-input v-model="form.descrizione" label="Descrizione Commerciale *" outlined dense />
          <q-input v-model="form.descrizione_en" label="Descrizione in Inglese (Export / CMR)" outlined dense />

          <div class="row q-col-gutter-sm">
            <div class="col-4">
              <q-input v-model.number="form.peso_netto" type="number" step="0.01" label="Peso Netto (Kg)" outlined dense />
            </div>
            <div class="col-4">
              <q-input v-model.number="form.peso_lordo" type="number" step="0.01" label="Peso Lordo (Kg)" outlined dense />
            </div>
            <div class="col-4">
              <q-input v-model.number="form.tara" type="number" step="0.01" label="Tara (Kg)" outlined dense />
            </div>
          </div>

          <div class="row q-col-gutter-sm items-center">
            <div class="col-6">
              <q-toggle 
                v-model="form.in_scadenza" 
                label="Tracciabilità Lotti / In Scadenza (Bio)" 
                color="teal" 
              />
            </div>
            <div class="col-6">
              <q-input v-model="form.codice_nc" label="Codice Doganale NC (Export)" outlined dense maxlength="15" />
            </div>
          </div>

          <div class="row q-col-gutter-sm">
            <div class="col-4">
              <q-input v-model.number="form.prezzo_acquisto" type="number" step="0.01" label="Prezzo Acquisto (€)" outlined dense />
            </div>
            <div class="col-4">
              <q-input v-model.number="form.prezzo_vendita" type="number" step="0.01" label="Prezzo Vendita (€) *" outlined dense />
            </div>
            <div class="col-4">
              <q-input v-model.number="form.aliquota_iva" type="number" label="Aliquota IVA %" outlined dense />
            </div>
          </div>

          <!-- Anteprima Margine in modale -->
          <div class="q-pa-sm bg-grey-2 rounded-borders row justify-between text-body2">
            <span>Margine Stimato: <strong>€ {{ (Number(form.prezzo_vendita || 0) - Number(form.prezzo_acquisto || 0)).toFixed(2) }}</strong></span>
            <span>Ricarico: <strong>{{ form.prezzo_acquisto > 0 ? (((form.prezzo_vendita - form.prezzo_acquisto) / form.prezzo_acquisto) * 100).toFixed(1) + '%' : '-' }}</strong></span>
          </div>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat label="Annulla" color="grey" v-close-popup />
          <q-btn flat label="Salva" color="primary" @click="saveProduct" :loading="saving" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Dialog Etichetta Barcode Termica -->
    <BarcodeLabelsDialog v-model="productLabelDialogOpen" :labels="productLabels" :title="productLabelTitle" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import BarcodeLabelsDialog from './BarcodeLabelsDialog.vue'

const productLabelDialogOpen = ref(false)
const productLabels = ref([])
const productLabelTitle = ref('')

const openProductLabel = async (prod) => {
  try {
    const res = await axios.post('/api/labels/generate', {
      label_type: 'collo',
      descrizione: prod.descrizione,
      codice_articolo: prod.codice,
      lotto: 'LOTTO-SAMPLE',
      data_scadenza: new Date().toISOString().split('T')[0],
      peso_netto: Number(prod.peso_netto || 1.0)
    })
    productLabels.value = [res.data]
    productLabelTitle.value = `Etichetta Prodotto ${prod.codice}`
    productLabelDialogOpen.value = true
  } catch (err) {
    alert(err.response?.data?.error || 'Errore generazione etichetta')
  }
}

const products = ref([])
const loading = ref(false)
const saving = ref(false)
const dialogOpen = ref(false)
const categoryFilter = ref('tutti')
const searchTerm = ref('')

const defaultForm = {
  id: null,
  codice: '',
  descrizione: '',
  descrizione_en: '',
  categoria: 'fresco',
  unita_misura: 'KG',
  peso_netto: 0.0,
  peso_lordo: 0.0,
  tara: 0.0,
  in_scadenza: false,
  scorta_minima: 0.0,
  prezzo_vendita: 0.0,
  prezzo_acquisto: 0.0,
  aliquota_iva: 4,
  codice_nc: ''
}

const form = ref({ ...defaultForm })

const columns = [
  { name: 'codice', label: 'Codice', field: 'codice', align: 'left', sortable: true },
  { name: 'descrizione', label: 'Descrizione', field: 'descrizione', align: 'left', sortable: true },
  { name: 'categoria', label: 'Categoria & Bio', field: 'categoria', align: 'center', sortable: true },
  { name: 'unita_misura', label: 'UdM', field: 'unita_misura', align: 'center' },
  { name: 'prezzo_acquisto', label: 'Costo (€)', field: row => `€ ${Number(row.prezzo_acquisto).toFixed(2)}`, align: 'right' },
  { name: 'prezzo_vendita', label: 'Listino (€)', field: 'prezzo_vendita', align: 'right', sortable: true },
  { name: 'margine', label: 'Margine (€)', align: 'right' },
  { name: 'actions', label: 'Azioni', align: 'right' }
]

const getCategoryColor = (cat) => {
  switch (cat) {
    case 'fresco': return 'positive'
    case 'trasformato': return 'warning'
    case 'imballo': return 'info'
    default: return 'grey'
  }
}

const getMarginClass = (row) => {
  const margin = Number(row.prezzo_vendita || 0) - Number(row.prezzo_acquisto || 0)
  return margin >= 0 ? 'text-positive text-weight-bold' : 'text-negative text-weight-bold'
}

const calculateMarkup = (row) => {
  const acq = Number(row.prezzo_acquisto || 0)
  const ven = Number(row.prezzo_vendita || 0)
  if (acq <= 0) return '-'
  const markup = ((ven - acq) / acq) * 100
  return `+${markup.toFixed(1)}%`
}

const fetchProducts = async () => {
  loading.value = true
  try {
    const params = {}
    if (categoryFilter.value && categoryFilter.value !== 'tutti') {
      params.categoria = categoryFilter.value
    }
    if (searchTerm.value) {
      params.search = searchTerm.value
    }
    const res = await axios.get('/api/products', { params })
    products.value = res.data
  } catch (err) {
    console.error('Error fetching products:', err)
  } finally {
    loading.value = false
  }
}

const openDialog = (product = null) => {
  if (product) {
    form.value = { ...product }
  } else {
    form.value = { ...defaultForm }
  }
  dialogOpen.value = true
}

const saveProduct = async () => {
  if (!form.value.codice || !form.value.descrizione) return
  saving.value = true
  try {
    if (form.value.id) {
      await axios.put(`/api/products/${form.value.id}`, form.value)
    } else {
      await axios.post('/api/products', form.value)
    }
    dialogOpen.value = false
    await fetchProducts()
  } catch (err) {
    console.error('Error saving product:', err)
  } finally {
    saving.value = false
  }
}

const confirmDelete = async (product) => {
  if (confirm(`Sei sicuro di voler disattivare ${product.codice}?`)) {
    try {
      await axios.delete(`/api/products/${product.id}`)
      await fetchProducts()
    } catch (err) {
      console.error('Error deleting product:', err)
    }
  }
}

onMounted(fetchProducts)
</script>
