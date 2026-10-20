<template>
  <div class="portal">
    <div class="navbar">
      <div class="nav-left">
        <div class="logo">DevPortal</div>
          <template v-if="isLoggedIn" class="navbar">
            <router-link to="/healthcheck" class="nav-item">Health Check</router-link>
            <router-link to="/users" class="nav-item">Users</router-link>
            <router-link to="/partners" class="nav-item">Soggetti</router-link>
            <router-link to="/products" class="nav-item">Articoli</router-link>
            <router-link to="/delivery-notes" class="nav-item">Bolle (DDT)</router-link>
            <router-link to="/invoices" class="nav-item">Fatture</router-link>
            <router-link to="/accounting" class="nav-item">Contabilità</router-link>
            <router-link to="/database" class="nav-item">Database</router-link>
          </template>
      </div>

      <div class="nav-right">
        <div class="user-menu" v-if="isLoggedIn">
          <router-link to="/settings" class="username-link">
            <span class="user-icon">👤</span> {{ currentUser }} <span v-if="userRole" class="role-badge">[{{ userRole }}]</span>
          </router-link>
          <button @click="handleLogout" class="logout-btn">Logout</button>
        </div>
        <div class="login-prompt" v-else>
          <a href="/oauth2/start?rd=/dashboard" class="login-link">Accedi</a>
        </div>
      </div>
    </div>

    <main class="content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const isLoggedIn = ref(false)
const currentUser = ref('')
const userRole = ref('')

onUnmounted(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('auth-change', checkAuth)
  }
})

const checkAuth = async () => {
  try {
    const res = await fetch('/api/me')
    if (res.ok) {
      const data = await res.json()
      if (data.authenticated) {
        isLoggedIn.value = true
        currentUser.value = data.username || data.email
        userRole.value = data.role || 'User'
        if (typeof window !== 'undefined' && window.localStorage) {
          window.localStorage.setItem('user_session', currentUser.value)
        }
        return
      }
    }
  } catch (err) {
    // Ignore fetch error
  }

  const session = (typeof window !== 'undefined' && window.localStorage) 
    ? window.localStorage.getItem('user_session') 
    : null
  isLoggedIn.value = !!session
  currentUser.value = session || ''
}

onMounted(() => {
  checkAuth()
  if (typeof window !== 'undefined') {
    window.addEventListener('auth-change', checkAuth)
  }
})

const handleLogout = () => {
  if (typeof window !== 'undefined' && window.localStorage) {
    window.localStorage.removeItem('user_session')
  }
  isLoggedIn.value = false
  currentUser.value = ''
  if (typeof window !== 'undefined' && window.location) {
    window.location.href = '/oauth2/sign_out?rd=/'
  }
}
</script>

<style scoped>
.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 2rem;
  height: 60px;
  background: #2c3e50;
  color: white;
}
.nav-left, .nav-right { display: flex; align-items: center; gap: 20px; }
.nav-item, .username-link {
  color: #bdc3c7;
  text-decoration: none;
  font-size: 0.9rem;
}
.router-link-active { color: #42b983; font-weight: bold; }
.user-icon { margin-right: 5px; }
.logout-btn {
  background: #e74c3c;
  border: none;
  color: white;
  padding: 5px 10px;
  border-radius: 4px;
  cursor: pointer;
}
</style>