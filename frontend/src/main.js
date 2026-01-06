import { createApp } from 'vue'
import App from './App.vue'
import axios from 'axios'

const app = createApp(App)

// Optional: Set a base URL so you don't type it every time
axios.defaults.baseURL = 'http://localhost:5000'

app.mount('#app')