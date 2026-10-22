<template>
  <q-layout view="lHh Lpr lFf" class="portal-layout">
    <!-- BARRA SUPERIORE (HEADER) -->
    <q-header elevated class="bg-primary text-white">
      <q-toolbar class="q-px-md">
        <q-btn
          v-if="isLoggedIn"
          flat
          dense
          round
          icon="menu"
          aria-label="Toggle Menu"
          @click="leftDrawerOpen = !leftDrawerOpen"
          class="q-mr-sm"
        />

        <div class="row items-center q-gutter-xs cursor-pointer" @click="$router.push('/')">
          <q-avatar size="32px" color="white" text-color="primary" icon="eco" />
          <div class="q-ml-sm">
            <div class="text-weight-bolder text-subtitle1 leading-tight">erp9lli</div>
            <div class="text-caption text-grey-3" style="font-size: 10px; line-height: 1">Gestionale ReteBio</div>
          </div>
        </div>

        <q-space />

        <!-- Toggle Dark Mode -->
        <q-btn
          flat
          round
          dense
          :icon="$q?.dark?.isActive ? 'light_mode' : 'dark_mode'"
          @click="$q?.dark?.toggle()"
          class="q-mr-sm"
        >
          <q-tooltip>{{ $q?.dark?.isActive ? 'Modalità Chiara' : 'Modalità Scura' }}</q-tooltip>
        </q-btn>

        <!-- Menu Utente Autenticato -->
        <div v-if="isLoggedIn" class="row items-center q-gutter-sm user-menu">
          <q-btn flat no-caps class="q-px-sm text-white username-link">
            <q-avatar size="30px" color="teal-7" text-color="white" icon="person" class="q-mr-xs user-icon" />
            <div class="text-left">
              <div class="text-weight-bold text-caption text-white">{{ currentUser }}</div>
              <div v-if="userRole" class="text-grey-3 text-caption role-badge" style="font-size: 10px">[{{ userRole }}]</div>
            </div>
            <q-menu auto-close>
              <q-list style="min-width: 160px">
                <q-item clickable to="/settings">
                  <q-item-section avatar><q-icon name="settings" /></q-item-section>
                  <q-item-section>Impostazioni</q-item-section>
                </q-item>
                <q-separator />
                <q-item clickable @click="handleLogout" class="text-negative">
                  <q-item-section avatar><q-icon name="logout" /></q-item-section>
                  <q-item-section>Esci</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
          </q-btn>

          <q-btn
            flat
            round
            dense
            icon="logout"
            color="white"
            class="logout-btn"
            @click="handleLogout"
          >
            <q-tooltip>Logout</q-tooltip>
          </q-btn>
        </div>

        <!-- Link Accesso se anonimo -->
        <div v-else class="login-prompt">
          <a href="/oauth2/start?rd=/dashboard" class="login-link text-white text-weight-bold">
            <q-btn color="secondary" label="Accedi con OIDC / SSO" icon="login" dense no-caps class="q-px-sm" />
          </a>
        </div>
      </q-toolbar>
    </q-header>

    <!-- SIDEBAR LATERALE (DRAWER) -->
    <q-drawer
      v-if="isLoggedIn"
      v-model="leftDrawerOpen"
      show-if-above
      bordered
      :width="260"
      class="bg-grey-1"
    >
      <q-scroll-area class="fit">
        <q-list padding class="text-grey-8">
          <!-- DASHBOARD -->
          <q-item clickable v-ripple to="/dashboard" active-class="text-primary bg-blue-1 text-weight-bold">
            <q-item-section avatar>
              <q-icon name="dashboard" />
            </q-item-section>
            <q-item-section>Dashboard</q-item-section>
          </q-item>

          <q-separator class="q-my-sm" />

          <!-- CICLO ATTIVO / VENDITE -->
          <template v-if="activeModules.orders || activeModules.delivery_notes || activeModules.invoicing">
            <q-item-label header class="text-weight-bold text-uppercase text-caption text-grey-7">
              Ciclo Attivo (Vendite)
            </q-item-label>

            <q-item v-if="activeModules.orders" clickable v-ripple to="/orders" active-class="text-primary bg-blue-1 text-weight-bold">
              <q-item-section avatar>
                <q-icon name="shopping_cart" />
              </q-item-section>
              <q-item-section>Ordini Clienti</q-item-section>
            </q-item>

            <q-item v-if="activeModules.delivery_notes" clickable v-ripple to="/delivery-notes" active-class="text-primary bg-blue-1 text-weight-bold">
              <q-item-section avatar>
                <q-icon name="local_shipping" />
              </q-item-section>
              <q-item-section>Bolle (DDT)</q-item-section>
            </q-item>

            <q-item v-if="activeModules.pos !== false" clickable v-ripple to="/bancom" active-class="text-primary bg-blue-1 text-weight-bold">
              <q-item-section avatar>
                <q-icon name="point_of_sale" />
              </q-item-section>
              <q-item-section>Vendita Banco (POS)</q-item-section>
            </q-item>

            <q-item v-if="activeModules.invoicing" clickable v-ripple to="/invoices" active-class="text-primary bg-blue-1 text-weight-bold">
              <q-item-section avatar>
                <q-icon name="receipt_long" />
              </q-item-section>
              <q-item-section>Fatture & Scadenzario</q-item-section>
            </q-item>

            <q-separator class="q-my-sm" />
          </template>

          <!-- LOGISTICA & MAGAZZINO -->
          <template v-if="activeModules.warehouse || activeModules.pallets || activeModules.cmr">
            <q-item-label header class="text-weight-bold text-uppercase text-caption text-grey-7">
              Logistica & Magazzino
            </q-item-label>

            <q-item v-if="activeModules.warehouse" clickable v-ripple to="/purchases" active-class="text-primary bg-blue-1 text-weight-bold">
              <q-item-section avatar>
                <q-icon name="move_to_inbox" />
              </q-item-section>
              <q-item-section>Entrata Merci (Carichi)</q-item-section>
            </q-item>

            <q-item v-if="activeModules.warehouse" clickable v-ripple to="/warehouse" active-class="text-primary bg-blue-1 text-weight-bold">
              <q-item-section avatar>
                <q-icon name="inventory_2" />
              </q-item-section>
              <q-item-section>Giacenze & Lotti FEFO</q-item-section>
            </q-item>

            <q-item v-if="activeModules.pallets" clickable v-ripple to="/pallets" active-class="text-primary bg-blue-1 text-weight-bold">
              <q-item-section avatar>
                <q-icon name="layers" />
              </q-item-section>
              <q-item-section>Interscambio Pallet (L.182)</q-item-section>
            </q-item>

            <q-item v-if="activeModules.cmr" clickable v-ripple to="/cmr" active-class="text-primary bg-blue-1 text-weight-bold">
              <q-item-section avatar>
                <q-icon name="public" />
              </q-item-section>
              <q-item-section>Lettere di Vettura (CMR)</q-item-section>
            </q-item>

            <q-separator class="q-my-sm" />
          </template>

          <!-- AMMINISTRAZIONE & CONTABILITÀ -->
          <template v-if="activeModules.accounting">
            <q-item-label header class="text-weight-bold text-uppercase text-caption text-grey-7">
              Contabilità Generale
            </q-item-label>

            <q-item clickable v-ripple to="/accounting" active-class="text-primary bg-blue-1 text-weight-bold">
              <q-item-section avatar>
                <q-icon name="account_balance" />
              </q-item-section>
              <q-item-section>Partita Doppia & Bilancio</q-item-section>
            </q-item>

            <q-separator class="q-my-sm" />
          </template>

          <!-- ANAGRAFICHE CORE -->
          <template v-if="activeModules.anagrafiche">
            <q-item-label header class="text-weight-bold text-uppercase text-caption text-grey-7">
              Anagrafiche Core
            </q-item-label>

            <q-item clickable v-ripple to="/partners" active-class="text-primary bg-blue-1 text-weight-bold">
              <q-item-section avatar>
                <q-icon name="business" />
              </q-item-section>
              <q-item-section>Soggetti (Clienti/Fornitori)</q-item-section>
            </q-item>

            <q-item clickable v-ripple to="/products" active-class="text-primary bg-blue-1 text-weight-bold">
              <q-item-section avatar>
                <q-icon name="eco" />
              </q-item-section>
              <q-item-section>Articoli Biologici</q-item-section>
            </q-item>

            <q-separator class="q-my-sm" />
          </template>

          <!-- SISTEMA & STRUMENTI -->
          <q-item-label header class="text-weight-bold text-uppercase text-caption text-grey-7">
            Sistema & Strumenti
          </q-item-label>

          <q-item clickable v-ripple to="/activities" active-class="text-primary bg-blue-1 text-weight-bold">
            <q-item-section avatar>
              <q-icon name="hub" />
            </q-item-section>
            <q-item-section>Attività, Code & Eventi</q-item-section>
          </q-item>

          <q-item clickable v-ripple to="/users" active-class="text-primary bg-blue-1 text-weight-bold">
            <q-item-section avatar>
              <q-icon name="people" />
            </q-item-section>
            <q-item-section>Gestione Utenti</q-item-section>
          </q-item>

          <q-item clickable v-ripple to="/database" active-class="text-primary bg-blue-1 text-weight-bold">
            <q-item-section avatar>
              <q-icon name="storage" />
            </q-item-section>
            <q-item-section>Database Explorer</q-item-section>
          </q-item>

          <q-item clickable v-ripple to="/healthcheck" active-class="text-primary bg-blue-1 text-weight-bold">
            <q-item-section avatar>
              <q-icon name="health_and_safety" />
            </q-item-section>
            <q-item-section>Health Check</q-item-section>
          </q-item>

          <q-item clickable v-ripple to="/settings" active-class="text-primary bg-blue-1 text-weight-bold">
            <q-item-section avatar>
              <q-icon name="tune" />
            </q-item-section>
            <q-item-section>Impostazioni</q-item-section>
          </q-item>
        </q-list>
      </q-scroll-area>
    </q-drawer>

    <!-- AREA CONTENUTO PRINCIPALE -->
    <q-page-container>
      <main class="content">
        <router-view />
      </main>
    </q-page-container>
  </q-layout>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const isLoggedIn = ref(false)
const currentUser = ref('')
const userRole = ref('')
const leftDrawerOpen = ref(true)

const activeModules = ref({
  anagrafiche: true,
  orders: true,
  delivery_notes: true,
  invoicing: true,
  accounting: true,
  warehouse: true,
  pallets: true,
  cmr: true
})

const fetchModules = async () => {
  try {
    const res = await fetch('/api/modules')
    if (res.ok) {
      activeModules.value = await res.json()
    }
  } catch (err) {
    // Mantieni default attivi
  }
}

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
  fetchModules()
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
.portal-layout {
  min-height: 100vh;
}
.content {
  padding: 0;
}
.leading-tight {
  line-height: 1.1;
}
</style>
