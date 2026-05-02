<template>
  <div class="q-pa-md">
    <q-table
      title="Gestione Utenti"
      :rows="users"
      :columns="columns"
      row-key="id"
      :filter="filter"
      :loading="loading"
    >
      <template v-slot:top-right>
        <q-input borderless dense debounce="300" v-model="filter" placeholder="Cerca...">
          <template v-slot:append><q-icon name="search" /></template>
        </q-input>
        <q-btn color="primary" icon="add" label="Nuovo" class="q-ml-md" @click="openDialog()" />
      </template>

      <template v-slot:body-cell-status="props">
        <q-td :props="props">
          <q-chip
            :color="props.row.reset_token ? 'orange' : 'positive'"
            text-color="white"
            dense
          >
            {{ props.row.reset_token ? 'Reset Pendente' : 'Attivo' }}
          </q-chip>
        </q-td>
      </template>

      <template v-slot:body-cell-actions="props">
        <q-td :props="props" class="q-gutter-x-sm">
          <q-btn flat round color="blue" icon="edit" @click="openDialog(props.row)" />
          <q-btn flat round color="negative" icon="delete" @click="deleteUser(props.row.id)" />
        </q-td>
      </template>
    </q-table>

    <q-dialog v-model="showDialog" persistent>
      <q-card style="min-width: 350px">
        <q-form @submit="saveUser">
          <q-card-section>
            <div class="text-h6">{{ isEditing ? 'Modifica' : 'Nuovo' }} Utente</div>
          </q-card-section>

          <q-card-section class="q-gutter-md">
            <q-input v-model="form.name" label="Nome" filled dense :rules="[val => !!val || 'Richiesto']" />
            <q-input v-model="form.email" label="Email" filled dense type="email" :rules="[val => !!val || 'Richiesto']" />
            <q-select v-model="form.role" :options="['Admin', 'User']" label="Ruolo" filled dense />
          </q-card-section>

          <q-card-actions align="right">
            <q-btn label="Annulla" flat v-close-popup />
            <q-btn label="Salva" color="primary" type="submit" :loading="loading" />
          </q-card-actions>
        </q-form>
      </q-card>
    </q-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { io } from "socket.io-client";
import { useQuasar } from 'quasar';
import axios from 'axios';

// Settings
const $q = useQuasar();
const users = ref([]);
const loading = ref(false);
const filter = ref('');
const showDialog = ref(false);

const form = ref({
  id: null,
  name: '',
  email: '',
  role: 'User'
});

const isEditing = computed(() => form.value.id !== null);

// --- WebSocket Logic (Socket.io) ---
const socket = io({ path: '/api/socket.io' });

const setupSocket = () => {
  socket.on('connect', () => console.log('✅ Socket Connected'));
  
  // Listen for the event emitted by your Flask backend
  socket.on('user_update', (data) => {
    users.value = data;
  });

  socket.on('connect_error', () => {
    $q.notify({ color: 'negative', message: 'Errore connessione Real-time', icon: 'cloud_off' });
  });
};

// --- Table Configuration ---
const columns = [
  { name: 'name', label: 'Nome', field: 'name', align: 'left', sortable: true },
  { name: 'email', label: 'Email', field: 'email', align: 'left', sortable: true },
  { name: 'status', label: 'Stato', align: 'center' },
  { name: 'actions', label: 'Azioni', align: 'right' }
];

// --- API Operations ---
const fetchUsers = async () => {
  loading.value = true;
  try {
    const res = await axios.get('/api/users');
    users.value = res.data;
  } catch (err) {
    $q.notify({ color: 'negative', message: 'Errore caricamento dati' });
  } finally {
    loading.value = false;
  }
};

const saveUser = async () => {
  loading.value = true;
  const url = isEditing.value ? `/api/users/${form.value.id}` : '/api/users';
  const method = isEditing.value ? 'put' : 'post';

  try {
    await axios[method](url, form.value);
    $q.notify({ color: 'positive', message: 'Operazione completata' });
    showDialog.value = false;
    fetchUsers(); // Fallback if socket fails
  } catch (err) {
    $q.notify({ color: 'negative', message: 'Errore durante il salvataggio' });
  } finally {
    loading.value = false;
  }
};

const deleteUser = (id) => {
  $q.dialog({
    title: 'Conferma',
    message: 'Sei sicuro di voler eliminare questo utente?',
    cancel: true,
    persistent: true
  }).onOk(async () => {
    try {
      await axios.delete(`/api/users/${id}`);
      $q.notify({ color: 'positive', message: 'Eliminato' });
      fetchUsers();
    } catch (err) {
      $q.notify({ color: 'negative', message: 'Errore eliminazione' });
    }
  });
};

const openDialog = (user = null) => {
  if (user) {
    form.value = { ...user };
  } else {
    form.value = { id: null, name: '', email: '', role: 'User' };
  }
  showDialog.value = true;
};

// --- Lifecycle ---
onMounted(() => {
  fetchUsers();
  setupSocket();
});

onUnmounted(() => {
  socket.disconnect();
});
</script>