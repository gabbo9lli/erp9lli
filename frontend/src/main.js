import { createApp } from 'vue'
import App from './App.vue'
import axios from 'axios'
import { Quasar, Notify, Dialog } from 'quasar' // Import them here
import { router } from './router'

import 'quasar/dist/quasar.css'

const app = createApp(App)

// Optional: Set a base URL so you don't type it every time
axios.defaults.baseURL = 'http://localhost:5000'

app.use(Quasar, {
  plugins: {
    Notify, // Register it here
    Dialog
  }
})
app.use(router).mount('#app')