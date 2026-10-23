<template>
  <div class="q-pa-md">
    <div class="row items-center justify-between q-mb-md">
      <div>
        <h2 class="text-h5 text-weight-bold q-my-none">Gestione Ordini Clienti</h2>
        <div class="text-caption text-grey-7">Presa in carico ordini a sequenze (passi di 5) ed evasione in DDT (ReteBio standard)</div>
      </div>
      <div class="row items-center q-gutter-sm">
        <q-btn 
          outline
          color="teal" 
          icon="sync_alt" 
          label="Log E-Commerce" 
          @click="openSyncLogsDialog"
        />
        <q-btn 
          color="primary" 
          icon="add_shopping_cart" 
          label="Nuovo Ordine" 
          @click="openNewOrderDialog()"
        />
      </div>
    </div>

    <!-- Filtri e Ricerca -->
    <div class="row q-gutter-sm items-center q-mb-md">
      <q-btn-toggle
        v-model="statusFilter"
        toggle-color="primary"
        :options="[
          { label: 'Tutti', value: 'tutti' },
          { label: 'Aperti', value: 'aperto' },
          { label: 'In Lavorazione', value: 'in_lavorazione' },
          { label: 'Chiusi', value: 'chiuso' }
        ]"
        @update:model-value="fetchOrders"
      />
      <q-space />
      <q-input 
        v-model="searchTerm" 
        dense 
        outlined 
        placeholder="Cerca numero o cliente..." 
        @update:model-value="fetchOrders"
        style="min-width: 280px"
      >
        <template v-slot:append>
          <q-icon name="search" />
        </template>
      </q-input>
    </div>

    <!-- Tabella Ordini -->
    <q-table
      :rows="orders"
      :columns="orderColumns"
      row-key="id"
      :loading="loading"
      flat
      bordered
    >
      <template v-slot:body-cell-numero_completo="props">
        <q-td :props="props">
          <div class="row items-center q-gutter-xs">
            <span class="text-weight-bold text-primary">{{ props.row.numero_completo }}</span>
            <q-badge v-if="props.row.canale_vendita === 'ecommerce'" color="positive" class="q-ml-xs">
              ECOMMERCE #{{ props.row.external_reference }}
            </q-badge>
          </div>
        </q-td>
      </template>

      <template v-slot:body-cell-cliente="props">
        <q-td :props="props">
          <span class="text-weight-medium">{{ props.row.cliente ? props.row.cliente.ragione_sociale : '-' }}</span>
        </q-td>
      </template>

      <template v-slot:body-cell-avanzamento="props">
        <q-td :props="props" style="min-width: 140px">
          <div class="row items-center q-gutter-xs">
            <q-linear-progress 
              :value="getOrderProgress(props.row)" 
              :color="getOrderProgressColor(props.row)" 
              size="8px" 
              class="col rounded-borders" 
            />
            <span class="text-caption text-weight-bold">{{ Math.round(getOrderProgress(props.row) * 100) }}%</span>
          </div>
        </q-td>
      </template>

      <template v-slot:body-cell-totale_imponibile="props">
        <q-td :props="props" align="right">
          <span class="text-weight-bold">€ {{ Number(props.row.totale_imponibile).toFixed(2) }}</span>
        </q-td>
      </template>

      <template v-slot:body-cell-stato="props">
        <q-td :props="props" align="center">
          <q-chip 
            :color="getOrderStatusColor(props.row.stato)" 
            text-color="white" 
            dense 
            size="sm"
          >
            {{ props.row.stato.toUpperCase().replace('_', ' ') }}
          </q-chip>
        </q-td>
      </template>

      <template v-slot:body-cell-actions="props">
        <q-td :props="props" align="right" class="q-gutter-xs">
          <q-btn flat round dense color="primary" icon="visibility" @click="viewOrder(props.row)">
            <q-tooltip>Dettaglio Righe</q-tooltip>
          </q-btn>
          <q-btn 
            v-if="props.row.stato !== 'chiuso'" 
            color="secondary" 
            icon="local_shipping" 
            label="Evadi in DDT" 
            dense 
            size="sm"
            @click="openFulfillDialog(props.row)"
          />
        </q-td>
      </template>
    </q-table>

    <!-- DIALOG NUOVO ORDINE CLIENTE -->
    <q-dialog v-model="newOrderDialogOpen" persistent full-width>
      <q-card style="max-width: 950px; margin: auto">
        <q-card-section class="row items-center justify-between">
          <div class="text-h6">Nuovo Ordine Cliente</div>
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>
        <q-separator />

        <q-card-section class="q-gutter-md">
          <div class="row q-col-gutter-sm">
            <div class="col-12 col-md-6">
              <q-select
                v-model="formOrder.cliente_id"
                :options="customerOptions"
                option-label="ragione_sociale"
                option-value="id"
                emit-value
                map-options
                label="Cliente *"
                outlined
                dense
              />
            </div>
            <div class="col-12 col-md-3">
              <q-input v-model="formOrder.data_ordine" type="date" label="Data Ordine *" outlined dense />
            </div>
            <div class="col-12 col-md-3">
              <q-input v-model="formOrder.data_richiesta" type="date" label="Data Richiesta Consegna" outlined dense />
            </div>
          </div>

          <!-- Righe Ordine a Sequenze (passi di 5) -->
          <div class="q-mt-md">
            <div class="row justify-between items-center q-mb-sm">
              <div class="text-subtitle2 text-weight-bold">Righe Articoli Ordinati</div>
              <q-btn color="secondary" icon="add" label="Aggiungi Riga" size="sm" @click="addOrderRow()" />
            </div>

            <div v-for="(row, idx) in formOrder.items" :key="idx" class="row q-col-gutter-xs items-center q-mb-xs">
              <div class="col-1 text-center">
                <q-badge color="grey-4" text-color="grey-9">Seq {{ row.sequenza }}</q-badge>
              </div>
              <div class="col-12 col-md-4">
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
              <div class="col-3 col-md-2">
                <q-input v-model.number="row.colli_ordinati" type="number" label="Colli *" outlined dense />
              </div>
              <div class="col-4 col-md-2">
                <q-input v-model.number="row.quantita_ordinata" type="number" step="0.1" label="Quantità (Kg) *" outlined dense />
              </div>
              <div class="col-3 col-md-2">
                <q-input v-model.number="row.prezzo_unitario" type="number" step="0.01" label="Prezzo Unit. (€)" outlined dense />
              </div>
              <div class="col-1 text-center">
                <q-btn flat round dense color="negative" icon="delete" @click="removeOrderRow(idx)" :disabled="formOrder.items.length <= 1" />
              </div>
            </div>
          </div>

          <div class="q-pa-md bg-grey-2 rounded-borders row justify-between items-center q-mt-md">
            <div>Righe Totali: <strong>{{ formOrder.items.length }}</strong></div>
            <div class="text-h6 text-primary">
              Totale Imponibile Stimato: <strong>€ {{ calculatedTotalOrder.toFixed(2) }}</strong>
            </div>
          </div>
        </q-card-section>

        <q-card-actions align="right" class="q-pa-md">
          <q-btn flat label="Annulla" color="grey" v-close-popup />
          <q-btn 
            label="Salva Ordine" 
            color="primary" 
            icon="save" 
            :disabled="!formOrder.cliente_id || !formOrder.items.length"
            :loading="savingOrder"
            @click="saveOrder"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- DIALOG EVASIONE IN DDT -->
    <q-dialog v-model="fulfillDialogOpen" persistent full-width>
      <q-card style="max-width: 850px; margin: auto">
        <q-card-section class="row items-center justify-between">
          <div>
            <div class="text-h6">Evasione Ordine in Bolla DDT</div>
            <div class="text-caption">{{ selectedOrderForFulfill?.numero_completo }} - {{ selectedOrderForFulfill?.cliente?.ragione_sociale }}</div>
          </div>
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>
        <q-separator />

        <q-card-section class="q-gutter-sm">
          <div class="text-subtitle2 text-weight-bold">Righe con Quantità Residua da Consegnare:</div>

          <div v-for="it in fulfillItems" :key="it.order_item_id" class="row q-col-gutter-sm items-center q-pa-sm bg-grey-1 rounded-borders q-mb-xs">
            <div class="col-12 col-md-5">
              <strong>{{ it.descrizione }}</strong>
              <div class="text-caption text-grey-7">Ordinati: {{ it.quantita_ordinata }} Kg | Consegnati: {{ it.quantita_consegnata }} Kg</div>
            </div>
            <div class="col-5 col-md-3">
              <q-input v-model.number="it.colli" type="number" label="Colli da Evadere" outlined dense />
            </div>
            <div class="col-7 col-md-4">
              <q-input v-model.number="it.quantita" type="number" step="0.1" :label="`Kg da Evadere (Max ${it.quantita_residua})`" outlined dense />
            </div>
          </div>
        </q-card-section>

        <q-card-actions align="right" class="q-pa-md">
          <q-btn flat label="Annulla" color="grey" v-close-popup />
          <q-btn 
            label="Emetti Bolla DDT" 
            color="secondary" 
            icon="local_shipping" 
            :loading="fulfilling"
            @click="submitFulfillment"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- DIALOG DETTAGLIO ORDINE -->
    <q-dialog v-model="detailDialogOpen">
      <q-card style="min-width: 600px; max-width: 750px">
        <q-card-section class="row items-center justify-between">
          <div>
            <div class="text-h6">{{ selectedOrder?.numero_completo }}</div>
            <div class="text-caption">{{ selectedOrder?.cliente?.ragione_sociale }} - Data: {{ selectedOrder?.data_ordine }}</div>
          </div>
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>
        <q-separator />
        <q-card-section>
          <div v-for="it in selectedOrder?.items" :key="it.id" class="q-pa-sm bg-grey-1 rounded-borders q-mb-xs">
            <div class="row justify-between items-center">
              <div>
                <strong>Seq {{ it.sequenza }}: {{ it.descrizione }}</strong>
                <div class="text-caption text-grey-7">Prezzo: € {{ Number(it.prezzo_unitario).toFixed(2) }} | IVA {{ it.aliquota_iva }}%</div>
              </div>
              <div class="text-right">
                <div>Ordinati: <strong>{{ it.quantita_ordinata }} {{ it.unita_misura }}</strong> ({{ it.colli_ordinati }} colli)</div>
                <div :class="it.quantita_residua > 0 ? 'text-negative' : 'text-positive'">
                  Consegnati: {{ it.quantita_consegnata }} | Residuo: <strong>{{ it.quantita_residua }} {{ it.unita_misura }}</strong>
                </div>
              </div>
            </div>
          </div>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Chiudi" color="grey" v-close-popup />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- DIALOG LOG E-COMMERCE -->
    <q-dialog v-model="syncLogsDialogOpen" full-width>
      <q-card style="max-width: 900px; margin: auto;">
        <q-card-section class="row items-center justify-between bg-teal text-white">
          <div class="text-h6 text-weight-bold">Sincronizzazione E-Commerce & Log Webhook</div>
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>

        <q-card-section class="q-pa-md">
          <div class="row justify-between items-center q-mb-md">
            <div class="text-subtitle2">Storico Webhook Ricevuti</div>
            <q-btn outline color="teal" icon="download" label="Esporta Feed Giacenze (JSON)" @click="downloadStockFeed" />
          </div>
          <q-table
            :rows="syncLogs"
            :columns="syncLogColumns"
            row-key="id"
            flat
            bordered
            dense
          />
        </q-card-section>
      </q-card>
    </q-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const orders = ref([])
const partners = ref([])
const products = ref([])
const loading = ref(false)
const savingOrder = ref(false)
const fulfilling = ref(false)

const newOrderDialogOpen = ref(false)
const fulfillDialogOpen = ref(false)
const detailDialogOpen = ref(false)
const selectedOrder = ref(null)
const selectedOrderForFulfill = ref(null)
const fulfillItems = ref([])

const statusFilter = ref('tutti')
const searchTerm = ref('')

const syncLogsDialogOpen = ref(false)
const syncLogs = ref([])

const syncLogColumns = [
  { name: 'timestamp', label: 'Data / Ora', field: 'timestamp', align: 'left', sortable: true },
  { name: 'tipo_operazione', label: 'Operazione', field: 'tipo_operazione', align: 'center' },
  { name: 'external_order_id', label: 'ID Ordine Web', field: 'external_order_id', align: 'left' },
  { name: 'stato', label: 'Esito', field: 'stato', align: 'center' },
  { name: 'dettaglio_risposta', label: 'Dettaglio', field: 'dettaglio_risposta', align: 'left' }
]

const openSyncLogsDialog = async () => {
  try {
    const res = await axios.get('/api/ecommerce/logs')
    syncLogs.value = res.data
    syncLogsDialogOpen.value = true
  } catch (err) {
    console.error('Errore recupero log:', err)
  }
}

const downloadStockFeed = async () => {
  try {
    const res = await axios.get('/api/ecommerce/sync/stock')
    const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `stock_feed_${new Date().toISOString().split('T')[0]}.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch (err) {
    alert('Errore download feed giacenze: ' + err)
  }
}

const formOrder = ref({
  cliente_id: null,
  data_ordine: new Date().toISOString().split('T')[0],
  data_richiesta: '',
  items: [
    { product_id: null, sequenza: 5, colli_ordinati: 1, quantita_ordinata: 10.0, prezzo_unitario: 0.0 }
  ]
})

const orderColumns = [
  { name: 'numero_completo', label: 'Numero Ordine', field: 'numero_completo', align: 'left', sortable: true },
  { name: 'data_ordine', label: 'Data', field: 'data_ordine', align: 'center', sortable: true },
  { name: 'cliente', label: 'Cliente', field: row => row.cliente?.ragione_sociale || '', align: 'left' },
  { name: 'avanzamento', label: 'Evasione', align: 'center' },
  { name: 'totale_imponibile', label: 'Imponibile (€)', field: 'totale_imponibile', align: 'right', sortable: true },
  { name: 'stato', label: 'Stato', field: 'stato', align: 'center' },
  { name: 'actions', label: 'Azioni', align: 'right' }
]

const customerOptions = computed(() => partners.value.filter(p => p.tipo === 'cliente' || p.tipo === 'entrambi'))

const calculatedTotalOrder = computed(() => {
  return formOrder.value.items.reduce((sum, it) => sum + ((Number(it.quantita_ordinata) || 0) * (Number(it.prezzo_unitario) || 0)), 0)
})

const getOrderStatusColor = (st) => {
  if (st === 'chiuso') return 'positive'
  if (st === 'in_lavorazione') return 'primary'
  return 'orange'
}

const getOrderProgress = (order) => {
  if (!order.items || !order.items.length) return 0
  const totOrd = order.items.reduce((s, it) => s + it.quantita_ordinata, 0)
  const totCons = order.items.reduce((s, it) => s + it.quantita_consegnata, 0)
  return totOrd > 0 ? Math.min(1, totCons / totOrd) : 0
}

const getOrderProgressColor = (order) => {
  const prog = getOrderProgress(order)
  if (prog >= 1) return 'positive'
  if (prog > 0) return 'primary'
  return 'orange'
}

const fetchOrders = async () => {
  loading.value = true
  try {
    const params = {}
    if (statusFilter.value && statusFilter.value !== 'tutti') {
      params.stato = statusFilter.value
    }
    if (searchTerm.value) {
      params.search = searchTerm.value
    }
    const res = await axios.get('/api/orders', { params })
    orders.value = res.data
  } catch (err) {
    console.error('Error fetching orders:', err)
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

const openNewOrderDialog = () => {
  formOrder.value = {
    cliente_id: null,
    data_ordine: new Date().toISOString().split('T')[0],
    data_richiesta: '',
    items: [
      { product_id: null, sequenza: 5, colli_ordinati: 1, quantita_ordinata: 10.0, prezzo_unitario: 0.0 }
    ]
  }
  newOrderDialogOpen.value = true
}

const addOrderRow = () => {
  const nextSeq = (formOrder.value.items.length * 5) + 5
  formOrder.value.items.push({
    product_id: null,
    sequenza: nextSeq,
    colli_ordinati: 1,
    quantita_ordinata: 10.0,
    prezzo_unitario: 0.0
  })
}

const removeOrderRow = (idx) => {
  formOrder.value.items.splice(idx, 1)
}

const onProductSelected = (productId, row) => {
  const prod = products.value.find(p => p.id === productId)
  if (prod) {
    row.prezzo_unitario = prod.prezzo_vendita || 0.0
  }
}

const saveOrder = async () => {
  savingOrder.value = true
  try {
    await axios.post('/api/orders', formOrder.value)
    newOrderDialogOpen.value = false
    await fetchOrders()
  } catch (err) {
    alert(err.response?.data?.error || 'Errore salvataggio ordine')
  } finally {
    savingOrder.value = false
  }
}

const viewOrder = (order) => {
  selectedOrder.value = order
  detailDialogOpen.value = true
}

const openFulfillDialog = (order) => {
  selectedOrderForFulfill.value = order
  fulfillItems.value = order.items
    .filter(it => it.quantita_residua > 0)
    .map(it => ({
      order_item_id: it.id,
      descrizione: it.descrizione,
      quantita_ordinata: it.quantita_ordinata,
      quantita_consegnata: it.quantita_consegnata,
      quantita_residua: it.quantita_residua,
      colli: it.colli_residui,
      quantita: it.quantita_residua
    }))
  fulfillDialogOpen.value = true
}

const submitFulfillment = async () => {
  fulfilling.value = true
  try {
    await axios.post(`/api/orders/${selectedOrderForFulfill.value.id}/fulfill-to-ddt`, {
      items: fulfillItems.value
    })
    fulfillDialogOpen.value = false
    await fetchOrders()
  } catch (err) {
    alert(err.response?.data?.error || 'Errore durante evasione ordine')
  } finally {
    fulfilling.value = false
  }
}

onMounted(() => {
  fetchOrders()
  fetchPartners()
  fetchProducts()
})
</script>
