import axios from 'axios';

// Use environment variable for the base URL
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:5000',
  headers: {
    'Content-Type': 'application/json'
  }
});

export default {
  getHello() {
    return apiClient.get('/api/hello');
  }
}