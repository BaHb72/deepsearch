<template>
  <div class="error-monitor">
    <!-- 折叠状态的浮动按钮 -->
    <div v-if="!expanded" class="monitor-button" @click="toggleExpanded">
      <el-badge :hidden="errorCount === 0" :value="errorCount" type="danger">
        <el-icon :size="24">
          <Warning/>
        </el-icon>
      </el-badge>
    </div>

    <!-- 展开状态的面板 -->
    <transition name="slide">
      <div v-if="expanded" class="monitor-panel">
        <div class="panel-header">
          <div class="header-left">
            <el-icon class="header-icon">
              <Monitor/>
            </el-icon>
            <span class="header-title">错误监控</span>
            <el-tag :type="isConnected ? 'success' : 'info'" size="small">
              {{ isConnected ? '实时监控中' : '未连接' }}
            </el-tag>
          </div>
          <div class="header-actions">
            <el-button size="small" @click="clearErrors">清空</el-button>
            <el-button size="small" @click="exportErrors">导出</el-button>
            <el-button circle size="small" @click="toggleExpanded">
              <el-icon>
                <Close/>
              </el-icon>
            </el-button>
          </div>
        </div>

        <div class="panel-stats">
          <div class="stat-item">
            <span class="stat-label">总错误数：</span>
            <span class="stat-value">{{ errors.length }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">最近1小时：</span>
            <span class="stat-value">{{ recentErrorCount }}</span>
          </div>
        </div>

        <div class="panel-content">
          <el-empty v-if="errors.length === 0" description="暂无错误记录"/>

          <div v-else class="error-list">
            <div
                v-for="error in displayErrors"
                :key="error.id"
                :class="['error-item', `error-${error.level}`]"
                @click="selectError(error)"
            >
              <div class="error-header">
                <el-tag :type="getErrorTagType(error.type)" size="small">
                  {{ error.type }}
                </el-tag>
                <span class="error-time">{{ formatTime(error.timestamp) }}</span>
              </div>
              <div class="error-message">{{ error.message }}</div>
              <div v-if="error.category === 'redis'" class="error-detail">
                <el-icon>
                  <Connection/>
                </el-icon>
                Redis相关: {{ error.fullError || error.message }}
              </div>
            </div>
          </div>
        </div>

        <!-- 错误详情对话框 -->
        <el-dialog
            v-model="showDetail"
            :close-on-click-modal="false"
            title="错误详情"
            width="70%"
        >
          <div v-if="selectedError" class="error-detail-content">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="错误ID">{{ selectedError.id }}</el-descriptions-item>
              <el-descriptions-item label="时间">{{ selectedError.timestamp }}</el-descriptions-item>
              <el-descriptions-item label="类型">{{ selectedError.type }}</el-descriptions-item>
              <el-descriptions-item label="级别">{{ selectedError.level }}</el-descriptions-item>
              <el-descriptions-item label="URL">{{ selectedError.url }}</el-descriptions-item>
              <el-descriptions-item label="消息">{{ selectedError.message }}</el-descriptions-item>

              <el-descriptions-item v-if="selectedError.component" label="组件">
                {{ selectedError.component }}
              </el-descriptions-item>

              <el-descriptions-item v-if="selectedError.fullError" label="完整错误">
                {{ selectedError.fullError }}
              </el-descriptions-item>

              <el-descriptions-item v-if="selectedError.stack" label="堆栈">
                <pre class="error-stack">{{ selectedError.stack }}</pre>
              </el-descriptions-item>

              <el-descriptions-item v-if="selectedError.responseData" label="响应数据">
                <pre class="error-response">{{ JSON.stringify(selectedError.responseData, null, 2) }}</pre>
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </el-dialog>
      </div>
    </transition>
  </div>
</template>

<script setup>
import {ref, computed, onMounted, onUnmounted} from 'vue'
import {ElMessage} from 'element-plus'
import {Close, Connection, Monitor, Warning} from '@element-plus/icons-vue'
import {errorTracker} from '@/utils/errorTracker'
import dayjs from 'dayjs'

// 定义组件名称
defineOptions({
  name: 'ErrorMonitor'
})

// 状态
const expanded = ref(false)
const errors = ref([])
const isConnected = ref(false)
const showDetail = ref(false)
const selectedError = ref(null)
const eventSource = ref(null)

// 计算属性
const errorCount = computed(() => errors.value.length)
const displayErrors = computed(() => errors.value.slice(0, 50))
const recentErrorCount = computed(() => {
  const oneHourAgo = Date.now() - 3600000
  return errors.value.filter(e => {
    const time = new Date(e.timestamp).getTime()
    return time > oneHourAgo
  }).length
})

// 切换展开状态
const toggleExpanded = () => {
  expanded.value = !expanded.value
}

// 格式化时间
const formatTime = (timestamp) => {
  return dayjs(timestamp).format('HH:mm:ss')
}

// 获取错误标签类型
const getErrorTagType = (type) => {
  const typeMap = {
    'vue-error': 'danger',
    'javascript-error': 'danger',
    'unhandled-promise': 'warning',
    'api-error': 'warning',
    'vue-warning': 'info',
    'resource-error': 'info',
    'manual': 'primary'
  }
  return typeMap[type] || 'info'
}

// 选择错误查看详情
const selectError = (error) => {
  selectedError.value = error
  showDetail.value = true
}

// 清空错误
const clearErrors = async () => {
  try {
    const response = await fetch('/api/frontend/errors', {
      method: 'DELETE'
    })
    if (response.ok) {
      errors.value = []
      errorTracker.clearErrors()
      ElMessage.success('错误日志已清空')
    }
  } catch (error) {
    ElMessage.error('清空失败')
  }
}

// 导出错误
const exportErrors = () => {
  errorTracker.exportErrors()
}

// 加载历史错误
const loadErrors = async () => {
  try {
    const response = await fetch('/api/frontend/errors')
    const data = await response.json()
    if (data.status === 'success') {
      errors.value = data.errors
    }
  } catch (error) {
    console.error('加载错误日志失败:', error)
  }
}

// 连接 SSE
const connectSSE = () => {
  eventSource.value = new EventSource('/api/frontend/errors/stream')

  eventSource.value.onopen = () => {
    isConnected.value = true
    console.log('错误监控 SSE 已连接')
  }

  eventSource.value.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.type !== 'connected') {
        errors.value.unshift(data)
        // 限制数量
        if (errors.value.length > 100) {
          errors.value.pop()
        }

        // 如果是严重错误，自动展开面板
        if (data.level === 'error' && data.type !== 'resource-error') {
          expanded.value = true
        }
      }
    } catch (error) {
      console.error('解析错误数据失败:', error)
    }
  }

  eventSource.value.onerror = () => {
    isConnected.value = false
    console.error('错误监控 SSE 连接断开')
    // 5秒后重连
    setTimeout(() => {
      if (eventSource.value) {
        connectSSE()
      }
    }, 5000)
  }
}

// 从错误追踪器监听本地错误
const handleLocalError = (error) => {
  if (error.type === 'clear') {
    errors.value = []
  } else {
    errors.value.unshift(error)
    if (errors.value.length > 100) {
      errors.value.pop()
    }
  }
}

onMounted(() => {
  // 加载历史错误
  loadErrors()

  // 连接 SSE
  connectSSE()

  // 监听本地错误
  errorTracker.addListener(handleLocalError)
})

onUnmounted(() => {
  // 关闭 SSE 连接
  if (eventSource.value) {
    eventSource.value.close()
    eventSource.value = null
  }

  // 移除监听器
  errorTracker.removeListener(handleLocalError)
})
</script>

<style scoped>
.error-monitor {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 2000;
}

/* 浮动按钮 */
.monitor-button {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: #ff6b6b;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(255, 107, 107, 0.4);
  transition: all 0.3s;
}

.monitor-button:hover {
  transform: scale(1.1);
  box-shadow: 0 6px 20px rgba(255, 107, 107, 0.5);
}

/* 监控面板 */
.monitor-panel {
  width: 480px;
  max-height: 600px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  padding: 16px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-icon {
  font-size: 20px;
  color: #ff6b6b;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.panel-stats {
  padding: 12px 16px;
  background: #f5f7fa;
  display: flex;
  gap: 24px;
}

.stat-item {
  display: flex;
  gap: 4px;
  font-size: 14px;
}

.stat-label {
  color: #909399;
}

.stat-value {
  font-weight: 600;
  color: #303133;
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

/* 错误列表 */
.error-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.error-item {
  padding: 12px;
  border-radius: 8px;
  background: #f5f7fa;
  cursor: pointer;
  transition: all 0.2s;
}

.error-item:hover {
  background: #e9ecef;
  transform: translateX(-2px);
}

.error-item.error-error {
  border-left: 3px solid #f56c6c;
}

.error-item.error-warning {
  border-left: 3px solid #e6a23c;
}

.error-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.error-time {
  font-size: 12px;
  color: #909399;
}

.error-message {
  font-size: 14px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.error-detail {
  margin-top: 4px;
  font-size: 12px;
  color: #606266;
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 错误详情 */
.error-detail-content {
  max-height: 600px;
  overflow-y: auto;
}

.error-stack,
.error-response {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

/* 动画 */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateY(20px);
  opacity: 0;
}

/* 响应式 */
@media (max-width: 768px) {
  .monitor-panel {
    width: calc(100vw - 48px);
    max-height: 70vh;
  }
}
</style>