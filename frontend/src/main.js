import { createApp } from 'vue'
import App from './App.vue'
import axios from 'axios'
import { router } from './router'

const app = createApp(App)

// Optional: Set a base URL so you don't type it every time
axios.defaults.baseURL = 'http://localhost:5000'

app.use(router).mount('#app')