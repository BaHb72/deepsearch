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
      <el-tag :type="connectionStatus === 'connected' ? 'success' : connectionStatus === 'error' ? 'danger' : 'info'"
              size="small">
        {{ connectionStatus === 'connected' ? '实时连接' : connectionStatus === 'connecting' ? '连接中...' : '未连接' }}
      </el-tag>

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
          <span class="log-module">{{ log.module || '-' }}</span>
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
import {systemApi} from '../api/system'

const logs = ref([])
const searchText = ref('')
const selectedLevel = ref('')
const dateRange = ref([])
const autoScroll = ref(true)
const logContainer = ref(null)
const isLoading = ref(false)
const logWebSocket = ref(null)
const connectionStatus = ref('disconnected')

// 获取历史日志
const fetchRecentLogs = async () => {
  isLoading.value = true
  try {
    const response = await systemApi.getRecentLogs(200, selectedLevel.value || 'INFO')
    if (response.status === 'success' && response.logs) {
      logs.value = response.logs.map((log, index) => ({
        id: log.id || index,
        timestamp: log.timestamp,
        level: log.level || 'INFO',
        module: log.service || log.location || 'deepsearch',
        message: log.message
      }))

      if (autoScroll.value) {
        nextTick(() => scrollToBottom())
      }
    }
  } catch (error) {
    console.error('获取日志失败:', error)
    ElMessage.error('获取日志失败')
  } finally {
    isLoading.value = false
  }
}

// 连接日志WebSocket
const connectLogWebSocket = () => {
  if (logWebSocket.value) {
    return
  }

  // 在开发环境中，直接连接到后端服务器
  // 在生产环境中，使用当前主机
  let wsUrl
  if (import.meta.env.DEV) {
    // 开发环境：直接连接到后端
    wsUrl = 'ws://localhost:8000/api/logs/ws'
  } else {
    // 生产环境：使用完整URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    wsUrl = `${protocol}//${window.location.host}/api/logs/ws`
  }

  try {
    logWebSocket.value = new WebSocket(wsUrl)
    connectionStatus.value = 'connecting'

    logWebSocket.value.onopen = () => {
      console.log('日志WebSocket已连接')
      connectionStatus.value = 'connected'
    }

    logWebSocket.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.type === 'initial') {
          // 初始日志数据
          logs.value = data.logs.map((log, index) => ({
            id: log.id || index,
            timestamp: log.timestamp,
            level: log.level || 'INFO',
            module: log.service || log.location || 'deepsearch',
            message: log.message
          }))
        } else if (data.type === 'update') {
          // 新日志
          const newLog = {
            id: data.log.id || Date.now(),
            timestamp: data.log.timestamp,
            level: data.log.level || 'INFO',
            module: data.log.service || data.log.location || 'deepsearch',
            message: data.log.message
          }

          logs.value.push(newLog)

          // 限制日志数量
          if (logs.value.length > 1000) {
            logs.value.shift()
          }

          if (autoScroll.value) {
            nextTick(() => scrollToBottom())
          }
        }
      } catch (error) {
        console.error('解析日志消息失败:', error)
      }
    }

    logWebSocket.value.onclose = () => {
      console.log('日志WebSocket已断开')
      connectionStatus.value = 'disconnected'
      logWebSocket.value = null

      // 5秒后重连
      setTimeout(() => {
        if (!logWebSocket.value) {
          connectLogWebSocket()
        }
      }, 5000)
    }

    logWebSocket.value.onerror = (error) => {
      console.error('日志WebSocket错误:', error)
      connectionStatus.value = 'error'
    }

    // 心跳
    setInterval(() => {
      if (logWebSocket.value && logWebSocket.value.readyState === WebSocket.OPEN) {
        logWebSocket.value.send('ping')
      }
    }, 30000)

  } catch (error) {
    console.error('创建WebSocket失败:', error)
    connectionStatus.value = 'error'
  }
}

// 滚动到底部
const scrollToBottom = () => {
  if (logContainer.value) {
    const content = logContainer.value.querySelector('.log-content')
    if (content) {
      content.scrollTop = content.scrollHeight
    }
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
  // 如果已经是格式化的时间字符串，直接返回
  if (typeof timestamp === 'string' && timestamp.includes('-')) {
    return timestamp
  }
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

onMounted(() => {
  // 获取历史日志
  fetchRecentLogs()

  // 连接WebSocket获取实时日志
  connectLogWebSocket()
})

onUnmounted(() => {
  // 断开WebSocket连接
  if (logWebSocket.value) {
    logWebSocket.value.close()
    logWebSocket.value = null
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