import { createRouter, createWebHistory } from 'vue-router'
import Auth from './components/Auth.vue'
import HealthCheck from './components/HealthCheck.vue'
import UserManagement from './components/UserManagement.vue'
import DatabaseExplorer from './components/DatabaseExplorer.vue'
import UserManagement2 from './components/UserManagement2.vue'
import PartnerManagement from './components/PartnerManagement.vue'
import ProductCatalog from './components/ProductCatalog.vue'
import DeliveryNotes from './components/DeliveryNotes.vue'
import Invoices from './components/Invoices.vue'
import Accounting from './components/Accounting.vue'
import Orders from './components/Orders.vue'
import Purchases from './components/Purchases.vue'
import WarehouseStock from './components/WarehouseStock.vue'
import Pallets from './components/Pallets.vue'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', component: Auth },
  { path: '/auth', component: Auth },
  { path: '/healthcheck', component: HealthCheck, meta: { requiresAuth: true } },
  { path: '/users', component: UserManagement2, meta: { requiresAuth: true } },
  { path: '/partners', component: PartnerManagement, meta: { requiresAuth: true } },
  { path: '/products', component: ProductCatalog, meta: { requiresAuth: true } },
  { path: '/orders', component: Orders, meta: { requiresAuth: true } },
  { path: '/delivery-notes', component: DeliveryNotes, meta: { requiresAuth: true } },
  { path: '/purchases', component: Purchases, meta: { requiresAuth: true } },
  { path: '/warehouse', component: WarehouseStock, meta: { requiresAuth: true } },
  { path: '/pallets', component: Pallets, meta: { requiresAuth: true } },
  { path: '/invoices', component: Invoices, meta: { requiresAuth: true } },
  { path: '/accounting', component: Accounting, meta: { requiresAuth: true } },
  { path: '/database', component: DatabaseExplorer, meta: { requiresAuth: true } },
  { path: '/settings', component: () => import('./components/Settings.vue'), meta: { requiresAuth: true }},
  { path: '/users2', redirect: '/users' },
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
