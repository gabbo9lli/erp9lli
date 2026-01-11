<template>
  <div class="portal">
    <div class="navbar">
      <div class="nav-left">
        <div class="logo">DevPortal</div>
          <template v-if="isLoggedIn" class="navbar">
            <router-link to="/healthcheck" class="nav-item">Healthchek</router-link>
            <router-link to="/users" class="nav-item">Users</router-link>
            <router-link to="/database" class="nav-item">Database</router-link>
          </template>
      </div>

      <div class="nav-right">
        <div class="user-menu">
          <router-link to="/settings" class="username-link">
            <span class="user-icon">👤</span> {{ currentUser }}
          </router-link>
          <button @click="handleLogout" class="logout-btn">Logout</button>
        </div>
      </div>
    </div>

    <main class="content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const isLoggedIn = ref(false)
const currentUser = ref('')

onUnmounted(() => {
  // Clean up listener to prevent memory leaks
  window.removeEventListener('auth-change', checkAuth);
});

const checkAuth = () => {
  const session = localStorage.getItem('user_session')
  isLoggedIn.value = !!session
  currentUser.value = session || ''
}

// onMounted(checkAuth)
// watch(() => route.path, checkAuth)
onMounted(() => {
  checkAuth();
  // Listen for the login event
  window.addEventListener('auth-change', checkAuth);
});

const handleLogout = () => {
  localStorage.removeItem('user_session')
  checkAuth()
  router.push('/auth')
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