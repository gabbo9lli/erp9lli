<template>
  <div>
    <h3>Add User to {{ dbType }}</h3>
    <input v-model="email" placeholder="Email" />
    <button @click="addUser">Submit</button>

    <ul>
      <li v-for="user in users" :key="user.email">
        ({{ user.email }})
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const email = ref('')
const users = ref([])

const fetchUsers = async () => {
  const res = await fetch('http://localhost:5000/api/users')
  users.value = await res.json()
}

const addUser = async () => {
  await fetch('http://localhost:5000/api/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: email.value })
  })
  email.value = ''
  fetchUsers()
}

onMounted(fetchUsers)
</script>