import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  server: {
    fs: {
      allow: ['..']
    }
  },
  test: {
    globals: true,
    environment: 'happy-dom',
    include: [
      '../tests/frontend/**/*.{test,spec}.{js,ts}'
    ]
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@vue/test-utils': path.resolve(__dirname, './node_modules/@vue/test-utils'),
      'vue': path.resolve(__dirname, './node_modules/vue')
    }
  }
})
