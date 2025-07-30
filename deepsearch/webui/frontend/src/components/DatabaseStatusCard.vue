<template>
  <el-card :class="{ 'status-error': !isConnected }" class="database-status-card">
    <div class="status-content">
      <div class="status-icon">
        <el-icon :color="isConnected ? '#67c23a' : '#909399'" :size="48">
          <Connection v-if="isConnected"/>
          <Link v-else/>
        </el-icon>
      </div>
      <div class="status-info">
        <h3 class="status-title">
          {{ isConnected ? '数据库已连接' : '数据库未连接' }}
        </h3>
        <p class="status-description">
          {{ statusMessage }}
        </p>

        <!-- 连接详情 -->
        <div v-if="dbDetails && isConnected" class="connection-details">
          <div class="detail-item">
            <span class="detail-label">数据库类型：</span>
            <span class="detail-value">{{ dbDetails.config?.type || 'PostgreSQL' }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">连接地址：</span>
            <span class="detail-value">{{ dbDetails.config?.host }}:{{ dbDetails.config?.port }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">数据库名：</span>
            <span class="detail-value">{{ dbDetails.config?.database }}</span>
          </div>
          <div v-if="dbDetails.timescaledb_enabled" class="detail-item">
            <span class="detail-label">TimescaleDB：</span>
            <el-tag size="small" type="success">已启用</el-tag>
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
            配置数据库
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
  name: 'DatabaseStatusCard'
})

const router = useRouter()
const systemStore = useSystemStore()
const statusMessage = ref('')
const dbDetails = ref(null)

// 使用 store 的数据库状态
const isConnected = computed(() => systemStore.isDatabaseConnected)

// 检查数据库连接状态
const checkDatabaseStatus = async () => {
  // 使用 store 中的数据库状态
  const dbStatus = systemStore.databaseStatus
  dbDetails.value = dbStatus

  if (isConnected.value) {
    statusMessage.value = '数据管理功能已就绪，可以正常使用'
  } else if (dbStatus.disconnectReason) {
    statusMessage.value = dbStatus.disconnectReason
  } else if (dbStatus.config?.enabled === false) {
    statusMessage.value = '数据库功能已禁用'
  } else {
    // 从组件状态获取更详细的信息
    const dbComponent = systemStore.components.find(c => c.name === 'database')
    if (dbComponent) {
      if (dbComponent.status === 'initialized' && !dbComponent.engine) {
        statusMessage.value = '请检查数据库配置并设置密码'
      } else if (dbComponent.status === 'error') {
        statusMessage.value = '数据库连接失败，请检查配置和服务状态'
      } else {
        statusMessage.value = '请先配置数据库连接以使用数据管理功能'
      }
    } else {
      statusMessage.value = '数据库组件未加载，请检查系统配置'
    }
  }
}

// 刷新状态
const refreshStatus = async () => {
  try {
    await systemStore.fetchDatabaseStatus()
    await checkDatabaseStatus()
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

// 监听 store 中的数据库状态变化
watch(() => systemStore.database, () => {
  checkDatabaseStatus()
}, {deep: true})

onMounted(() => {
  checkDatabaseStatus()
})
</script>

<style scoped>
.database-status-card {
  margin-bottom: 20px;
  border-radius: 12px;
  overflow: hidden;
  transition: all 0.3s ease;
  border: 2px solid transparent;
}

.database-status-card:not(.status-error) {
  background: linear-gradient(135deg, #f0f9ff 0%, #e6f7ff 100%);
  border-color: #91d5ff;
}

.database-status-card.status-error {
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
.database-status-card {
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