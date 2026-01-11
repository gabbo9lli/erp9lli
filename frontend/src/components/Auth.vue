<template>
  <div class="auth-wrapper">
    <div class="auth-card">
      <h2>{{ viewTitle }}</h2>
      <p class="subtitle">{{ viewSubtitle }}</p>

      <div class="form-body">
        <div class="input-group">
          <label>Email Address</label>
          <input 
            v-model="form.email" 
            type="email" 
            placeholder="name@company.com"
            :class="{ 'error-border': !isEmailValid && form.email.length > 0 }"
          />
        </div>

        <div v-if="view !== 'forgot'" class="input-group">
          <label>Password</label>
          <input 
            v-model="form.password" 
            type="password" 
            placeholder="••••••••" 
          />
        </div>

        <button 
          @click="handleAction" 
          :disabled="loading || !isEmailValid"
          class="primary-btn"
        >
          {{ loading ? 'Processing...' : actionButtonText }}
        </button>
      </div>

      <div class="auth-footer">
        <template v-if="view === 'login'">
          <p>Don't have an account? <span @click="view = 'signup'">Sign Up</span></p>
          <p class="forgot-link" @click="view = 'forgot'">Forgot password?</p>
        </template>
        
        <template v-else-if="view === 'signup'">
          <p>Already have an account? <span @click="view = 'login'">Sign In</span></p>
        </template>

        <template v-else-if="view === 'forgot'">
          <p @click="view = 'login'">Back to Login</p>
        </template>
      </div>

      <transition name="fade">
        <div v-if="feedback.text" :class="['feedback-msg', feedback.type]">
          {{ feedback.text }}
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'

// State Management
const view = ref('login') // 'login', 'signup', or 'forgot'
const loading = ref(false)
const feedback = reactive({ text: '', type: '' })
const form = reactive({ email: '', password: '' })

// Computed properties for UI strings
const viewTitle = computed(() => {
  if (view.value === 'login') return 'Welcome Back'
  if (view.value === 'signup') return 'Create Account'
  return 'Reset Password'
})

const viewSubtitle = computed(() => {
  if (view.value === 'forgot') return 'Enter your email to receive a reset link.'
  return 'Please enter your details.'
})

const actionButtonText = computed(() => {
  if (view.value === 'login') return 'Sign In'
  if (view.value === 'signup') return 'Get Started'
  return 'Send Reset Link'
})

const isEmailValid = computed(() => {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)
})

// Logic Handlers
const setFeedback = (msg, type = 'error') => {
  feedback.text = msg
  feedback.type = type
  setTimeout(() => { feedback.text = '' }, 5000)
}

const handleAction = async () => {
  loading.value = true
  feedback.text = ''

  const endpoints = {
    login: '/api/login',
    signup: '/api/signup',
    forgot: '/api/forgot-password'
  }

  try {
    const response = await fetch(endpoints[view.value], {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: form.email,
        password: form.password,
      })
    })

    const data = await response.json()

    if (response.ok) {
      if (view.value === 'forgot') {
        setFeedback("Check your email (or console) for the link!", "success")
      } else {
        setFeedback(view.value === 'login' ? "Success! Redirecting..." : "Account created!", "success")
        if (view.value === 'login') {
          localStorage.setItem('user_session', data.user)
          window.dispatchEvent(new CustomEvent('auth-change'));
          router.push('/dashboard');
          // window.location.href = '/dashboard' // Navigate on success
        }
      }
    } else {
      setFeedback(data.error || "Something went wrong")
    }
  } catch (err) {
    setFeedback("Network error. Is the backend running?")
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 60vh;
}

.auth-card {
  width: 100%;
  max-width: 400px;
  padding: 2.5rem;
  background: white;
  border-radius: 12px;
  box-shadow: 0 10px 25px rgba(0,0,0,0.1);
}

h2 { margin-bottom: 0.5rem; color: #2d3436; }
.subtitle { color: #636e72; margin-bottom: 2rem; font-size: 0.9rem; }

.input-group { margin-bottom: 1.5rem; text-align: left; }
.input-group label { display: block; margin-bottom: 0.5rem; font-weight: 600; font-size: 0.85rem; }

input {
  width: 100%;
  padding: 0.8rem;
  border: 1px solid #dfe6e9;
  border-radius: 6px;
  font-size: 1rem;
}

.error-border { border-color: #ff7675; }

.primary-btn {
  width: 100%;
  padding: 0.8rem;
  background: #42b983;
  color: white;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.primary-btn:disabled { background: #b2bec3; cursor: not-allowed; }

.auth-footer { margin-top: 1.5rem; font-size: 0.85rem; }
.auth-footer span, .forgot-link { color: #42b983; cursor: pointer; font-weight: 600; }

.feedback-msg {
  margin-top: 1.5rem;
  padding: 0.8rem;
  border-radius: 6px;
  font-size: 0.85rem;
}

.error { background: #fff5f5; color: #c0392b; border: 1px solid #ff8787; }
.success { background: #f0fff4; color: #27ae60; border: 1px solid #63e6be; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.3s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>