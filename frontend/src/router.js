import { createRouter, createWebHistory } from 'vue-router'
import Auth from './components/Auth.vue'
import HealthCheck from './components/HealthCheck.vue'
import UserManagement from './components/UserManagement.vue'
import DatabaseExplorer from './components/DatabaseExplorer.vue'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', component: Auth },
  { path: '/auth', component: Auth },
  { path: '/healthcheck', component: HealthCheck, meta: { requiresAuth: true } },
  { path: '/users', component: UserManagement, meta: { requiresAuth: true } },
  { path: '/database', component: DatabaseExplorer, meta: { requiresAuth: true } },
  { path: '/settings', component: () => import('./components/Settings.vue'), meta: { requiresAuth: true }},
]

export const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const isAuthenticated = !!localStorage.getItem('user_session')

  if (to.meta.requiresAuth && !isAuthenticated) {
    // If route is protected and user is not logged in, send to login
    next('/auth')
  } else if (to.path === '/auth' && isAuthenticated) {
    // If already logged in, don't let them go back to login page
    next('/dashboard')
  } else {
    next()
  }
})
