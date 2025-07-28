<template>
  <div class="events-view">
    <div class="page-header">
      <h1>事件监控</h1>
      <div class="header-actions">
        <el-button :disabled="events.length === 0" @click="clearEvents">
          清除所有
        </el-button>
        <el-button type="primary" @click="exportEvents">
          导出日志
        </el-button>
      </div>
    </div>

    <div class="filters">
      <el-input
          v-model="searchText"
          clearable
          placeholder="搜索事件..."
          style="width: 300px"
      >
        <template #prefix>
          <el-icon>
            <Search/>
          </el-icon>
        </template>
      </el-input>

      <el-select
          v-model="selectedType"
          clearable
          placeholder="事件类型"
          style="width: 200px"
      >
        <el-option
            v-for="type in eventTypes"
            :key="type"
            :label="type"
            :value="type"
        />
      </el-select>
    </div>

    <el-table
        :data="filteredEvents"
        max-height="600"
        style="width: 100%"
    >
      <el-table-column
          :formatter="formatTime"
          label="时间"
          prop="timestamp"
          width="180"
      />
      <el-table-column
          label="类型"
          prop="type"
          width="150"
      >
        <template #default="scope">
          <el-tag :type="getTagType(scope.row.type)">
            {{ scope.row.type }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
          :formatter="formatData"
          label="数据"
          prop="data"
      />
    </el-table>
  </div>
</template>

<script setup>
import {ref, computed, onMounted, onUnmounted} from 'vue'
import {Search} from '@element-plus/icons-vue'
import {ElMessage} from 'element-plus'
import {useSystemStore} from '@/stores/system'

const store = useSystemStore()
const events = ref([])
const searchText = ref('')
const selectedType = ref('')
const eventTypes = ref([])

// 模拟事件数据
const mockEvents = () => {
  const types = ['EVENT_TICK', 'EVENT_ORDER', 'EVENT_TRADE', 'EVENT_LOG', 'EVENT_ERROR']
  const event = {
    id: Date.now(),
    timestamp: new Date(),
    type: types[Math.floor(Math.random() * types.length)],
    data: {
      symbol: 'AAPL',
      price: 150 + Math.random() * 10,
      volume: Math.floor(Math.random() * 1000)
    }
  }
  events.value.unshift(event)
  if (events.value.length > 100) {
    events.value.pop()
  }
  updateEventTypes()
}

const updateEventTypes = () => {
  const types = new Set(events.value.map(e => e.type))
  eventTypes.value = Array.from(types)
}

const filteredEvents = computed(() => {
  return events.value.filter(event => {
    const matchesSearch = !searchText.value ||
        JSON.stringify(event).toLowerCase().includes(searchText.value.toLowerCase())
    const matchesType = !selectedType.value || event.type === selectedType.value
    return matchesSearch && matchesType
  })
})

const formatTime = (row) => {
  return new Date(row.timestamp).toLocaleString('zh-CN')
}

const formatData = (row) => {
  return JSON.stringify(row.data)
}

const getTagType = (type) => {
  if (type.includes('ERROR')) return 'danger'
  if (type.includes('TRADE')) return 'success'
  if (type.includes('ORDER')) return 'warning'
  return 'info'
}

const clearEvents = () => {
  events.value = []
  ElMessage.success('事件已清除')
}

const exportEvents = () => {
  const data = JSON.stringify(events.value, null, 2)
  const blob = new Blob([data], {type: 'application/json'})
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `events_${new Date().getTime()}.json`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('导出成功')
}

let timer = null

onMounted(() => {
  // 模拟实时事件
  timer = setInterval(mockEvents, 2000)
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
  }
})
</script>

<style scoped>
.events-view {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.filters {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}
</style>