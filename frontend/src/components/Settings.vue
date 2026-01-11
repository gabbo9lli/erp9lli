<template>
  <div class="settings-page">
    <h2>Personal Configurations</h2>
    <div class="settings-card">
      <div class="setting-item">
        <label>Email Address (Account ID)</label>
        <input type="text" :value="currentUser" disabled />
      </div>
      
      <div class="setting-item">
        <label>Interface Theme</label>
        <select v-model="config.theme">
          <option value="light">Light Mode</option>
          <option value="dark">Dark Mode</option>
        </select>
      </div>

      <button @click="saveSettings" class="save-btn">Save Configurations</button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'

const currentUser = ref(localStorage.getItem('user_session'))
const config = reactive({
  theme: 'light'
})

const saveSettings = () => {
  // Save to local storage or send to /api/user/settings
  localStorage.setItem('user_config', JSON.stringify(config))
  alert('Settings saved locally!')
}

onMounted(() => {
  const saved = localStorage.getItem('user_config')
  if (saved) Object.assign(config, JSON.parse(saved))
})
</script>

<style scoped>
.settings-card {
  max-width: 500px;
  background: #f8f9fa;
  padding: 2rem;
  border-radius: 8px;
  border: 1px solid #dee2e6;
}
.setting-item { margin-bottom: 1.5rem; display: flex; flex-direction: column; }
.setting-item label { font-weight: bold; margin-bottom: 0.5rem; }
input:disabled { background: #e9ecef; cursor: not-allowed; }
.save-btn { background: #42b983; color: white; border: none; padding: 10px; cursor: pointer; border-radius: 4px; }
</style>