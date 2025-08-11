<template>
  <div class="data-source">
    <h2>数据源监控</h2>

    <!-- Worker 节点状态 -->
    <el-card class="worker-status">
      <template #header>
        <div class="card-header">
          <span>Worker 节点状态</span>
          <el-button :loading="refreshing" size="small" @click="refreshWorkers">
            <el-icon>
              <Refresh/>
            </el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <el-table :data="workerNodes" style="width: 100%">
        <el-table-column label="节点 URL" min-width="250" prop="url"/>
        <el-table-column label="区域" prop="region" width="100"/>
        <el-table-column label="状态" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.healthy ? 'success' : 'danger'">
              {{ scope.row.healthy ? '健康' : '异常' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="延迟 (ms)" prop="latency" width="100"/>
        <el-table-column label="成功率" width="100">
          <template #default="scope">
            {{ (scope.row.success_rate * 100).toFixed(1) }}%
          </template>
        </el-table-column>
        <el-table-column label="总请求数" prop="total_requests" width="100"/>
        <el-table-column fixed="right" label="操作" width="100">
          <template #default="scope">
            <el-button
                :loading="testing[scope.row.url]"
                size="small"
                @click="testWorker(scope.row)"
            >
              测试
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 数据获取统计 -->
    <el-card class="fetch-stats">
      <template #header>
        <span>数据获取统计</span>
      </template>

      <el-row :gutter="20">
        <el-col :span="6">
          <el-statistic :value="stats.total_requests" title="总请求数"/>
        </el-col>
        <el-col :span="6">
          <el-statistic
              :value="stats.success_rate"
              suffix="%"
              title="成功率"
          />
        </el-col>
        <el-col :span="6">
          <el-statistic
              :value="stats.avg_latency"
              suffix="ms"
              title="平均延迟"
          />
        </el-col>
        <el-col :span="6">
          <el-statistic
              :value="stats.cache_hit_rate"
              suffix="%"
              title="缓存命中率"
          />
        </el-col>
      </el-row>

      <el-row :gutter="20" style="margin-top: 20px">
        <el-col :span="12">
          <el-progress
              :percentage="healthyPercentage"
              :status="healthyPercentage === 100 ? 'success' : 'warning'"
          >
            <span>健康节点: {{ stats.healthy_workers }}/{{ stats.total_workers }}</span>
          </el-progress>
        </el-col>
      </el-row>
    </el-card>

    <!-- 数据测试 -->
    <el-card class="data-test">
      <template #header>
        <span>数据获取测试</span>
      </template>

      <el-form :inline="true">
        <el-form-item label="股票代码">
          <el-input v-model="testSymbol" placeholder="例如: 000001"/>
        </el-form-item>
        <el-form-item label="数据类型">
          <el-select v-model="testType">
            <el-option label="实时数据" value="realtime"/>
            <el-option label="历史数据" value="history"/>
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button :loading="fetching" type="primary" @click="testFetch">
            获取数据
          </el-button>
        </el-form-item>
      </el-form>

      <div v-if="testResult" class="test-result">
        <el-alert
            :closable="false"
            :title="testResult.success ? '获取成功' : '获取失败'"
            :type="testResult.success ? 'success' : 'error'"
        >
          <pre>{{ JSON.stringify(testResult.data, null, 2) }}</pre>
        </el-alert>
      </div>
    </el-card>

    <!-- 实时日志 -->
    <el-card class="logs">
      <template #header>
        <div class="card-header">
          <span>实时日志</span>
          <el-tag>{{ logs.length }} 条</el-tag>
        </div>
      </template>

      <div class="log-container">
        <div
            v-for="log in logs"
            :key="log.id"
            :class="['log-item', `log-${log.level}`]"
        >
          <span class="log-time">{{ formatTime(log.timestamp) }}</span>
          <el-tag :type="getLogType(log.level)" size="small">{{ log.level }}</el-tag>
          <span class="log-worker">[{{ log.worker }}]</span>
          <span class="log-message">{{ log.message }}</span>
        </div>
        <div v-if="logs.length === 0" class="no-logs">
          等待日志...
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import {computed, onMounted, onUnmounted, ref} from 'vue'
import {ElMessage} from 'element-plus'
import {Refresh} from '@element-plus/icons-vue'

// 数据
const workerNodes = ref([])
const stats = ref({
  total_requests: 0,
  success_rate: 0,
  avg_latency: 0,
  cache_hit_rate: 0,
  healthy_workers: 0,
  total_workers: 0
})
const logs = ref([])

// 状态
const refreshing = ref(false)
const testing = ref({})
const fetching = ref(false)

// 测试相关
const testSymbol = ref('000001')
const testType = ref('realtime')
const testResult = ref(null)

// WebSocket
let ws = null
let updateInterval = null

// 计算属性
const healthyPercentage = computed(() => {
  if (stats.value.total_workers === 0) return 0
  return Math.round((stats.value.healthy_workers / stats.value.total_workers) * 100)
})

// 生命周期
onMounted(() => {
  // 获取初始数据
  fetchWorkerStatus()
  fetchStats()

  // 建立 WebSocket 连接
  connectWebSocket()

  // 定期更新
  updateInterval = setInterval(() => {
    fetchWorkerStatus()
    fetchStats()
  }, 5000)
})

onUnmounted(() => {
  if (updateInterval) {
    clearInterval(updateInterval)
  }
  if (ws) {
    ws.close()
  }
})

// 方法
async function fetchWorkerStatus() {
  try {
    const response = await fetch('/api/data-source/workers')
    const data = await response.json()
    workerNodes.value = data
  } catch (error) {
    console.error('获取 Worker 状态失败:', error)
  }
}

async function fetchStats() {
  try {
    const response = await fetch('/api/data-source/stats')
    const data = await response.json()
    stats.value = data
  } catch (error) {
    console.error('获取统计数据失败:', error)
  }
}

async function refreshWorkers() {
  refreshing.value = true
  try {
    const response = await fetch('/api/data-source/refresh', {
      method: 'POST'
    })
    const data = await response.json()
    ElMessage.success(data.message)

    // 刷新数据
    await fetchWorkerStatus()
    await fetchStats()
  } catch (error) {
    ElMessage.error('刷新失败')
  } finally {
    refreshing.value = false
  }
}

async function testWorker(worker) {
  testing.value[worker.url] = true
  try {
    const response = await fetch('/api/data-source/test-worker', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({url: worker.url})
    })

    const result = await response.json()

    if (result.success) {
      ElMessage.success(`Worker ${worker.region} 测试成功`)
    } else {
      ElMessage.error(`Worker ${worker.region} 测试失败: ${result.message}`)
    }
  } catch (error) {
    ElMessage.error('测试失败')
  } finally {
    testing.value[worker.url] = false
  }
}

async function testFetch() {
  if (!testSymbol.value) {
    ElMessage.warning('请输入股票代码')
    return
  }

  fetching.value = true
  testResult.value = null

  try {
    const response = await fetch('/api/data-source/fetch', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        symbols: [testSymbol.value],
        data_type: testType.value,
        start_date: '2024-01-01',
        end_date: '2024-01-31'
      })
    })

    const data = await response.json()

    if (response.ok) {
      testResult.value = {
        success: true,
        data: data
      }
      ElMessage.success('数据获取成功')
    } else {
      testResult.value = {
        success: false,
        data: data
      }
      ElMessage.error('数据获取失败')
    }
  } catch (error) {
    testResult.value = {
      success: false,
      data: {error: error.message}
    }
    ElMessage.error('请求失败')
  } finally {
    fetching.value = false
  }
}

function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  ws = new WebSocket(`${protocol}//${host}/api/data-source/logs`)

  ws.onmessage = (event) => {
    const log = JSON.parse(event.data)
    logs.value.unshift(log)

    // 保留最新的 50 条日志
    if (logs.value.length > 50) {
      logs.value.pop()
    }
  }

  ws.onerror = (error) => {
    console.error('WebSocket 错误:', error)
  }

  ws.onclose = () => {
    // 尝试重连
    setTimeout(() => {
      if (ws.readyState === WebSocket.CLOSED) {
        connectWebSocket()
      }
    }, 5000)
  }
}

function formatTime(timestamp) {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN')
}

function getLogType(level) {
  const types = {
    'error': 'danger',
    'warning': 'warning',
    'info': 'info',
    'debug': 'info'
  }
  return types[level] || 'info'
}
</script>

<style scoped>
.data-source {
  padding: 20px;
}

.el-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.log-container {
  height: 300px;
  overflow-y: auto;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  background: #f5f5f5;
  padding: 10px;
  border-radius: 4px;
}

.log-item {
  padding: 4px 8px;
  margin-bottom: 4px;
  border-radius: 2px;
  background: white;
  display: flex;
  align-items: center;
  gap: 8px;
}

.log-error {
  background-color: #fee;
}

.log-warning {
  background-color: #ffeaa7;
}

.log-info {
  background-color: #fff;
}

.log-debug {
  background-color: #f0f0f0;
}

.log-time {
  color: #666;
  min-width: 80px;
}

.log-worker {
  color: #09f;
  font-weight: bold;
}

.log-message {
  flex: 1;
}

.no-logs {
  text-align: center;
  color: #999;
  padding: 50px;
}

.test-result {
  margin-top: 20px;
}

.test-result pre {
  max-height: 300px;
  overflow-y: auto;
  font-size: 12px;
}

.el-progress {
  margin-top: 10px;
}
</style>