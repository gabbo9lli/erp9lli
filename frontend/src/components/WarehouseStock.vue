<template>
  <div class="q-pa-md">
    <div class="row items-center justify-between q-mb-md">
      <div>
        <h2 class="text-h5 text-weight-bold q-my-none">Giacenze Magazzino & Tracciabilità FEFO</h2>
        <div class="text-caption text-grey-7">Disponibilità scorte per lotto con monitoraggio scadenze deperibili (ReteBio standard)</div>
      </div>
      <div class="q-gutter-sm">
        <q-btn flat round dense icon="refresh" @click="fetchStock" :loading="loading">
          <q-tooltip>Ricarica Giacenze</q-tooltip>
        </q-btn>
      </div>
    </div>

    <!-- KPI Scadenze -->
    <div class="row q-gutter-md q-mb-md">
      <q-badge color="positive" class="q-pa-sm text-subtitle2">
        Lotti Freschi: {{ countFresco }}
      </q-badge>
      <q-badge color="warning" text-color="black" class="q-pa-sm text-subtitle2">
        In Scadenza (≤15gg): {{ countInScadenza }}
      </q-badge>
      <q-badge color="negative" class="q-pa-sm text-subtitle2">
        Scaduti: {{ countScaduto }}
      </q-badge>
    </div>

    <!-- Barra di Ricerca -->
    <div class="row q-mb-md">
      <q-input 
        v-model="searchTerm" 
        dense 
        outlined 
        placeholder="Cerca per codice articolo, descrizione o lotto..." 
        style="min-width: 320px"
      >
        <template v-slot:append>
          <q-icon name="search" />
        </template>
      </q-input>
    </div>

    <!-- Tabella Giacenze -->
    <q-table
      :rows="filteredStocks"
      :columns="stockColumns"
      row-key="lotto"
      :loading="loading"
      flat
      bordered
    >
      <template v-slot:body-cell-product="props">
        <q-td :props="props">
          <div class="text-weight-bold text-primary">{{ props.row.product_codice }}</div>
          <div class="text-caption text-grey-8">{{ props.row.product_descrizione }}</div>
        </q-td>
      </template>

      <template v-slot:body-cell-lotto="props">
        <q-td :props="props">
          <q-badge color="grey-3" text-color="grey-9" class="text-weight-bold">
            {{ props.row.lotto }}
          </q-badge>
        </q-td>
      </template>

      <template v-slot:body-cell-scadenza="props">
        <q-td :props="props">
          <div class="row items-center q-gutter-xs">
            <span>{{ props.row.data_scadenza || '-' }}</span>
            <span v-if="props.row.giorni_a_scadere !== null" class="text-caption text-grey-7">
              ({{ props.row.giorni_a_scadere }} gg)
            </span>
          </div>
        </q-td>
      </template>

      <template v-slot:body-cell-stato_scadenza="props">
        <q-td :props="props" align="center">
          <q-chip 
            :color="getStatusColor(props.row.stato_scadenza)" 
            :text-color="props.row.stato_scadenza === 'in_scadenza' ? 'black' : 'white'"
            dense 
            size="sm"
          >
            {{ props.row.stato_scadenza.toUpperCase().replace('_', ' ') }}
          </q-chip>
        </q-td>
      </template>

      <template v-slot:body-cell-giacenza_kg="props">
        <q-td :props="props" align="right">
          <span class="text-weight-bolder text-subtitle2">{{ Number(props.row.giacenza_kg).toFixed(1) }} Kg</span>
          <div class="text-caption text-grey-7">({{ props.row.colli_disponibili }} colli)</div>
        </q-td>
      </template>
    </q-table>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const stocks = ref([])
const loading = ref(false)
const searchTerm = ref('')

const stockColumns = [
  { name: 'product', label: 'Articolo Biologico', field: 'product_codice', align: 'left', sortable: true },
  { name: 'lotto', label: 'Lotto Tracciabilità', field: 'lotto', align: 'left', sortable: true },
  { name: 'scadenza', label: 'Data Scadenza', field: 'data_scadenza', align: 'left', sortable: true },
  { name: 'stato_scadenza', label: 'Freschezza', field: 'stato_scadenza', align: 'center' },
  { name: 'giacenza_kg', label: 'Giacenza Disponibile', field: 'giacenza_kg', align: 'right', sortable: true }
]

const countFresco = computed(() => stocks.value.filter(s => s.stato_scadenza === 'fresco').length)
const countInScadenza = computed(() => stocks.value.filter(s => s.stato_scadenza === 'in_scadenza').length)
const countScaduto = computed(() => stocks.value.filter(s => s.stato_scadenza === 'scaduto').length)

const filteredStocks = computed(() => {
  if (!searchTerm.value) return stocks.value
  const term = searchTerm.value.toLowerCase()
  return stocks.value.filter(s => 
    (s.product_codice && s.product_codice.toLowerCase().includes(term)) ||
    (s.product_descrizione && s.product_descrizione.toLowerCase().includes(term)) ||
    (s.lotto && s.lotto.toLowerCase().includes(term))
  )
})

const getStatusColor = (st) => {
  if (st === 'fresco') return 'positive'
  if (st === 'in_scadenza') return 'warning'
  if (st === 'scaduto') return 'negative'
  return 'grey'
}

const fetchStock = async () => {
  loading.value = true
  try {
    const res = await axios.get('/api/warehouse/stock')
    stocks.value = res.data
  } catch (err) {
    console.error('Error fetching warehouse stock:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchStock()
})
</script>
