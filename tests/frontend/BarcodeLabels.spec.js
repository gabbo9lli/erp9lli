import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import BarcodeLabelsDialog from '../../frontend/src/components/BarcodeLabelsDialog.vue'

describe('BarcodeLabelsDialog.vue', () => {
  it('renders thermal pallet label preview and actions', async () => {
    const mockLabel = {
      label_type: 'pallet',
      barcode_value: 'BIO-MELA-LOTTO-01',
      zpl: '^XA^PW800^LL1200^FDMele Gala Bio^FS^XZ',
      svg_barcode: '<svg><rect x="0" y="0" width="10" height="50" /></svg>',
      html_preview: '<div class="pallet-label">Mele Gala Bio</div>',
      dati: {
        descrizione: 'Mele Gala Bio',
        lotto: 'LOTTO-01',
        colli: 48,
        peso_netto: 480.0
      }
    }

    const wrapper = mount(BarcodeLabelsDialog, {
      props: {
        modelValue: true,
        labels: [mockLabel],
        title: 'Etichette DDT-2026-0001'
      },
      global: {
        stubs: {
          'q-dialog': { template: '<div><slot /></div>' },
          'q-card': { template: '<div><slot /></div>' },
          'q-card-section': { template: '<div><slot /></div>' },
          'q-card-actions': { template: '<div><slot /></div>' },
          'q-btn': true,
          'q-btn-toggle': true,
          'q-icon': true,
          'q-chip': true,
          'q-badge': true,
          'q-separator': true
        }
      }
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Etichette DDT-2026-0001')
    expect(wrapper.text()).toContain('Mele Gala Bio')
    expect(wrapper.html()).toContain('pallet-label')
  })
})
