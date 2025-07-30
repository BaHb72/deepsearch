<template>
  <el-card :class="{ 'status-error': !isConnected }" class="cache-status-card">
    <div class="status-content">
      <div class="status-icon">
        <el-icon :color="isConnected ? '#67c23a' : '#909399'" :size="48">
          <Connection v-if="isConnected"/>
          <Link v-else/>
        </el-icon>
      </div>
      <div class="status-info">
        <h3 class="status-title">
          {{ isConnected ? 'Redis 缓存已连接' : 'Redis 缓存未连接' }}
        </h3>
        <p class="status-description">
          {{ statusMessage }}
        </p>

        <!-- 连接详情 -->
        <div v-if="cacheDetails && isConnected" class="connection-details">
          <div class="detail-item">
            <span class="detail-label">Redis 版本：</span>
            <span class="detail-value">{{ cacheDetails.connectionInfo?.version || 'unknown' }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">连接地址：</span>
            <span class="detail-value">{{ cacheDetails.config?.host }}:{{ cacheDetails.config?.port }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">数据库索引：</span>
            <span class="detail-value">{{ cacheDetails.config?.db || 0 }}</span>
          </div>
          <div v-if="cacheDetails.connectionInfo?.used_memory_human" class="detail-item">
            <span class="detail-label">内存使用：</span>
            <span class="detail-value">{{ cacheDetails.connectionInfo.used_memory_human }}</span>
          </div>
          <div v-if="cacheDetails.health?.details?.ping_ms !== undefined" class="detail-item">
            <span class="detail-label">响应时间：</span>
            <el-tag :type="getPingType(cacheDetails.health.details.ping_ms)" size="small">
              {{ cacheDetails.health.details.ping_ms }} ms
            </el-tag>
          </div>
        </div>

        <div class="status-actions">
          <el-button
              v-if="!isConnected"
              size="small"
              type="primary"
              @click="goToConfig"
          >
            <el-icon>
              <Setting/>
            </el-icon>
            配置缓存
          </el-button>
          <el-button
              v-else
              disabled
              plain
              size="small"
              type="success"
          >
            <el-icon>
              <CircleCheck/>
            </el-icon>
            运行正常
          </el-button>
          <el-button
              v-if="isConnected"
              plain
              size="small"
              @click="refreshStatus"
          >
            <el-icon>
              <Refresh/>
            </el-icon>
            刷新
          </el-button>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import {computed, onMounted, ref, watch} from 'vue'
import {useRouter} from 'vue-router'
import {useSystemStore} from '@/stores/system'
import {CircleCheck, Connection, Link, Refresh, Setting} from '@element-plus/icons-vue'
import {ElMessage} from 'element-plus'

// 定义组件名称
defineOptions({
  name: 'CacheStatusCard'
})

const router = useRouter()
const systemStore = useSystemStore()
const statusMessage = ref('')
const cacheDetails = ref(null)

// 使用 store 的缓存状态
const isConnected = computed(() => systemStore.isCacheConnected)

// 获取 ping 类型
const getPingType = (pingMs) => {
  if (pingMs < 10) return 'success'
  if (pingMs < 50) return 'warning'
  return 'danger'
}

// 检查缓存连接状态
const checkCacheStatus = async () => {
  // 使用 store 中的缓存状态
  const cacheStatus = systemStore.cacheStatus
  cacheDetails.value = cacheStatus

  if (isConnected.value) {
    statusMessage.value = '缓存服务运行正常，提供高速数据访问'
  } else if (cacheStatus.disconnectReason) {
    statusMessage.value = cacheStatus.disconnectReason
  } else if (cacheStatus.config?.enabled === false) {
    statusMessage.value = 'Redis 缓存功能已禁用'
  } else {
    // 从组件状态获取更详细的信息
    const cacheComponent = systemStore.components.find(c => c.name === 'cache')
    if (cacheComponent) {
      if (cacheComponent.status === 'initialized' && !cacheComponent.engine) {
        statusMessage.value = '请检查 Redis 配置并确保服务正在运行'
      } else if (cacheComponent.status === 'error') {
        statusMessage.value = 'Redis 连接失败，请检查配置和服务状态'
      } else {
        statusMessage.value = '请先配置 Redis 连接以使用缓存功能'
      }
    } else {
      statusMessage.value = 'Redis 缓存组件未加载，请检查系统配置'
    }
  }
}

// 刷新状态
const refreshStatus = async () => {
  try {
    await systemStore.fetchCacheStatus()
    await checkCacheStatus()
    ElMessage.success('状态已刷新')
  } catch (error) {
    ElMessage.error('刷新失败')
  }
}

// 跳转到配置页面
const goToConfig = () => {
  router.push({
    name: 'config',
    query: {tab: 'database'}
  })
}

// 监听 store 中的缓存状态变化
watch(() => systemStore.database.cache, () => {
  checkCacheStatus()
}, {deep: true})

onMounted(() => {
  checkCacheStatus()
})
</script>

<style scoped>
.cache-status-card {
  margin-bottom: 20px;
  border-radius: 12px;
  overflow: hidden;
  transition: all 0.3s ease;
  border: 2px solid transparent;
}

.cache-status-card:not(.status-error) {
  background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);
  border-color: #ffb74d;
}

.cache-status-card.status-error {
  background: linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%);
  border-color: #d9d9d9;
}

.status-content {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 8px;
}

.status-icon {
  flex-shrink: 0;
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: white;
  border-radius: 50%;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.status-info {
  flex: 1;
}

.status-title {
  margin: 0 0 8px 0;
  font-size: 20px;
  font-weight: 600;
  color: #1f2329;
}

.status-description {
  margin: 0 0 16px 0;
  font-size: 14px;
  color: #646a73;
  line-height: 1.5;
}

.status-actions {
  display: flex;
  gap: 12px;
}

/* 动画效果 */
.cache-status-card {
  animation: fadeIn 0.5s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 连接详情样式 */
.connection-details {
  margin: 16px 0;
  padding: 12px;
  background: #f7f9fb;
  border-radius: 8px;
  font-size: 13px;
}

.detail-item {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.detail-item:last-child {
  margin-bottom: 0;
}

.detail-label {
  color: #646a73;
  margin-right: 8px;
  min-width: 80px;
}

.detail-value {
  color: #1f2329;
  font-weight: 500;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .status-content {
    flex-direction: column;
    text-align: center;
  }

  .status-actions {
    justify-content: center;
  }

  .connection-details {
    text-align: left;
  }
}
</style>