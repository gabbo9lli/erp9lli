import { createApp } from 'vue'
import App from './App.vue'
import axios from 'axios'
import { Quasar, Notify, Dialog } from 'quasar' // Import them here
import { router } from './router'

import 'quasar/dist/quasar.css'

const app = createApp(App)

// Configura baseURL opzionale se definita da VITE_API_URL (altrimenti usa relative path /api)
if (import.meta.env.VITE_API_URL) {
  axios.defaults.baseURL = import.meta.env.VITE_API_URL
}

app.use(Quasar, {
  plugins: {
    Notify, // Register it here
    Dialog
  }
})
app.use(router).mount('#app')