import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    // 1. Listen on all addresses so Docker can map the port
    host: '0.0.0.0', 
    port: 5173,
    
    // 2. Configure Hot Module Replacement (HMR) for Docker/WSL
    watch: {
      usePolling: true,
    },

    // 3. The Proxy: This solves the "localhost:5000" vs "backend:5000" problem
    proxy: {
      '/api': {
        target: 'http://backend:5000', // Use the Docker service name of your Flask app
        changeOrigin: true,
        secure: false,
      }
    }
  }
})