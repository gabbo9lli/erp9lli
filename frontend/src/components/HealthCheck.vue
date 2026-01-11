<template>
  <div class="health-card">
    <h3>System Health Check</h3>
    <button @click="checkHealth" :disabled="loading">
      {{ loading ? 'Checking...' : 'Refresh Status' }}
    </button>

    <div class="status-grid">
      <div class="status-item">
        <span>Flask API:</span>
        <span :class="data.flask_status === 'UP' ? 'ok' : 'error'">
          {{ data.flask_status || 'OFFLINE' }}
        </span>
      </div>

      <div class="status-item">
        <span>Database Type:</span>
        <span class="info">{{ data.database?.type }}</span>
      </div>

      <div class="status-item">
        <span>DB Connection:</span>
        <span :class="data.database?.status === 'UP' ? 'ok' : 'error'">
          {{ data.database?.status || 'DOWN' }}
        </span>
      </div>
    </div>

    <p v-if="data.database?.connection_error" class="err-msg">
      Error: {{ data.database.connection_error }}
    </p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const data = ref({})
const loading = ref(false)

const checkHealth = async () => {
  loading.value = true
  try {
    const res = await fetch('http://localhost:5000/api/health')
    data.value = await res.json()
  } catch (err) {
    data.value = { flask_status: 'DOWN' }
  } finally {
    loading.value = false
  }
}

onMounted(checkHealth)
</script>

<style scoped>
.health-card { border: 1px solid #ccc; padding: 1rem; border-radius: 8px; max-width: 400px; }
.status-grid { margin-top: 1rem; display: grid; gap: 0.5rem; }
.ok { color: green; font-weight: bold; }
.error { color: red; font-weight: bold; }
.info { color: blue; }
.err-msg { font-size: 0.8rem; color: red; margin-top: 10px; }
</style>