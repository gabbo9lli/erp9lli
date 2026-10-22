<template>
  <div class="q-pa-md">
    <div class="row justify-between items-center q-mb-md">
      <div>
        <div class="text-h5 text-weight-bold text-primary">
          <q-icon name="point_of_sale" class="q-mr-sm" />
          Vendita al Banco (POS / Cassa)
        </div>
        <div class="text-caption text-grey-7">
          Cassa rapida al minuto, tracciabilità lotti biologici FEFO e integrazione Registratore Telematico
        </div>
      </div>
      <div class="row items-center q-gutter-sm">
        <q-chip :color="currentStation?.attivo ? 'positive' : 'negative'" text-color="white" icon="devices">
          {{ currentStation ? `${currentStation.codice} (${currentStation.driver_tipo})` : 'Nessuna Cassa' }}
        </q-chip>
      </div>
    </div>

    <!-- TABS -->
    <q-tabs v-model="activeTab" dense class="text-grey" active-color="primary" indicator-color="primary" align="left">
      <q-tab name="pos" label="Cassa & Vendita Rapida" icon="shopping_bag" />
      <q-tab name="sales" label="Storico Scontrini" icon="receipt_long" />
      <q-tab name="settings" label="Configurazione Punto Cassa" icon="settings_suggest" />
    </q-tabs>

    <q-separator class="q-mb-md" />

    <q-tab-panels v-model="activeTab" animated>
      <!-- TAB 1: CASSA TOUCH -->
      <q-tab-panel name="pos" class="q-pa-none">
        <div class="row q-col-gutter-md">
          <!-- COLONNA SINISTRA: CATALOGO ARTICOLI -->
          <div class="col-12 col-md-7">
            <q-card flat bordered class="q-pa-sm">
              <q-input
                v-model="productSearch"
                dense
                outlined
                placeholder="Cerca prodotto per codice, descrizione..."
                clearable
                class="q-mb-sm"
              >
                <template v-slot:prepend>
                  <q-icon name="search" />
                </template>
              </q-input>

              <div class="row q-col-gutter-sm scroll" style="max-height: 65vh; overflow-y: auto;">
                <div v-for="prod in filteredProducts" :key="prod.id" class="col-12 col-sm-6 col-lg-4">
                  <q-card flat bordered class="cursor-pointer hover-shadow q-pa-sm" @click="addToCart(prod)">
                    <div class="text-weight-bold text-subtitle2 ellipsis">{{ prod.descrizione }}</div>
                    <div class="text-caption text-grey-7">Cod: {{ prod.codice }}</div>
                    <div class="row justify-between items-center q-mt-xs">
                      <span class="text-h6 text-primary text-weight-bolder">€ {{ Number(prod.prezzo_vendita || 0).toFixed(2) }}</span>
                      <q-badge color="teal">IVA {{ prod.aliquota_iva }}%</q-badge>
                    </div>
                    <q-btn
                      dense
                      flat
                      color="primary"
                      icon="add_shopping_cart"
                      label="Aggiungi"
                      class="full-width q-mt-xs bg-blue-1"
                    />
                  </q-card>
                </div>
              </div>
            </q-card>
          </div>

          <!-- COLONNA DESTRA: CARRELLO E PAGAMENTO -->
          <div class="col-12 col-md-5">
            <q-card flat bordered class="q-pa-md bg-grey-1">
              <div class="row justify-between items-center q-mb-sm">
                <div class="text-subtitle1 text-weight-bold">Carrello Spesa</div>
                <q-btn dense flat color="negative" icon="delete_sweep" label="Svuota" @click="clearCart" :disable="cart.length === 0" />
              </div>

              <!-- LISTA ARTICOLI IN CARRELLO -->
              <div class="scroll q-mb-md" style="max-height: 30vh; overflow-y: auto;">
                <div v-if="cart.length === 0" class="text-center text-grey-6 q-pa-lg">
                  <q-icon name="shopping_cart" size="48px" />
                  <div>Carrello vuoto. Seleziona i prodotti a sinistra.</div>
                </div>

                <div v-for="(item, idx) in cart" :key="idx" class="bg-white q-pa-sm q-mb-xs rounded-borders shadow-1">
                  <div class="row justify-between items-center">
                    <div class="text-weight-bold col-7 ellipsis">{{ item.descrizione }}</div>
                    <div class="col-5 text-right text-weight-bolder text-primary">€ {{ item.subtotale.toFixed(2) }}</div>
                  </div>
                  <div class="row justify-between items-center q-mt-xs">
                    <div class="row items-center q-gutter-xs">
                      <q-btn round dense flat size="sm" icon="remove" color="primary" @click="changeQty(item, -1)" />
                      <span class="text-weight-bold q-px-sm">{{ item.quantita }}</span>
                      <q-btn round dense flat size="sm" icon="add" color="primary" @click="changeQty(item, 1)" />
                    </div>
                    <div class="text-caption text-grey-7">€ {{ item.prezzo_unitario.toFixed(2) }} cad.</div>
                  </div>
                </div>
              </div>

              <q-separator class="q-mb-md" />

              <!-- TOTALI -->
              <div class="q-mb-md">
                <div class="row justify-between text-caption text-grey-8">
                  <span>Imponibile Netto:</span>
                  <span>€ {{ cartImponibile.toFixed(2) }}</span>
                </div>
                <div class="row justify-between text-caption text-grey-8">
                  <span>IVA Totale:</span>
                  <span>€ {{ cartIva.toFixed(2) }}</span>
                </div>
                <div class="row justify-between text-h5 text-weight-bolder text-primary q-mt-xs">
                  <span>TOTALE:</span>
                  <span>€ {{ cartTotal.toFixed(2) }}</span>
                </div>
              </div>

              <!-- MODALITÀ PAGAMENTO -->
              <div class="q-mb-sm">
                <div class="text-caption text-weight-bold text-grey-8 q-mb-xs">METODO DI PAGAMENTO</div>
                <q-btn-toggle
                  v-model="paymentMethod"
                  spread
                  no-caps
                  toggle-color="primary"
                  color="white"
                  text-color="primary"
                  :options="[
                    { label: 'Contanti', value: 'contanti', icon: 'payments' },
                    { label: 'Carta / POS', value: 'pos_carta', icon: 'credit_card' }
                  ]"
                />
              </div>

              <!-- TASTIERINO RAPIDO CONTANTI & RESTO -->
              <div v-if="paymentMethod === 'contanti'" class="q-mb-md">
                <div class="row q-gutter-xs q-mb-xs">
                  <q-btn dense outline color="primary" label="Esatto" @click="paidAmount = cartTotal" />
                  <q-btn dense outline color="primary" label="€ 5" @click="setPaidFast(5)" />
                  <q-btn dense outline color="primary" label="€ 10" @click="setPaidFast(10)" />
                  <q-btn dense outline color="primary" label="€ 20" @click="setPaidFast(20)" />
                  <q-btn dense outline color="primary" label="€ 50" @click="setPaidFast(50)" />
                </div>
                <div class="row q-col-gutter-sm items-center">
                  <div class="col-6">
                    <q-input
                      v-model.number="paidAmount"
                      dense
                      outlined
                      type="number"
                      step="0.01"
                      prefix="€"
                      label="Contante Ricevuto"
                    />
                  </div>
                  <div class="col-6 text-right">
                    <div class="text-caption text-grey-7">RESTO DA DARE:</div>
                    <div class="text-h6 text-weight-bolder" :class="calculatedResto >= 0 ? 'text-positive' : 'text-negative'">
                      € {{ calculatedResto.toFixed(2) }}
                    </div>
                  </div>
                </div>
              </div>

              <!-- PULSANTE EMISSIONE SCONTRINO -->
              <q-btn
                color="positive"
                icon="receipt"
                label="EMETTI SCONTRINO (F12)"
                class="full-width text-weight-bold q-py-sm"
                :disable="cart.length === 0 || (paymentMethod === 'contanti' && paidAmount < cartTotal)"
                @click="checkout"
              />
            </q-card>
          </div>
        </div>
      </q-tab-panel>

      <!-- TAB 2: STORICO SCONTRINI -->
      <q-tab-panel name="sales" class="q-pa-none">
        <q-table
          :rows="salesHistory"
          :columns="salesColumns"
          row-key="id"
          flat
          bordered
        >
          <template v-slot:body-cell-actions="props">
            <q-td :props="props" align="right">
              <q-btn flat round dense icon="print" color="primary" @click="reprintSale(props.row)" />
            </q-td>
          </template>
        </q-table>
      </q-tab-panel>

      <!-- TAB 3: CONFIGURAZIONE CASSA -->
      <q-tab-panel name="settings" class="q-pa-none">
        <q-card flat bordered class="q-pa-md" style="max-width: 600px">
          <div class="text-subtitle1 text-weight-bold q-mb-md">Impostazioni Punto Cassa & Registratore Telematico</div>
          <q-input v-model="stationForm.codice" label="Codice Cassa" outlined dense class="q-mb-sm" />
          <q-input v-model="stationForm.nome" label="Nome Cassa" outlined dense class="q-mb-sm" />
          <q-select
            v-model="stationForm.driver_tipo"
            :options="['simulator', 'epson_epos_http', 'custom_tcp', 'escpos_browser']"
            label="Tipo Driver Fiscale"
            outlined
            dense
            class="q-mb-sm"
          />
          <q-input v-model="stationForm.ip_address" label="Indirizzo IP Cassa (LAN)" outlined dense class="q-mb-sm" />
          <q-input v-model.number="stationForm.porta" label="Porta" type="number" outlined dense class="q-mb-sm" />
          <q-input v-model="stationForm.matricola_rt" label="Matricola Fiscale RT" outlined dense class="q-mb-sm" />
          <q-input v-model="stationForm.intestazione" label="Intestazione Scontrino" type="textarea" outlined dense class="q-mb-sm" />
          <q-input v-model="stationForm.pie_pagina" label="Messaggio di Cortesia" outlined dense class="q-mb-md" />
          <q-btn color="primary" label="Salva Configurazione" @click="saveStation" />
        </q-card>
      </q-tab-panel>
    </q-tab-panels>

    <!-- DIALOG ANTEPRIMA SCONTRINO TERMICO -->
    <q-dialog v-model="receiptDialogOpen">
      <q-card style="min-width: 380px; max-width: 440px;">
        <q-card-section class="row items-center justify-between bg-primary text-white">
          <div class="text-subtitle1 text-weight-bold">Scontrino Emesso</div>
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>

        <q-card-section class="q-pa-md bg-grey-2">
          <pre class="bg-white q-pa-sm rounded-borders text-caption text-weight-medium shadow-1" style="font-family: monospace; white-space: pre-wrap;">{{ lastReceiptText }}</pre>
        </q-card-section>

        <q-card-actions align="right" class="q-pa-md">
          <q-btn flat label="Chiudi" color="grey" v-close-popup />
          <q-btn icon="print" color="primary" label="Stampa Browser" @click="printBrowserReceipt" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const activeTab = ref('pos')
const products = ref([])
const productSearch = ref('')
const currentStation = ref(null)
const salesHistory = ref([])

const cart = ref([])
const paymentMethod = ref('contanti')
const paidAmount = ref(0)

const receiptDialogOpen = ref(false)
const lastReceiptText = ref('')

const stationForm = ref({
  codice: 'CASSA_01',
  nome: 'Cassa Banco Principale',
  driver_tipo: 'simulator',
  ip_address: '',
  porta: 80,
  matricola_rt: '99MEY0001',
  intestazione: 'RETEBIO SOCIETA\' AGRICOLA\nBOLOGNA (BO)',
  pie_pagina: 'ARRIVEDERCI E GRAZIE'
})

const salesColumns = [
  { name: 'numero_scontrino', label: 'Numero Scontrino', field: 'numero_scontrino', align: 'left', sortable: true },
  { name: 'data_ora', label: 'Data / Ora', field: 'data_ora', align: 'left' },
  { name: 'totale_lordo', label: 'Totale (€)', field: row => `€ ${row.totale_lordo.toFixed(2)}`, align: 'right' },
  { name: 'metodo_pagamento', label: 'Pagamento', field: 'metodo_pagamento', align: 'center' },
  { name: 'stato_fiscale_rt', label: 'Stato RT', field: 'stato_fiscale_rt', align: 'center' },
  { name: 'actions', label: 'Ristampa', align: 'right' }
]

const filteredProducts = computed(() => {
  if (!productSearch.value) return products.value
  const q = productSearch.value.toLowerCase()
  return products.value.filter(p =>
    (p.descrizione && p.descrizione.toLowerCase().includes(q)) ||
    (p.codice && p.codice.toLowerCase().includes(q))
  )
})

const cartTotal = computed(() => {
  return cart.value.reduce((sum, it) => sum + it.subtotale, 0)
})

const cartIva = computed(() => {
  return cart.value.reduce((sum, it) => {
    const aliquota = it.aliquota_iva || 22.0
    const imp = it.subtotale / (1.0 + aliquota / 100.0)
    return sum + (it.subtotale - imp)
  }, 0)
})

const cartImponibile = computed(() => {
  return Math.max(0, cartTotal.value - cartIva.value)
})

const calculatedResto = computed(() => {
  if (paymentMethod.value !== 'contanti') return 0
  return Math.max(0, paidAmount.value - cartTotal.value)
})

const addToCart = (prod) => {
  const existing = cart.value.find(it => it.product_id === prod.id)
  const price = Number(prod.prezzo_vendita || 0)
  if (existing) {
    existing.quantita += 1
    existing.subtotale = Number((existing.quantita * existing.prezzo_unitario).toFixed(2))
  } else {
    cart.value.push({
      product_id: prod.id,
      codice: prod.codice,
      descrizione: prod.descrizione,
      quantita: 1,
      prezzo_unitario: price,
      aliquota_iva: prod.aliquota_iva || 22.0,
      subtotale: price
    })
  }
  if (paymentMethod.value === 'contanti' && paidAmount.value < cartTotal.value) {
    paidAmount.value = cartTotal.value
  }
}

const changeQty = (item, delta) => {
  item.quantita += delta
  if (item.quantita <= 0) {
    cart.value = cart.value.filter(it => it.product_id !== item.product_id)
  } else {
    item.subtotale = Number((item.quantita * item.prezzo_unitario).toFixed(2))
  }
}

const clearCart = () => {
  cart.value = []
  paidAmount.value = 0
}

const setPaidFast = (amount) => {
  paidAmount.value = amount
}

const checkout = async () => {
  if (cart.value.length === 0) return
  try {
    const payload = {
      pos_station_id: currentStation.value?.id,
      metodo_pagamento: paymentMethod.value,
      importo_pagato: paymentMethod.value === 'contanti' ? Number(paidAmount.value) : cartTotal.value,
      items: cart.value.map(it => ({
        product_id: it.product_id,
        quantita: it.quantita,
        prezzo_unitario: it.prezzo_unitario
      }))
    }
    const res = await axios.post('/api/pos/sales', payload)
    lastReceiptText.value = res.data.ticket_ascii || 'Scontrino emesso.'
    receiptDialogOpen.value = true
    clearCart()
    fetchSales()
  } catch (err) {
    alert(err.response?.data?.error || 'Errore emissione scontrino')
  }
}

const reprintSale = async (sale) => {
  try {
    const res = await axios.post(`/api/pos/sales/${sale.id}/print`)
    lastReceiptText.value = res.data.ticket_ascii || 'Scontrino ristampato.'
    receiptDialogOpen.value = true
  } catch (err) {
    alert(err.response?.data?.error || 'Errore ristampa scontrino')
  }
}

const printBrowserReceipt = () => {
  window.print()
}

const fetchProducts = async () => {
  try {
    const res = await axios.get('/api/products')
    products.value = res.data
  } catch (err) {
    console.error('Error fetching products:', err)
  }
}

const fetchStations = async () => {
  try {
    const res = await axios.get('/api/pos/stations')
    if (res.data && res.data.length > 0) {
      currentStation.value = res.data[0]
      Object.assign(stationForm.value, res.data[0])
    }
  } catch (err) {
    console.error('Error fetching stations:', err)
  }
}

const fetchSales = async () => {
  try {
    const res = await axios.get('/api/pos/sales')
    salesHistory.value = res.data
  } catch (err) {
    console.error('Error fetching sales:', err)
  }
}

const saveStation = async () => {
  try {
    if (currentStation.value?.id) {
      const res = await axios.put(`/api/pos/stations/${currentStation.value.id}`, stationForm.value)
      currentStation.value = res.data
      alert('Configurazione cassa salvata con successo!')
    }
  } catch (err) {
    alert(err.response?.data?.error || 'Errore salvataggio cassa')
  }
}

onMounted(() => {
  fetchProducts()
  fetchStations()
  fetchSales()
})
</script>

<style scoped>
.hover-shadow:hover {
  box-shadow: 0 4px 8px rgba(0,0,0,0.12);
}
</style>
