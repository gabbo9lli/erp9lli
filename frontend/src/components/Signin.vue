
<template>
    <div class="portal-container">
        <div class="auth-card">
        <h2>{{ isLogin ? 'Sign In' : 'Sign Up' }}</h2>
        
        <form @submit.prevent="handleAuth">
            <input v-model="email" type="email" placeholder="Email" required />
            <input v-model="password" type="password" placeholder="Password" required />
            <button type="submit">{{ isLogin ? 'Login' : 'Create Account' }}</button>
        </form>

        <p @click="isLogin = !isLogin" class="toggle-link">
            {{ isLogin ? "Don't have an account? Sign Up" : "Already have an account? Sign In" }}
        </p>

        <p v-if="message" class="status-msg">{{ message }}</p>
        </div>
    </div>
</template>

<style scoped>
.portal-container { display: flex; justify-content: center; align-items: center; height: 100vh; background: #f0f2f5; }
.auth-card { background: white; padding: 2rem; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 300px; }
input { width: 100%; margin-bottom: 1rem; padding: 10px; box-sizing: border-box; }
button { width: 100%; padding: 10px; background: #42b983; color: white; border: none; cursor: pointer; }
.toggle-link { color: #2c3e50; cursor: pointer; font-size: 0.8rem; margin-top: 1rem; text-decoration: underline; }
.status-msg { font-size: 0.9rem; color: #e74c3c; margin-top: 10px; }
</style>

<script setup>
import { ref } from 'vue'
import axios from 'axios'

const isLogin = ref(true)
const email = ref('')
const password = ref('')
const message = ref('')

const handleAuth = async () => {
  const endpoint = isLogin.value ? '/api/signin' : '/api/signup'
  try {
    const response = await axios.post(endpoint, {
      email: email.value,
      password: password.value
    })
    
    if (isLogin.value) {
      localStorage.setItem('token', response.data.access_token)
      message.value = "Successfully Signed In!"
    } else {
      message.value = "Successfully Signed Up! Please Sign In."
      isLogin.value = true
    }
  } catch (err) {
    message.value = err.response?.data?.msg || "An error occurred"
  }
}
</script>