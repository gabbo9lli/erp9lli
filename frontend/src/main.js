import { createApp } from 'vue'
import App from './App.vue'
import axios from 'axios'
import { Quasar, Notify, Dialog, Dark } from 'quasar'
import { router } from './router'

import '@quasar/extras/material-icons/material-icons.css'
import 'quasar/dist/quasar.css'

const app = createApp(App)

// Configura baseURL opzionale se definita da VITE_API_URL (altrimenti usa relative path /api)
if (import.meta.env.VITE_API_URL) {
  axios.defaults.baseURL = import.meta.env.VITE_API_URL
}

// Interceptor globale per iniettare automaticamente il Bearer Token JWT salvato in localStorage
axios.interceptors.request.use((config) => {
  const token = (typeof window !== 'undefined' && window.localStorage) ? window.localStorage.getItem('token') : null
  if (token && !config.headers['Authorization']) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
}, (error) => {
  return Promise.reject(error)
})

app.use(Quasar, {
  plugins: {
    Notify,
    Dialog,
    Dark
  }
})
app.use(router).mount('#app')