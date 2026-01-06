<script setup>
import { ref, onMounted } from 'vue';
import api from '../services/api';

const message = ref('Loading...');

onMounted(async () => {
  try {
    const response = await api.getHello();
    message.ref = response.data.message;
  } catch (error) {
    message.value = "Error connecting to backend.";
    console.error(error);
  }
});
</script>

<template>
  <h1>Backend Says: {{ message }}</h1>
</template>