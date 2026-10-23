<template>
  <q-dialog :model-value="modelValue" @update:model-value="val => $emit('update:modelValue', val)" full-width full-height>
    <q-card class="column full-height" style="max-width: 900px; margin: auto;">
      <!-- HEADER -->
      <q-card-section class="row items-center justify-between bg-primary text-white q-py-sm">
        <div class="row items-center q-gutter-sm">
          <q-icon name="qr_code_2" size="28px" />
          <div class="text-h6 text-weight-bold">{{ title || 'Etichette Barcode Termiche' }}</div>
          <q-badge color="teal" v-if="labels && labels.length">
            {{ currentIndex + 1 }} di {{ labels.length }} etichette
          </q-badge>
        </div>
        <q-btn icon="close" flat round dense v-close-popup />
      </q-card-section>

      <!-- BODY: ANTEPRIMA ETICHETTA -->
      <q-card-section class="col q-pa-md scroll bg-grey-2 flex flex-center">
        <div v-if="currentLabel" class="column items-center">
          <!-- NAVIGATORE ETICHETTE -->
          <div v-if="labels.length > 1" class="row items-center q-gutter-md q-mb-md">
            <q-btn round dense flat icon="chevron_left" color="primary" :disable="currentIndex === 0" @click="currentIndex--" />
            <span class="text-subtitle2 text-weight-bold">Etichetta {{ currentIndex + 1 }} / {{ labels.length }}</span>
            <q-btn round dense flat icon="chevron_right" color="primary" :disable="currentIndex === labels.length - 1" @click="currentIndex++" />
          </div>

          <!-- ANTEPRIMA GRAFICA TERMICA -->
          <div class="shadow-3 rounded-borders bg-white print-area" v-html="currentLabel.html_preview"></div>
        </div>
        <div v-else class="text-grey-7 text-center q-pa-xl">
          <q-icon name="error_outline" size="48px" />
          <div>Nessuna etichetta disponibile.</div>
        </div>
      </q-card-section>

      <!-- ACTIONS & CONTROLLI -->
      <q-card-actions align="between" class="bg-white q-pa-md border-top">
        <div class="row q-gutter-sm">
          <q-btn
            outline
            color="primary"
            icon="content_copy"
            label="Copia ZPL"
            @click="copyZpl"
            :disable="!currentLabel"
          />
          <q-btn
            outline
            color="primary"
            icon="download"
            label="Scarica ZPL (.txt)"
            @click="downloadZpl"
            :disable="!currentLabel"
          />
        </div>

        <div class="row q-gutter-sm">
          <q-btn flat label="Chiudi" color="grey" v-close-popup />
          <q-btn
            color="positive"
            icon="print"
            label="Stampa Termica (Browser)"
            @click="printBrowser"
            :disable="!currentLabel"
          />
        </div>
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  labels: {
    type: Array,
    default: () => []
  },
  title: {
    type: String,
    default: 'Etichette Barcode Termiche'
  }
})

defineEmits(['update:modelValue'])

const currentIndex = ref(0)

watch(() => props.labels, (newVal) => {
  currentIndex.value = 0
}, { immediate: true })

const currentLabel = computed(() => {
  if (!props.labels || props.labels.length === 0) return null
  return props.labels[currentIndex.value] || props.labels[0]
})

const copyZpl = async () => {
  if (!currentLabel.value?.zpl) return
  try {
    await navigator.clipboard.writeText(currentLabel.value.zpl)
    alert('Codice ZPL copiato negli appunti!')
  } catch (err) {
    alert('Errore copia appunti: ' + err)
  }
}

const downloadZpl = () => {
  if (!currentLabel.value?.zpl) return
  const blob = new Blob([currentLabel.value.zpl], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `etichetta_${currentLabel.value.barcode_value || 'barcode'}.zpl`
  a.click()
  URL.revokeObjectURL(url)
}

const printBrowser = () => {
  window.print()
}
</script>

<style>
@media print {
  body * {
    visibility: hidden;
  }
  .print-area, .print-area * {
    visibility: visible;
  }
  .print-area {
    position: absolute;
    left: 0;
    top: 0;
    width: 100%;
    margin: 0;
    padding: 0;
    box-shadow: none !important;
  }
}
</style>
