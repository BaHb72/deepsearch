<template>
  <div class="logs-view">
    <div class="page-header">
      <h1>系统日志</h1>
      <div class="header-actions">
        <el-button :disabled="logs.length === 0" @click="clearLogs">
          清除日志
        </el-button>
        <el-button @click="toggleAutoScroll">
          {{ autoScroll ? '停止' : '开始' }}自动滚动
        </el-button>
        <el-button type="primary" @click="downloadLogs">
          下载日志
        </el-button>
      </div>
    </div>

    <div class="filters">
      <el-input
          v-model="searchText"
          clearable
          placeholder="搜索日志..."
          style="width: 300px"
      >
        <template #prefix>
          <el-icon>
            <Search/>
          </el-icon>
        </template>
      </el-input>

      <el-select
          v-model="selectedLevel"
          clearable
          placeholder="日志级别"
          style="width: 150px"
      >
        <el-option label="DEBUG" value="DEBUG"/>
        <el-option label="INFO" value="INFO"/>
        <el-option label="WARNING" value="WARNING"/>
        <el-option label="ERROR" value="ERROR"/>
      </el-select>

      <el-date-picker
          v-model="dateRange"
          end-placeholder="结束时间"
          format="YYYY-MM-DD HH:mm:ss"
          range-separator="至"
          start-placeholder="开始时间"
          type="datetimerange"
          value-format="YYYY-MM-DD HH:mm:ss"
      />
    </div>

    <div ref="logContainer" class="log-container">
      <div class="log-content">
        <div
            v-for="log in filteredLogs"
            :key="log.id"
            :class="['log-item', `log-${log.level.toLowerCase()}`]"
        >
          <span class="log-time">{{ formatTime(log.timestamp) }}</span>
          <span class="log-level">[{{ log.level }}]</span>
          <span class="log-module">{{ log.module }}</span>
          <span class="log-message">{{ log.message }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import {computed, nextTick, onMounted, onUnmounted, ref} from 'vue'
import {Search} from '@element-plus/icons-vue'
import {ElMessage} from 'element-plus'

const logs = ref([])
const searchText = ref('')
const selectedLevel = ref('')
const dateRange = ref([])
const autoScroll = ref(true)
const logContainer = ref(null)

// 模拟日志数据
const mockLog = () => {
  const levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
  const modules = ['deepsearch.core', 'deepsearch.event', 'deepsearch.gateway', 'deepsearch.webui']
  const messages = [
    'Event received: EVENT_TICK',
    'Processing order: ORDER_12345',
    'Trade executed successfully',
    'Connection established',
    'System health check passed',
    'Performance metrics updated',
    'Configuration loaded',
    'Cache cleared'
  ]

  const log = {
    id: Date.now(),
    timestamp: new Date(),
    level: levels[Math.floor(Math.random() * levels.length)],
    module: modules[Math.floor(Math.random() * modules.length)],
    message: messages[Math.floor(Math.random() * messages.length)]
  }

  logs.value.push(log)
  if (logs.value.length > 500) {
    logs.value.shift()
  }

  if (autoScroll.value) {
    nextTick(() => {
      if (logContainer.value) {
        const content = logContainer.value.querySelector('.log-content')
        if (content) {
          content.scrollTop = content.scrollHeight
        }
      }
    })
  }
}

const filteredLogs = computed(() => {
  return logs.value.filter(log => {
    const matchesSearch = !searchText.value ||
        log.message.toLowerCase().includes(searchText.value.toLowerCase()) ||
        log.module.toLowerCase().includes(searchText.value.toLowerCase())

    const matchesLevel = !selectedLevel.value || log.level === selectedLevel.value

    const matchesDate = !dateRange.value || dateRange.value.length === 0 || (
        new Date(log.timestamp) >= new Date(dateRange.value[0]) &&
        new Date(log.timestamp) <= new Date(dateRange.value[1])
    )

    return matchesSearch && matchesLevel && matchesDate
  })
})

const formatTime = (timestamp) => {
  return new Date(timestamp).toLocaleString('zh-CN')
}

const clearLogs = () => {
  logs.value = []
  ElMessage.success('日志已清除')
}

const toggleAutoScroll = () => {
  autoScroll.value = !autoScroll.value
}

const downloadLogs = () => {
  const logText = filteredLogs.value.map(log =>
      `${formatTime(log.timestamp)} [${log.level}] ${log.module} - ${log.message}`
  ).join('\n')

  const blob = new Blob([logText], {type: 'text/plain'})
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `deepsearch_logs_${new Date().getTime()}.log`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('日志下载成功')
}

let timer = null

onMounted(() => {
  // 模拟实时日志
  timer = setInterval(mockLog, 1000)
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
  }
})
</script>

<style scoped>
.logs-view {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
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
  align-items: center;
}

.log-container {
  flex: 1;
  background: #1e1e1e;
  border-radius: 4px;
  padding: 10px;
  overflow: hidden;
}

.log-content {
  height: 100%;
  overflow-y: auto;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.5;
}

.log-item {
  margin-bottom: 2px;
  white-space: pre-wrap;
  word-break: break-word;
}

.log-time {
  color: #888;
  margin-right: 10px;
}

.log-level {
  font-weight: bold;
  margin-right: 10px;
}

.log-module {
  color: #569cd6;
  margin-right: 10px;
}

.log-message {
  color: #d4d4d4;
}

.log-debug .log-level {
  color: #888;
}

.log-info .log-level {
  color: #4ec9b0;
}

.log-warning .log-level {
  color: #dcdcaa;
}

.log-error .log-level {
  color: #f44747;
}

.log-error .log-message {
  color: #f44747;
}
</style>