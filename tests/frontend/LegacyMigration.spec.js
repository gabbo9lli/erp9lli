import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import axios from 'axios'
import LegacyMigration from '../../frontend/src/components/LegacyMigration.vue'

describe('LegacyMigration.vue', () => {
  it('renders migration dashboard and controls correctly', async () => {
    const wrapper = mount(LegacyMigration, {
      global: {
        stubs: {
          'q-btn': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
          'q-file': {
            props: ['label', 'hint'],
            template: '<div class="q-file-stub"><label>{{ label }}</label><span>{{ hint }}</span><slot /></div>'
          },
          'q-input': { template: '<input />' },
          'q-card': { template: '<div><slot /></div>' },
          'q-card-section': { template: '<div><slot /></div>' },
          'q-card-actions': { template: '<div><slot /></div>' },
          'q-dialog': { template: '<div><slot /></div>' },
          'q-linear-progress': { template: '<div><slot /></div>' },
          'q-badge': { template: '<span><slot /></span>' },
          'q-banner': { template: '<div><slot /></div>' },
          'q-toggle': { template: '<input type="checkbox" />' },
          'q-radio': { template: '<input type="radio" />' },
          'q-icon': { template: '<i />' },
          'q-separator': { template: '<hr />' },
          'q-table': { template: '<div><slot /></div>' },
          'q-space': { template: '<span />' }
        }
      }
    })
    expect(wrapper.text()).toContain('Inizializzazione & Migrazione Dati Legacy')
    expect(wrapper.text()).toContain('Windows')
  })

  it('allows uploading a file from Windows and triggers upload to server', async () => {
    const uploadSpy = vi.spyOn(axios, 'post').mockImplementation((url) => {
      if (url.includes('/api/migration/upload')) {
        return Promise.resolve({
          data: {
            status: 'success',
            filename: 'GestionaleReteBio2026.accdb',
            file_path: '/tmp/legacy_uploads/20261028_GestionaleReteBio2026.accdb',
            file_size_bytes: 1048576,
            file_size_mb: 1.0
          }
        })
      }
      return Promise.resolve({ data: {} })
    })

    const wrapper = mount(LegacyMigration, {
      global: {
        stubs: {
          'q-btn': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
          'q-file': {
            name: 'q-file',
            props: ['modelValue', 'label', 'hint'],
            emits: ['update:modelValue'],
            template: '<div class="q-file-stub"><label>{{ label }}</label><span>{{ hint }}</span><slot /></div>'
          },
          'q-input': { template: '<input />' },
          'q-card': { template: '<div><slot /></div>' },
          'q-card-section': { template: '<div><slot /></div>' },
          'q-card-actions': { template: '<div><slot /></div>' },
          'q-dialog': { template: '<div><slot /></div>' },
          'q-linear-progress': { template: '<div><slot /></div>' },
          'q-badge': { template: '<span><slot /></span>' },
          'q-banner': { template: '<div><slot /></div>' },
          'q-toggle': { template: '<input type="checkbox" />' },
          'q-radio': { template: '<input type="radio" />' },
          'q-icon': { template: '<i />' },
          'q-separator': { template: '<hr />' },
          'q-table': { template: '<div><slot /></div>' },
          'q-space': { template: '<span />' }
        }
      }
    })

    const dummyFile = new File(['dummy binary content'], 'GestionaleReteBio2026.accdb', { type: 'application/x-msaccess' })
    const qFile = wrapper.findComponent({ name: 'q-file' })
    expect(qFile.exists()).toBe(true)
    await qFile.vm.$emit('update:modelValue', dummyFile)
    await flushPromises()

    expect(uploadSpy).toHaveBeenCalledWith(
      '/api/migration/upload',
      expect.any(FormData),
      expect.any(Object)
    )
    expect(wrapper.text()).toContain('Caricato sul server')
  })

  it('runs dry run and displays statistical preview', async () => {
    vi.spyOn(axios, 'post').mockImplementation((url) => {
      if (url.includes('/api/migration/upload')) {
        return Promise.resolve({
          data: {
            status: 'success',
            filename: 'GestionaleReteBio2026.accdb',
            file_path: '/tmp/legacy_uploads/GestionaleReteBio2026.accdb',
            file_size_bytes: 1048576,
            file_size_mb: 1.0
          }
        })
      }
      if (url.includes('/api/migration/dry-run')) {
        return Promise.resolve({
          data: {
            status: 'success',
            source_file: 'GestionaleReteBio2026.accdb',
            partners_count: 180,
            products_count: 3200,
            stock_lots_count: 324,
            delivery_notes_count: 67,
            invoices_count: 850,
            installments_count: 1600,
            estimated_seconds: 15
          }
        })
      }
      return Promise.resolve({ data: {} })
    })

    const wrapper = mount(LegacyMigration, {
      global: {
        stubs: {
          'q-btn': {
            props: ['label'],
            template: '<button @click="$emit(\'click\')">{{ label }}<slot /></button>'
          },
          'q-file': {
            name: 'q-file',
            props: ['modelValue', 'label', 'hint'],
            emits: ['update:modelValue'],
            template: '<div class="q-file-stub"><label>{{ label }}</label><span>{{ hint }}</span><slot /></div>'
          },
          'q-input': { template: '<input />' },
          'q-card': { template: '<div><slot /></div>' },
          'q-card-section': { template: '<div><slot /></div>' },
          'q-card-actions': { template: '<div><slot /></div>' },
          'q-dialog': { template: '<div><slot /></div>' },
          'q-linear-progress': { template: '<div><slot /></div>' },
          'q-badge': { template: '<span><slot /></span>' },
          'q-banner': { template: '<div><slot /></div>' },
          'q-toggle': { template: '<input type="checkbox" />' },
          'q-radio': { template: '<input type="radio" />' },
          'q-icon': { template: '<i />' },
          'q-separator': { template: '<hr />' },
          'q-table': { template: '<div><slot /></div>' },
          'q-space': { template: '<span />' }
        }
      }
    })

    // First select/upload file
    const dummyFile = new File(['dummy'], 'GestionaleReteBio2026.accdb')
    const qFile = wrapper.findComponent({ name: 'q-file' })
    await qFile.vm.$emit('update:modelValue', dummyFile)
    await flushPromises()

    const dryRunBtn = wrapper.findAll('button').find(b => b.text().includes('Analizza') || b.text().includes('Dry Run'))
    expect(dryRunBtn).toBeDefined()
    await dryRunBtn.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('180')
    expect(wrapper.text()).toContain('3200')
    expect(wrapper.text()).toContain('67')
    expect(wrapper.text()).toContain('DDT')
  })
})
