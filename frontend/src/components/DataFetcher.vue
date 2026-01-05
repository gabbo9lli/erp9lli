<template>
  <div>
    <h2>Backend Status</h2>
    <p class="api-url">API URL used: <strong>{{ apiUrl }}</strong></p>

    <p v-if="loading">Connecting to Flask backend...</p>
    <div v-else-if="error" class="error-message">
      Error: {{ error }} <br>
      Is the Flask container running on the correct port?
    </div>
    <div v-else class="success-message">
      ✅ Success! Message: **{{ message }}**
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'DataFetcher',
  data() {
    return {
      // Use the environment variable injected by Vue CLI/Vite
      // It will be 'http://localhost:5000/' for Dev and '/api/' for Prod.
      apiUrl: process.env.VUE_APP_API_URL, 
      message: '',
      loading: true,
      error: null,
    };
  },
  methods: {
    async fetchData() {
      if (!this.apiUrl) {
        this.error = 'VUE_APP_API_URL is not defined in the environment.';
        this.loading = false;
        return;
      }
      
      const endpoint = `${this.apiUrl}`; 
      
      try {
        const response = await axios.get(endpoint);
        this.message = response.data.message;
        this.loading = false;
      } catch (err) {
        this.error = err.message || 'Unknown network error.';
        console.error('API Error:', err);
        this.loading = false;
      }
    },
  },
  mounted() {
    this.fetchData();
  },
};
</script>

<style scoped>
.error-message {
  color: red;
  border: 1px solid red;
  padding: 10px;
}
.success-message {
  color: green;
  font-size: 1.1em;
  padding: 10px;
}
.api-url {
  font-size: 0.8em;
  margin-bottom: 20px;
}
</style>