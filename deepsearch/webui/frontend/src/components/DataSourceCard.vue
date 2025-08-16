<template>
  <el-card :class="{ 'is-active': isActive }" class="data-source-card">
    <div class="card-header">
      <el-icon :class="iconClass" class="source-icon">
        <Connection v-if="isWorkers"/>
        <DataLine v-else/>
      </el-icon>
      <div class="title-section">
        <h3>数据源状态</h3>
        <el-tag :type="tagType" size="small">{{ sourceLabel }}</el-tag>
      </div>
    </div>

    <div class="card-body">
      <div class="info-row">
        <span class="label">当前模式：</span>
        <span class="value">{{ sourceMode }}</span>
      </div>

      <div v-if="isWorkers" class="info-row">
        <span class="label">Worker节点：</span>
        <span class="value">{{ workerUrl }}</span>
      </div>

      <div class="info-row">
        <span class="label">响应时间：</span>
        <span class="value">{{ latency }}ms</span>
      </div>

      <div class="info-row">
        <span class="label">最后更新：</span>
        <span class="value">{{ lastUpdate }}</span>
      </div>
    </div>

    <div class="card-footer">
      <el-progress
          :percentage="healthPercentage"
          :status="progressStatus"
          :stroke-width="6"
      />
    </div>
  </el-card>
</template>

<script setup>
import {computed, onMounted, onUnmounted, ref} from 'vue'
import {Connection, DataLine} from '@element-plus/icons-vue'
import {getDataSourceStatus} from '@/api/market'

const props = defineProps({
  dataSource: {
    type: String,
    default: ''
  }
})

// 定时刷新
let refreshTimer = null

// 响应式数据
const sourceInfo = ref({
  source: 'unknown',
  workerUrl: '',
  latency: 0,
  lastUpdate: new Date().toLocaleTimeString(),
  health: 100
})

// 计算属性
const isWorkers = computed(() => {
  if (!sourceInfo.value.source) return false
  return sourceInfo.value.source.startsWith('workers:')
})

const isActive = computed(() => {
  return sourceInfo.value.source !== 'unknown' && sourceInfo.value.source !== 'error'
})

const sourceLabel = computed(() => {
  const source = sourceInfo.value.source
  if (!source || source === 'unknown') return '未知'
  if (source === 'cache') return '缓存'
  if (source === 'error') return '错误'
  if (source.startsWith('workers:')) return 'Workers代理'
  if (source.startsWith('direct:')) return '直连AkShare'
  return source
})

const sourceMode = computed(() => {
  const source = sourceInfo.value.source
  if (!source || source === 'unknown') return '未连接'
  if (source === 'cache') return '本地缓存'
  if (source === 'error') return '连接失败'
  if (source.startsWith('workers:')) return 'Cloudflare Workers'
  if (source.startsWith('direct:')) return 'AkShare直连'
  return '未知模式'
})

const workerUrl = computed(() => {
  const source = sourceInfo.value.source
  if (source && source.startsWith('workers:')) {
    const url = source.substring(8)
    // 简化显示URL
    try {
      const urlObj = new URL(url)
      return urlObj.hostname
    } catch {
      return url
    }
  }
  return '-'
})

const latency = computed(() => {
  return sourceInfo.value.latency || 0
})

const lastUpdate = computed(() => {
  return sourceInfo.value.lastUpdate
})

const healthPercentage = computed(() => {
  return sourceInfo.value.health || 0
})

const progressStatus = computed(() => {
  const health = healthPercentage.value
  if (health >= 80) return 'success'
  if (health >= 50) return 'warning'
  return 'exception'
})

const tagType = computed(() => {
  const source = sourceInfo.value.source
  if (!source || source === 'unknown') return 'info'
  if (source === 'error') return 'danger'
  if (source === 'cache') return 'warning'
  if (source.startsWith('workers:')) return 'success'
  if (source.startsWith('direct:')) return 'primary'
  return 'info'
})

const iconClass = computed(() => {
  return {
    'workers': isWorkers.value,
    'direct': !isWorkers.value && sourceInfo.value.source.startsWith('direct:'),
    'error': sourceInfo.value.source === 'error'
  }
})

// 更新数据源信息
const updateSourceInfo = (data) => {
  if (data.data_source) {
    sourceInfo.value.source = data.data_source
  }
  if (data.latency !== undefined) {
    sourceInfo.value.latency = Math.round(data.latency)
  }
  sourceInfo.value.lastUpdate = new Date().toLocaleTimeString()

  // 根据响应时间计算健康度
  if (data.latency !== undefined) {
    if (data.latency < 100) {
      sourceInfo.value.health = 100
    } else if (data.latency < 500) {
      sourceInfo.value.health = 80
    } else if (data.latency < 1000) {
      sourceInfo.value.health = 60
    } else {
      sourceInfo.value.health = 40
    }
  }
}

// 获取数据源状态
const fetchDataSourceStatus = async () => {
  try {
    const response = await getDataSourceStatus()
    if (response && response.data) {
      const data = response.data
      sourceInfo.value = {
        source: data.source || 'unknown',
        workerUrl: data.worker_url || '',
        latency: Math.round(data.latency || 0),
        lastUpdate: new Date().toLocaleTimeString(),
        health: data.healthy ? 100 : 50
      }
    }
  } catch (error) {
    console.error('获取数据源状态失败:', error)
    sourceInfo.value.source = 'error'
    sourceInfo.value.health = 0
  }
}

// 解析数据源信息（从props或API）
const parseDataSource = async () => {
  if (props.dataSource) {
    updateSourceInfo({data_source: props.dataSource})
  } else {
    await fetchDataSourceStatus()
  }
}

onMounted(async () => {
  // 初始加载
  await parseDataSource()

  // 每5秒刷新一次
  refreshTimer = setInterval(async () => {
    await fetchDataSourceStatus()
  }, 5000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style scoped>
.data-source-card {
  height: 100%;
  transition: all 0.3s ease;
}

.data-source-card.is-active {
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
}

.source-icon {
  font-size: 32px;
  margin-right: 12px;
  transition: color 0.3s;
}

.source-icon.workers {
  color: var(--el-color-success);
}

.source-icon.direct {
  color: var(--el-color-primary);
}

.source-icon.error {
  color: var(--el-color-danger);
}

.title-section h3 {
  margin: 0 0 4px 0;
  font-size: 16px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.card-body {
  margin-bottom: 16px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.info-row:last-child {
  border-bottom: none;
}

.info-row .label {
  color: var(--el-text-color-regular);
  font-size: 14px;
}

.info-row .value {
  color: var(--el-text-color-primary);
  font-size: 14px;
  font-weight: 500;
}

.card-footer {
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}
</style>