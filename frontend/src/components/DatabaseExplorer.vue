<template>
  <div class="db-explorer">
    <h2>Database Explorer</h2>
    <div v-if="!dbData">Loading schema...</div>

    <div v-else>
      <div v-for="table in dbData.tables" :key="table.name" class="table-card">
        <div class="table-header">
          <h3>Table: {{ table.name }}</h3>
          <button @click="fetchRawData(table.name)">View Raw Data</button>
        </div>

        <div v-if="selectedTable === table.name" class="preview-area">
          <h4>Preview (Top 10 rows)</h4>
          <div class="table-scroll">
            <table v-if="rawData.rows.length">
              <thead>
                <tr>
                  <th v-for="col in rawData.columns" :key="col">{{ col }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, idx) in rawData.rows" :key="idx">
                  <td v-for="col in rawData.columns" :key="col">{{ row[col] }}</td>
                </tr>
              </tbody>
            </table>
            <p v-else>Table is empty.</p>
          </div>
          <button @click="selectedTable = null" class="close-btn">Close Preview</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const dbData = ref(null)
const selectedTable = ref(null)
const rawData = ref({ columns: [], rows: [] })

onMounted(async () => {
  const res = await fetch('/api/db-explorer')
  dbData.value = await res.json()
})

const fetchRawData = async (tableName) => {
  const res = await fetch(`/api/db-explorer/${tableName}/data`)
  rawData.value = await res.json()
  selectedTable.value = tableName
}
</script>

<style scoped>
.table-card { border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; border-radius: 8px; }
.table-header { display: flex; justify-content: space-between; align-items: center; }
.preview-area { background: #f9f9f9; padding: 15px; margin-top: 10px; border-top: 2px solid #42b983; }
.table-scroll { overflow-x: auto; margin-bottom: 10px; }
table { width: 100%; border-collapse: collapse; background: white; }
th, td { border: 1px solid #eee; padding: 8px; text-align: left; font-family: monospace; }
th { background: #f4f4f4; }
.close-btn { background: #ff7675; color: white; border: none; padding: 5px 10px; cursor: pointer; }
</style>