<template>
  <div class="q-pa-md">
    <div class="row items-center justify-between q-mb-md">
      <div>
        <h2 class="text-h5 text-weight-bold q-my-none">Anagrafica Soggetti</h2>
        <div class="text-caption text-grey-7">Gestione unificata Clienti, Fornitori e Vettori (ReteBio standard)</div>
      </div>
      <q-btn 
        color="primary" 
        icon="add" 
        label="Nuovo Soggetto" 
        @click="openDialog()"
      />
    </div>

    <!-- Filtri rapidi per Tipologia -->
    <div class="row q-gutter-sm items-center q-mb-md">
      <q-btn-toggle
        v-model="tipoFilter"
        toggle-color="primary"
        :options="[
          { label: 'Tutti', value: 'tutti' },
          { label: 'Clienti', value: 'cliente' },
          { label: 'Fornitori', value: 'fornitore' },
          { label: 'Vettori', value: 'vettore' }
        ]"
        @update:model-value="fetchPartners"
      />
      <q-space />
      <q-input 
        v-model="searchTerm" 
        dense 
        outlined 
        placeholder="Cerca ragione sociale, P.IVA, città..." 
        @update:model-value="fetchPartners"
        style="min-width: 280px"
      >
        <template v-slot:append>
          <q-icon name="search" />
        </template>
      </q-input>
    </div>

    <!-- Tabella Quasar -->
    <q-table
      :rows="partners"
      :columns="columns"
      row-key="id"
      :loading="loading"
      flat
      bordered
    >
      <template v-slot:body-cell-tipo="props">
        <q-td :props="props">
          <q-chip 
            :color="getTipoColor(props.row.tipo)" 
            text-color="white" 
            dense 
            size="sm"
          >
            {{ props.row.tipo.toUpperCase() }}
          </q-chip>
        </q-td>
      </template>

      <template v-slot:body-cell-sdi="props">
        <q-td :props="props">
          <span class="text-weight-medium">{{ props.row.codice_sdi }}</span>
          <div v-if="props.row.pec" class="text-caption text-grey-6">{{ props.row.pec }}</div>
        </q-td>
      </template>

      <template v-slot:body-cell-actions="props">
        <q-td :props="props" align="right">
          <q-btn flat round dense color="primary" icon="edit" @click="openDialog(props.row)" />
          <q-btn flat round dense color="negative" icon="delete" @click="confirmDelete(props.row)" />
        </q-td>
      </template>
    </q-table>

    <!-- Dialog Creazione/Modifica -->
    <q-dialog v-model="dialogOpen">
      <q-card style="min-width: 500px; max-width: 600px">
        <q-card-section>
          <div class="text-h6">{{ form.id ? 'Modifica Soggetto' : 'Nuovo Soggetto' }}</div>
        </q-card-section>

        <q-card-section class="q-pt-none q-gutter-sm">
          <q-input v-model="form.ragione_sociale" label="Ragione Sociale *" outlined dense />
          
          <div class="row q-col-gutter-sm">
            <div class="col-6">
              <q-select 
                v-model="form.tipo" 
                :options="['cliente', 'fornitore', 'vettore', 'entrambi']" 
                label="Tipologia *" 
                outlined 
                dense 
              />
            </div>
            <div class="col-6">
              <q-input v-model="form.codice_sdi" label="Codice Destinatario SDI" outlined dense maxlength="7" />
            </div>
          </div>

          <div class="row q-col-gutter-sm">
            <div class="col-6">
              <q-input v-model="form.partita_iva" label="Partita IVA" outlined dense />
            </div>
            <div class="col-6">
              <q-input v-model="form.codice_fiscale" label="Codice Fiscale" outlined dense />
            </div>
          </div>

          <q-input v-model="form.pec" label="Indirizzo PEC" outlined dense />
          <q-input v-model="form.indirizzo" label="Indirizzo" outlined dense />

          <div class="row q-col-gutter-sm">
            <div class="col-4">
              <q-input v-model="form.cap" label="CAP" outlined dense />
            </div>
            <div class="col-5">
              <q-input v-model="form.citta" label="Città" outlined dense />
            </div>
            <div class="col-3">
              <q-input v-model="form.provincia" label="Provincia" outlined dense maxlength="5" />
            </div>
          </div>

          <q-input v-model="form.istituto_certificatore" label="Istituto Certificatore Bio (es. ICEA, CCPB)" outlined dense />
          <q-input v-model="form.iban" label="Coordinate IBAN" outlined dense />
          <q-input v-model="form.condizioni_pagamento" label="Condizioni Pagamento" outlined dense placeholder="30gg fm" />
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat label="Annulla" color="grey" v-close-popup />
          <q-btn flat label="Salva" color="primary" @click="savePartner" :loading="saving" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const partners = ref([])
const loading = ref(false)
const saving = ref(false)
const dialogOpen = ref(false)
const tipoFilter = ref('tutti')
const searchTerm = ref('')

const defaultForm = {
  id: null,
  ragione_sociale: '',
  tipo: 'cliente',
  partita_iva: '',
  codice_fiscale: '',
  indirizzo: '',
  cap: '',
  citta: '',
  provincia: '',
  nazione: 'IT',
  codice_sdi: '0000000',
  pec: '',
  istituto_certificatore: '',
  iban: '',
  condizioni_pagamento: '30gg fm'
}

const form = ref({ ...defaultForm })

const columns = [
  { name: 'ragione_sociale', label: 'Ragione Sociale', field: 'ragione_sociale', align: 'left', sortable: true },
  { name: 'tipo', label: 'Tipo', field: 'tipo', align: 'center', sortable: true },
  { name: 'partita_iva', label: 'P.IVA / CF', field: row => row.partita_iva || row.codice_fiscale, align: 'left' },
  { name: 'citta', label: 'Città', field: row => row.citta ? `${row.citta} (${row.provincia || ''})` : '-', align: 'left' },
  { name: 'sdi', label: 'SDI / PEC', field: 'codice_sdi', align: 'left' },
  { name: 'actions', label: 'Azioni', align: 'right' }
]

const getTipoColor = (tipo) => {
  switch (tipo) {
    case 'cliente': return 'primary'
    case 'fornitore': return 'positive'
    case 'vettore': return 'orange'
    case 'entrambi': return 'purple'
    default: return 'grey'
  }
}

const fetchPartners = async () => {
  loading.value = true
  try {
    const params = {}
    if (tipoFilter.value && tipoFilter.value !== 'tutti') {
      params.tipo = tipoFilter.value
    }
    if (searchTerm.value) {
      params.search = searchTerm.value
    }
    const res = await axios.get('/api/partners', { params })
    partners.value = res.data
  } catch (err) {
    console.error('Error fetching partners:', err)
  } finally {
    loading.value = false
  }
}

const openDialog = (partner = null) => {
  if (partner) {
    form.value = { ...partner }
  } else {
    form.value = { ...defaultForm }
  }
  dialogOpen.value = true
}

const savePartner = async () => {
  if (!form.value.ragione_sociale) return
  saving.value = true
  try {
    if (form.value.id) {
      await axios.put(`/api/partners/${form.value.id}`, form.value)
    } else {
      await axios.post('/api/partners', form.value)
    }
    dialogOpen.value = false
    await fetchPartners()
  } catch (err) {
    console.error('Error saving partner:', err)
  } finally {
    saving.value = false
  }
}

const confirmDelete = async (partner) => {
  if (confirm(`Sei sicuro di voler disattivare ${partner.ragione_sociale}?`)) {
    try {
      await axios.delete(`/api/partners/${partner.id}`)
      await fetchPartners()
    } catch (err) {
      console.error('Error deleting partner:', err)
    }
  }
}

onMounted(fetchPartners)
</script>
