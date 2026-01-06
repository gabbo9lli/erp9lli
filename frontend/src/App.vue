<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

// Reactive variables to store state
const message = ref('Waiting for Flask...')
const status = ref('loading') // 'loading', 'success', or 'error'

const fetchData = async () => {
  try {
    // We use /api because of the vite.config.js proxy
    const response = await axios.get('/api/hello')
    
    // Update our variables with the Flask response
    message.value = response.data.message
    status.value = 'success'
  } catch (err) {
    console.error("Connection Error:", err)
    message.value = "Failed to connect to Flask backend."
    status.value = 'error'
  }
}

// Call the function when the component loads
onMounted(() => {
  fetchData()
})
</script>

<template>
  <main class="container">
    <h1>Vue + Flask Interaction</h1>

    <div :class="['card', status]">
      <p v-if="status === 'loading'">⏳ Connecting to backend...</p>
      <p v-else-if="status === 'success'">✅ Backend says: <strong>{{ message }}</strong></p>
      <p v-else>❌ Error: {{ message }}</p>
    </div>

    <button @click="fetchData">Refresh Data</button>
  </main>
</template>

<style scoped>
.container {
  font-family: sans-serif;
  text-align: center;
  margin-top: 50px;
}
.card {
  padding: 20px;
  border-radius: 8px;
  display: inline-block;
  margin: 20px;
  border: 1px solid #ccc;
}
.success { background-color: #e6fffa; border-color: #38b2ac; }
.error { background-color: #fff5f5; border-color: #feb2b2; }
button { padding: 10px 20px; cursor: pointer; }
</style>