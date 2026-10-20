<template>
  <div class="q-pa-md">
    <div class="row items-center justify-between q-mb-md">
      <div>
        <h2 class="text-h5 text-weight-bold q-my-none">Fatturazione Attiva & Scadenzario</h2>
        <div class="text-caption text-grey-7">Fatture differite da DDT (TD24), castelletto IVA e scadenze (ReteBio standard)</div>
      </div>
      <div class="q-gutter-sm">
        <q-btn 
          color="secondary" 
          icon="receipt_long" 
          label="Fatturazione Differita da DDT" 
          @click="openDifferitaWizard()"
        />
      </div>
    </div>

    <!-- Schede di Navigazione: Fatture vs Scadenzario -->
    <q-tabs v-model="activeTab" dense class="text-grey" active-color="primary" indicator-color="primary" align="left">
      <q-tab name="invoices" label="Fatture di Vendita" icon="receipt" />
      <q-tab name="installments" label="Scadenzario Rate" icon="payments" />
    </q-tabs>

    <q-separator class="q-mb-md" />

    <q-tab-panels v-model="activeTab" animated>
      <!-- TAB 1: ELENCO FATTURE -->
      <q-tab-panel name="invoices" class="q-pa-none">
        <div class="row q-gutter-sm items-center q-mb-md">
          <q-btn-toggle
            v-model="invoiceStatusFilter"
            toggle-color="primary"
            :options="[
              { label: 'Tutte', value: 'tutti' },
              { label: 'Emesse', value: 'emessa' },
              { label: 'Saldate', value: 'saldata' }
            ]"
            @update:model-value="fetchInvoices"
          />
          <q-space />
          <q-input 
            v-model="searchTerm" 
            dense 
            outlined 
            placeholder="Cerca numero o cliente..." 
            @update:model-value="fetchInvoices"
            style="min-width: 280px"
          >
            <template v-slot:append>
              <q-icon name="search" />
            </template>
          </q-input>
        </div>

        <q-table
          :rows="invoices"
          :columns="invoiceColumns"
          row-key="id"
          :loading="loading"
          flat
          bordered
        >
          <template v-slot:body-cell-numero_completo="props">
            <q-td :props="props">
              <span class="text-weight-bold text-primary">{{ props.row.numero_completo }}</span>
              <q-badge color="grey-3" text-color="grey-9" class="q-ml-sm">{{ props.row.tipo_documento }}</q-badge>
            </q-td>
          </template>

          <template v-slot:body-cell-cliente="props">
            <q-td :props="props">
              <span class="text-weight-medium">{{ props.row.cliente ? props.row.cliente.ragione_sociale : '-' }}</span>
              <div class="text-caption text-grey-7">{{ props.row.condizioni_pagamento }}</div>
            </q-td>
          </template>

          <template v-slot:body-cell-totali="props">
            <q-td :props="props" align="right">
              <div class="text-weight-bolder text-subtitle2">€ {{ Number(props.row.totale_fattura).toFixed(2) }}</div>
              <div class="text-caption text-grey-7">Imp: € {{ Number(props.row.totale_imponibile).toFixed(2) }} + IVA € {{ Number(props.row.totale_imposta).toFixed(2) }}</div>
            </q-td>
          </template>

          <template v-slot:body-cell-stato="props">
            <q-td :props="props" align="center">
              <q-chip 
                :color="props.row.stato === 'saldata' ? 'positive' : 'primary'" 
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
              <q-btn flat round dense color="primary" icon="visibility" @click="viewInvoice(props.row)" />
            </q-td>
          </template>
        </q-table>
      </q-tab-panel>

      <!-- TAB 2: SCADENZARIO RATE -->
      <q-tab-panel name="installments" class="q-pa-none">
        <div class="row q-gutter-sm items-center q-mb-md">
          <q-btn-toggle
            v-model="installmentStatusFilter"
            toggle-color="primary"
            :options="[
              { label: 'Tutte', value: 'tutti' },
              { label: 'Aperte', value: 'aperta' },
              { label: 'Incassate', value: 'incassata' }
            ]"
            @update:model-value="fetchInstallments"
          />
        </div>

        <q-table
          :rows="installments"
          :columns="installmentColumns"
          row-key="id"
          :loading="loadingInstallments"
          flat
          bordered
        >
          <template v-slot:body-cell-importo="props">
            <q-td :props="props" align="right">
              <span class="text-weight-bold text-subtitle2">€ {{ Number(props.row.importo).toFixed(2) }}</span>
            </q-td>
          </template>

          <template v-slot:body-cell-stato="props">
            <q-td :props="props" align="center">
              <q-chip 
                :color="getInstallmentColor(props.row)" 
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
              <q-btn 
                v-if="props.row.stato === 'aperta'"
                color="positive" 
                label="Incassa" 
                dense 
                size="sm" 
                icon="check" 
                @click="payInstallment(props.row)"
              />
            </q-td>
          </template>
        </q-table>
      </q-tab-panel>
    </q-tab-panels>

    <!-- WIZARD MODALE: FATTURAZIONE DIFFERITA DA DDT -->
    <q-dialog v-model="differitaDialogOpen" persistent full-width>
      <q-card style="max-width: 900px; margin: auto">
        <q-card-section class="row items-center justify-between">
          <div class="text-h6">Fatturazione Differita da DDT (Fine Mese)</div>
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>

        <q-separator />

        <q-card-section class="q-gutter-md">
          <div class="row q-col-gutter-sm">
            <div class="col-12 col-md-6">
              <q-select
                v-model="wizard.cliente_id"
                :options="customerOptions"
                option-label="ragione_sociale"
                option-value="id"
                emit-value
                map-options
                label="Seleziona Cliente *"
                outlined
                dense
                @update:model-value="onWizardClientChange"
              />
            </div>
            <div class="col-12 col-md-3">
              <q-input v-model="wizard.data_documento" type="date" label="Data Fattura *" outlined dense />
            </div>
            <div class="col-12 col-md-3">
              <q-input v-model="wizard.condizioni_pagamento" label="Condizioni Pagamento" outlined dense />
            </div>
          </div>

          <!-- Tabella DDT Da Fatturare -->
          <div class="q-mt-md">
            <div class="text-subtitle2 text-weight-bold q-mb-xs">DDT Confermati da Fatturare</div>
            <div v-if="!wizard.cliente_id" class="text-grey-6 text-caption">Seleziona un cliente per visualizzare le bolle aperte.</div>
            <div v-else-if="!unbilledDdts.length" class="text-negative text-caption">Nessun DDT confermato in attesa di fatturazione per questo cliente.</div>
            
            <div v-else class="q-gutter-xs">
              <div 
                v-for="ddt in unbilledDdts" 
                :key="ddt.id" 
                class="row items-center justify-between q-pa-sm bg-grey-2 rounded-borders"
              >
                <div class="row items-center q-gutter-sm">
                  <q-checkbox v-model="wizard.selectedDdtIds" :val="ddt.id" />
                  <strong>{{ ddt.numero_completo }}</strong>
                  <span class="text-grey-7">del {{ ddt.data_documento }}</span>
                  <span class="text-caption">({{ ddt.colli_totali }} colli, {{ ddt.peso_totale_netto }} Kg)</span>
                </div>
                <div class="text-weight-bold text-primary">
                  € {{ Number(ddt.totale_imponibile).toFixed(2) }}
                </div>
              </div>
            </div>
          </div>

          <!-- Box Totali Anteprima -->
          <div class="q-pa-md bg-green-1 rounded-borders row justify-between items-center q-mt-md">
            <div>
              DDT Selezionati: <strong>{{ wizard.selectedDdtIds.length }}</strong>
            </div>
            <div class="text-h6 text-positive">
              Totale Imponibile Stimato: <strong>€ {{ wizardTotalSelected.toFixed(2) }}</strong>
            </div>
          </div>
        </q-card-section>

        <q-card-actions align="right" class="q-pa-md">
          <q-btn flat label="Annulla" color="grey" v-close-popup />
          <q-btn 
            label="Emetti Fattura Differita" 
            color="secondary" 
            icon="receipt_long" 
            :disabled="!wizard.selectedDdtIds.length"
            :loading="issuingInvoice"
            @click="issueDifferitaInvoice"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- DIALOG DETTAGLIO FATTURA -->
    <q-dialog v-model="detailDialogOpen">
      <q-card style="min-width: 600px; max-width: 750px">
        <q-card-section class="row items-center justify-between">
          <div>
            <div class="text-h6">{{ selectedInvoice?.numero_completo }}</div>
            <div class="text-caption">{{ selectedInvoice?.cliente?.ragione_sociale }} - Data: {{ selectedInvoice?.data_documento }}</div>
          </div>
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>
        <q-separator />
        <q-card-section class="q-gutter-sm">
          <div class="text-subtitle2 text-weight-bold">Castelletto IVA</div>
          <div class="row q-gutter-md">
            <div v-for="(iva, aliquota) in selectedInvoice?.castelletto_iva" :key="aliquota" class="q-pa-sm bg-grey-2 rounded-borders">
              <div>Aliquota: <strong>{{ aliquota }}%</strong></div>
              <div>Imponibile: € {{ Number(iva.imponibile).toFixed(2) }}</div>
              <div>Imposta: € {{ Number(iva.imposta).toFixed(2) }}</div>
            </div>
          </div>

          <div class="text-subtitle2 text-weight-bold q-mt-md">Rate Scadenzario</div>
          <div v-for="inst in selectedInvoice?.installments" :key="inst.id" class="row justify-between items-center q-pa-sm bg-grey-1 rounded-borders">
            <span>Rata {{ inst.numero_rata }}/{{ inst.totale_rate }} - Scadenza: <strong>{{ inst.data_scadenza }}</strong></span>
            <div>
              <span class="q-mr-md text-weight-bold">€ {{ Number(inst.importo).toFixed(2) }}</span>
              <q-badge :color="inst.stato === 'incassata' ? 'positive' : 'orange'">{{ inst.stato.toUpperCase() }}</q-badge>
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

const activeTab = ref('invoices')
const invoices = ref([])
const installments = ref([])
const partners = ref([])
const unbilledDdts = ref([])
const loading = ref(false)
const loadingInstallments = ref(false)
const issuingInvoice = ref(false)
const differitaDialogOpen = ref(false)
const detailDialogOpen = ref(false)
const selectedInvoice = ref(null)

const invoiceStatusFilter = ref('tutti')
const installmentStatusFilter = ref('tutti')
const searchTerm = ref('')

const wizard = ref({
  cliente_id: null,
  data_documento: new Date().toISOString().split('T')[0],
  condizioni_pagamento: '30gg fm',
  selectedDdtIds: []
})

const invoiceColumns = [
  { name: 'numero_completo', label: 'Numero Fattura', field: 'numero_completo', align: 'left', sortable: true },
  { name: 'data_documento', label: 'Data', field: 'data_documento', align: 'center', sortable: true },
  { name: 'cliente', label: 'Cliente & Pagamento', field: row => row.cliente?.ragione_sociale || '', align: 'left' },
  { name: 'totali', label: 'Totale Fattura', field: 'totale_fattura', align: 'right', sortable: true },
  { name: 'stato', label: 'Stato', field: 'stato', align: 'center' },
  { name: 'actions', label: 'Dettaglio', align: 'right' }
]

const installmentColumns = [
  { name: 'invoice_numero', label: 'Fattura', field: 'invoice_numero', align: 'left' },
  { name: 'cliente_nome', label: 'Cliente', field: 'cliente_nome', align: 'left' },
  { name: 'rata', label: 'Rata', field: row => `Rata ${row.numero_rata} di ${row.totale_rate}`, align: 'center' },
  { name: 'data_scadenza', label: 'Data Scadenza', field: 'data_scadenza', align: 'center', sortable: true },
  { name: 'importo', label: 'Importo (€)', field: 'importo', align: 'right', sortable: true },
  { name: 'stato', label: 'Stato', field: 'stato', align: 'center' },
  { name: 'actions', label: 'Azioni', align: 'right' }
]

const customerOptions = computed(() => partners.value.filter(p => p.tipo === 'cliente' || p.tipo === 'entrambi'))

const wizardTotalSelected = computed(() => {
  return unbilledDdts.value
    .filter(d => wizard.value.selectedDdtIds.includes(d.id))
    .reduce((sum, d) => sum + (Number(d.totale_imponibile) || 0), 0)
})

const getInstallmentColor = (inst) => {
  if (inst.stato === 'incassata') return 'positive'
  const today = new Date().toISOString().split('T')[0]
  if (inst.data_scadenza < today) return 'negative'
  return 'orange'
}

const fetchInvoices = async () => {
  loading.value = true
  try {
    const params = {}
    if (invoiceStatusFilter.value && invoiceStatusFilter.value !== 'tutti') {
      params.stato = invoiceStatusFilter.value
    }
    if (searchTerm.value) {
      params.search = searchTerm.value
    }
    const res = await axios.get('/api/invoices', { params })
    invoices.value = res.data
  } catch (err) {
    console.error('Error fetching invoices:', err)
  } finally {
    loading.value = false
  }
}

const fetchInstallments = async () => {
  loadingInstallments.value = true
  try {
    const params = {}
    if (installmentStatusFilter.value && installmentStatusFilter.value !== 'tutti') {
      params.stato = installmentStatusFilter.value
    }
    const res = await axios.get('/api/installments', { params })
    installments.value = res.data
  } catch (err) {
    console.error('Error fetching installments:', err)
  } finally {
    loadingInstallments.value = false
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

const openDifferitaWizard = () => {
  wizard.value = {
    cliente_id: null,
    data_documento: new Date().toISOString().split('T')[0],
    condizioni_pagamento: '30gg fm',
    selectedDdtIds: []
  }
  unbilledDdts.value = []
  differitaDialogOpen.value = true
}

const onWizardClientChange = async (clienteId) => {
  if (!clienteId) return
  const client = partners.value.find(p => p.id === clienteId)
  if (client) {
    wizard.value.condizioni_pagamento = client.condizioni_pagamento || '30gg fm'
  }
  try {
    const res = await axios.get(`/api/delivery-notes/unbilled?cliente_id=${clienteId}`)
    unbilledDdts.value = res.data
    wizard.value.selectedDdtIds = unbilledDdts.value.map(d => d.id)
  } catch (err) {
    console.error('Error loading unbilled DDTs:', err)
  }
}

const issueDifferitaInvoice = async () => {
  if (!wizard.value.selectedDdtIds.length) return
  issuingInvoice.value = true
  try {
    await axios.post('/api/invoices/from-ddt', {
      cliente_id: wizard.value.cliente_id,
      data_documento: wizard.value.data_documento,
      condizioni_pagamento: wizard.value.condizioni_pagamento,
      ddt_ids: wizard.value.selectedDdtIds
    })
    differitaDialogOpen.value = false
    await fetchInvoices()
    await fetchInstallments()
  } catch (err) {
    alert(err.response?.data?.error || 'Errore durante emissione fattura differita')
  } finally {
    issuingInvoice.value = false
  }
}

const viewInvoice = (inv) => {
  selectedInvoice.value = inv
  detailDialogOpen.value = true
}

const payInstallment = async (inst) => {
  if (confirm(`Confermare l'incasso della rata di € ${inst.importo}?`)) {
    try {
      await axios.post(`/api/installments/${inst.id}/pay`)
      await fetchInstallments()
      await fetchInvoices()
    } catch (err) {
      alert(err.response?.data?.error || 'Errore durante registrazione incasso')
    }
  }
}

onMounted(() => {
  fetchInvoices()
  fetchInstallments()
  fetchPartners()
})
</script>
