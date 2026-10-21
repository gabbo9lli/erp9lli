<template>
  <div class="q-pa-md">
    <div class="row items-center justify-between q-mb-md">
      <div>
        <h2 class="text-h5 text-weight-bold q-my-none">Spedizioni Internazionali & Lettere di Vettura CMR</h2>
        <div class="text-caption text-grey-7">Convenzione di Ginevra 1956, export ortofrutta bio, hub Alessandria e regola 21 righe</div>
      </div>
      <div>
        <q-btn 
          color="primary" 
          icon="add" 
          label="Nuova Lettera CMR" 
          @click="openNewCmrDialog()"
        />
      </div>
    </div>

    <!-- Filtri e Ricerca -->
    <div class="row q-gutter-sm items-center q-mb-md">
      <q-input 
        v-model="searchTerm" 
        dense 
        outlined 
        placeholder="Cerca numero CMR, destinatario o destinazione..." 
        @update:model-value="fetchCmrs"
        style="min-width: 320px"
      >
        <template v-slot:append>
          <q-icon name="search" />
        </template>
      </q-input>
      <q-space />
      <div class="text-caption text-grey-7">
        Totale Spedizioni Estere: <strong>{{ cmrs.length }}</strong>
      </div>
    </div>

    <!-- Tabella CMR -->
    <q-table
      :rows="cmrs"
      :columns="columns"
      row-key="id"
      :loading="loading"
      flat
      bordered
    >
      <template v-slot:body-cell-numero_completo="props">
        <q-td :props="props">
          <span class="text-weight-bold text-primary">{{ props.row.numero_completo }}</span>
          <div v-if="props.row.delivery_note_numero" class="text-caption text-grey-7">DDT: {{ props.row.delivery_note_numero }}</div>
        </q-td>
      </template>

      <template v-slot:body-cell-cliente="props">
        <q-td :props="props">
          <span class="text-weight-medium">{{ props.row.cliente ? props.row.cliente.ragione_sociale : '-' }}</span>
          <q-badge color="indigo-8" text-color="white" class="q-ml-xs">
            {{ props.row.cliente?.nazione || 'ESTERO' }}
          </q-badge>
        </q-td>
      </template>

      <template v-slot:body-cell-hub_carico="props">
        <q-td :props="props">
          <q-chip dense color="teal-1" text-color="teal-9" icon="warehouse">
            {{ props.row.luogo_carico }}
          </q-chip>
        </q-td>
      </template>

      <template v-slot:body-cell-colli_pesi="props">
        <q-td :props="props" align="right">
          <div><strong>{{ props.row.totale_colli }}</strong> colli</div>
          <div class="text-caption text-grey-7">{{ Number(props.row.peso_totale_netto).toFixed(1) }} Kg netti ({{ Number(props.row.peso_totale_lordo).toFixed(1) }} lordi)</div>
        </q-td>
      </template>

      <template v-slot:body-cell-righe_allegato="props">
        <q-td :props="props" align="center">
          <q-badge v-if="props.row.ha_allegato_righe" color="deep-orange" text-color="white">
            ALLEGATO (>21 RIGHE)
          </q-badge>
          <q-badge v-else color="positive" text-color="white">
            CORPO CMR ({{ props.row.items?.length || 0 }} RIGHE)
          </q-badge>
        </q-td>
      </template>

      <template v-slot:body-cell-actions="props">
        <q-td :props="props" align="right" class="q-gutter-xs">
          <q-btn flat round dense color="primary" icon="description" @click="viewCmrModel(props.row)" title="Visualizza Modello CMR (24 Caselle)" />
          <q-btn flat round dense color="secondary" icon="edit" @click="editCmrTransport(props.row)" title="Modifica Dati Trasporto" />
        </q-td>
      </template>
    </q-table>

    <!-- DIALOG VISUALIZZATORE MODELLO CMR A 24 CASELLE -->
    <q-dialog v-model="cmrViewerOpen" full-width full-height>
      <q-card style="max-width: 1100px; margin: auto" class="column">
        <q-card-section class="row items-center justify-between bg-indigo-9 text-white q-py-sm">
          <div class="text-h6">
            <q-icon name="public" class="q-mr-sm" />
            CONTRATTO DI TRASPORTO INTERNAZIONALE MERCI SU STRADA (CMR) - {{ selectedCmr?.numero_completo }}
          </div>
          <q-btn icon="close" flat round dense v-close-popup text-color="white" />
        </q-card-section>

        <q-card-section class="col q-pa-md scroll" style="background-color: #fafafa">
          <!-- Griglia Caselle Standard CMR Convenzione di Ginevra 1956 -->
          <div class="cmr-grid">
            <!-- Riquadro Superiore: Mittente / Destinatario / Luoghi -->
            <div class="row q-col-gutter-sm q-mb-sm">
              <div class="col-12 col-md-6">
                <div class="cmr-box">
                  <div class="cmr-box-header">1. Mittente (nome, indirizzo, paese) / Sender</div>
                  <div class="text-weight-bold">ReteBio Società Cooperativa Agricola</div>
                  <div>Via della Cooperazione 12 - 40100 Bologna (BO) - ITALIA</div>
                  <div class="text-caption">P.IVA / C.F.: IT01234567890 - Reg. Imprese BO</div>
                </div>

                <div class="cmr-box q-mt-sm">
                  <div class="cmr-box-header">2. Destinatario (nome, indirizzo, paese) / Consignee</div>
                  <div class="text-weight-bold text-primary">{{ selectedCmr?.cliente?.ragione_sociale }}</div>
                  <div>{{ selectedCmr?.cliente?.indirizzo }}</div>
                  <div>{{ selectedCmr?.cliente?.cap }} {{ selectedCmr?.cliente?.citta }} ({{ selectedCmr?.cliente?.nazione }})</div>
                  <div class="text-caption">P.IVA: {{ selectedCmr?.cliente?.partita_iva }}</div>
                </div>
              </div>

              <div class="col-12 col-md-6">
                <div class="cmr-box">
                  <div class="cmr-box-header">3. Luogo previsto per la consegna / Place of delivery</div>
                  <div class="text-weight-bold">{{ selectedCmr?.luogo_consegna }}</div>
                </div>

                <div class="cmr-box q-mt-sm">
                  <div class="cmr-box-header">4. Luogo e data di presa in carico / Place and date of taking over</div>
                  <div class="text-weight-bold text-teal-9">{{ selectedCmr?.luogo_carico }}</div>
                  <div>Data: {{ selectedCmr?.data_documento }}</div>
                </div>

                <div class="cmr-box q-mt-sm">
                  <div class="cmr-box-header">5. Documenti allegati / Documents attached</div>
                  <div>DDT di vendita: <strong>{{ selectedCmr?.delivery_note_numero || 'N.D.' }}</strong></div>
                  <div>Certificato Biologico di Conformità CE</div>
                </div>
              </div>
            </div>

            <!-- Riquadro Merci Caselle 6-12 -->
            <div class="cmr-box q-mb-sm">
              <div class="cmr-box-header">
                6-12. Contrassegni e numeri - Numero dei colli - Modo d'imballaggio - Denominazione della merce - N. Statistico - Peso lordo Kg
              </div>

              <div v-if="selectedCmr?.ha_allegato_righe" class="q-pa-md text-center bg-orange-1 text-deep-orange text-weight-bold">
                *** VEDI DISTINTA ANALITICA MERCI IN ALLEGATO (REGOLA DELLE 21 RIGHE SUPERATA: {{ selectedCmr?.items?.length }} RIGHE TOTALI) ***
              </div>

              <div v-else class="q-pa-xs">
                <table class="full-width cmr-table">
                  <thead>
                    <tr>
                      <th align="left">7. Marchi / Lotti Bio</th>
                      <th align="right">8. N. Colli</th>
                      <th align="left">9. Imballaggio</th>
                      <th align="left">10. Denominazione Merce</th>
                      <th align="center">Codice NC</th>
                      <th align="right">11. Peso Lordo Kg</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="it in selectedCmr?.items" :key="it.id">
                      <td>{{ it.contrassegno_lotto || '-' }}</td>
                      <td align="right">{{ it.numero_colli }}</td>
                      <td>{{ it.modo_imballaggio }}</td>
                      <td><strong>{{ it.natura_merce }}</strong></td>
                      <td align="center">{{ it.codice_nc || '08051020' }}</td>
                      <td align="right">{{ Number(it.peso_lordo_kg).toFixed(1) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- Riquadro Inferiore: Istruzioni / Vettore / Targhe -->
            <div class="row q-col-gutter-sm">
              <div class="col-12 col-md-6">
                <div class="cmr-box">
                  <div class="cmr-box-header">13. Istruzioni del mittente / Sender's instructions</div>
                  <div class="text-italic">{{ selectedCmr?.istruzioni_mittente || "Merci biologiche deperibili a temperatura controllata (+4°C). Origine preferenziale CE." }}</div>
                </div>
              </div>

              <div class="col-12 col-md-6">
                <div class="cmr-box">
                  <div class="cmr-box-header">16. Trasportatore / Carrier</div>
                  <div class="text-weight-bold text-primary">{{ selectedCmr?.vettore?.ragione_sociale || 'LD TRASPORTI SRL' }}</div>
                  <div>Targa Camion / Trattore: <strong>{{ selectedCmr?.targa_automezzo || 'ND' }}</strong></div>
                  <div>Targa Semirimorchio: <strong>{{ selectedCmr?.targa_rimorchio || 'ND' }}</strong></div>
                </div>
              </div>
            </div>
          </div>
        </q-card-section>

        <q-separator />
        <q-card-actions align="right" class="q-pa-md bg-white">
          <q-btn flat label="Chiudi" color="grey" v-close-popup />
          <q-btn color="primary" icon="print" label="Stampa Lettera CMR" @click="printCmr" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- DIALOG MODIFICA DATI TRASPORTO -->
    <q-dialog v-model="editTransportOpen">
      <q-card style="min-width: 500px">
        <q-card-section class="row items-center justify-between">
          <div class="text-h6">Dati Trasporto {{ editingCmr?.numero_completo }}</div>
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>
        <q-separator />

        <q-card-section class="q-gutter-md">
          <q-input v-model="editingCmrForm.luogo_carico" label="Luogo di Carico (Presa in carico)" outlined dense />
          <q-input v-model="editingCmrForm.luogo_consegna" label="Luogo di Consegna Previsto" outlined dense />
          <div class="row q-col-gutter-sm">
            <div class="col-6">
              <q-input v-model="editingCmrForm.targa_automezzo" label="Targa Trattore" outlined dense />
            </div>
            <div class="col-6">
              <q-input v-model="editingCmrForm.targa_rimorchio" label="Targa Rimorchio" outlined dense />
            </div>
          </div>
          <q-input v-model="editingCmrForm.istruzioni_mittente" label="Istruzioni Mittente / Dogana" type="textarea" rows="2" outlined dense />
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat label="Annulla" color="grey" v-close-popup />
          <q-btn label="Salva Modifiche" color="primary" @click="saveTransportEdit" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const cmrs = ref([])
const loading = ref(false)
const searchTerm = ref('')

const cmrViewerOpen = ref(false)
const selectedCmr = ref(null)

const editTransportOpen = ref(false)
const editingCmr = ref(null)
const editingCmrForm = ref({
  luogo_carico: '',
  luogo_consegna: '',
  targa_automezzo: '',
  targa_rimorchio: '',
  istruzioni_mittente: ''
})

const columns = [
  { name: 'numero_completo', label: 'Numero CMR', field: 'numero_completo', align: 'left', sortable: true },
  { name: 'data_documento', label: 'Data', field: 'data_documento', align: 'center', sortable: true },
  { name: 'cliente', label: 'Destinatario Estero', field: row => row.cliente?.ragione_sociale || '', align: 'left' },
  { name: 'hub_carico', label: 'Luogo di Carico', field: 'luogo_carico', align: 'left' },
  { name: 'vettore', label: 'Vettore', field: row => row.vettore?.ragione_sociale || 'LD Trasporti', align: 'left' },
  { name: 'colli_pesi', label: 'Colli & Pesi', align: 'right' },
  { name: 'righe_allegato', label: 'Impaginazione Merci', align: 'center' },
  { name: 'actions', label: 'Azioni', align: 'right' }
]

const fetchCmrs = async () => {
  loading.value = true
  try {
    const params = {}
    if (searchTerm.value) {
      params.search = searchTerm.value
    }
    const res = await axios.get('/api/cmr', { params })
    cmrs.value = res.data
  } catch (err) {
    console.error('Error fetching CMRs:', err)
  } finally {
    loading.value = false
  }
}

const viewCmrModel = (cmr) => {
  selectedCmr.value = cmr
  cmrViewerOpen.value = true
}

const editCmrTransport = (cmr) => {
  editingCmr.value = cmr
  editingCmrForm.value = {
    luogo_carico: cmr.luogo_carico,
    luogo_consegna: cmr.luogo_consegna,
    targa_automezzo: cmr.targa_automezzo || '',
    targa_rimorchio: cmr.targa_rimorchio || '',
    istruzioni_mittente: cmr.istruzioni_mittente || ''
  }
  editTransportOpen.value = true
}

const saveTransportEdit = async () => {
  try {
    await axios.put(`/api/cmr/${editingCmr.value.id}`, editingCmrForm.value)
    editTransportOpen.value = false
    await fetchCmrs()
  } catch (err) {
    alert(err.response?.data?.error || 'Errore salvataggio dati trasporto')
  }
}

const printCmr = () => {
  window.print()
}

const openNewCmrDialog = () => {
  alert("Per emettere un nuovo CMR, genera una bolla DDT verso un cliente estero (es. Belgio) e clicca sul pulsante 'CMR' nella schermata Bollettazione!")
}

onMounted(() => {
  fetchCmrs()
})
</script>

<style scoped>
.cmr-box {
  background: white;
  border: 1px solid #c5cae9;
  border-radius: 4px;
  padding: 8px 12px;
}
.cmr-box-header {
  font-size: 11px;
  text-transform: uppercase;
  color: #3949ab;
  font-weight: bold;
  border-bottom: 1px dashed #e8eaf6;
  margin-bottom: 4px;
  padding-bottom: 2px;
}
.cmr-table {
  border-collapse: collapse;
}
.cmr-table th, .cmr-table td {
  padding: 6px 8px;
  border-bottom: 1px solid #e0e0e0;
  font-size: 13px;
}
</style>
