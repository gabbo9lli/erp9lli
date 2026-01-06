<script setup>
import axios from 'axios'
import { ref, onMounted } from 'vue'

const data = ref(null)

onMounted(async () => {
  try {
    const response = await axios.get('/api/data')
    data.value = response.data
  } catch (error) {
    console.error("Error fetching data:", error)
  }
})
</script>