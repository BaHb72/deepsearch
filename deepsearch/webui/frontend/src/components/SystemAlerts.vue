<template>
  <div v-if="alerts.length > 0" class="system-alerts">
    <div class="alerts-header">
      <el-icon class="header-icon">
        <InfoFilled/>
      </el-icon>
      <span class="header-title">系统待办事项</span>
      <el-badge :value="alerts.length" type="warning"/>
    </div>
    <transition-group class="alerts-list" name="alert-list" tag="div">
      <div
          v-for="alert in alerts"
          :key="alert.id"
          :class="`alert-${alert.type}`"
          class="alert-item"
      >
        <div class="alert-content">
          <div class="alert-main">
            <el-icon class="alert-icon">
              <component :is="getAlertIcon(alert.type)"/>
            </el-icon>
            <div class="alert-text">
              <div class="alert-title">{{ alert.title }}</div>
              <div class="alert-description">{{ alert.description }}</div>
            </div>
          </div>
          <el-button
              v-if="alert.action"
              plain
              size="small"
              type="primary"
              @click="handleAction(alert)"
          >
            {{ alert.actionText || '立即处理' }}
          </el-button>
        </div>
      </div>
    </transition-group>
  </div>
</template>

<script setup>
import {onMounted, ref, watch} from 'vue'
import {useRouter} from 'vue-router'
import {useSystemStore} from '@/stores/system'
import {CircleClose, Connection, InfoFilled, Key, Setting, Warning} from '@element-plus/icons-vue'

// 定义组件名称
defineOptions({
  name: 'SystemAlerts'
})

const router = useRouter()
const systemStore = useSystemStore()
const alerts = ref([])

// 获取警告图标
const getAlertIcon = (type) => {
  const iconMap = {
    database: Connection,
    config: Setting,
    security: Key,
    error: CircleClose,
    warning: Warning,
    info: InfoFilled
  }
  return iconMap[type] || Warning
}

// 检查系统状态并生成警告
const checkSystemStatus = async () => {
  const newAlerts = []

  // 使用 store 的统一数据库状态
  if (systemStore.hasDatabaseIssue) {
    const dbStatus = systemStore.databaseStatus
    const dbComponent = systemStore.components.find(c => c.name === 'database')
    
    newAlerts.push({
      id: 'db-connection',
      type: 'database',
      title: '数据库未连接',
      description: dbStatus.disconnectReason ||
          (dbComponent?.status === 'initialized'
              ? '数据库配置不完整或密码未设置'
              : '请配置并连接数据库以使用完整功能'),
      action: true,
      actionText: '前往配置',
      actionRoute: {name: 'config', query: {tab: 'database'}}
    })
  }

  // 检查Redis连接状态（可选）
  const cacheComponent = systemStore.components.find(c => c.name === 'cache')
  if (cacheComponent?.enabled && !systemStore.isCacheConnected) {
    newAlerts.push({
      id: 'cache-connection',
      type: 'database',
      title: 'Redis缓存未连接',
      description: '缓存服务未运行，可能影响系统性能',
      action: true,
      actionText: '配置缓存',
      actionRoute: {name: 'config', query: {tab: 'database'}}
    })
  }

  // 检查配置文件
  try {
    const response = await fetch('/api/config')
    const config = await response.json()

    if (config.config_missing) {
      newAlerts.push({
        id: 'config-missing',
        type: 'config',
        title: '配置文件缺失',
        description: `环境: ${config.env}, 路径: ${config.config_path}`,
        action: true,
        actionText: '查看说明',
        actionRoute: {name: 'config'}
      })
    }
  } catch (error) {
    // 静默处理错误
  }

  alerts.value = newAlerts
}

// 处理警告操作
const handleAction = (alert) => {
  if (alert.actionRoute) {
    router.push(alert.actionRoute)
  } else if (alert.actionCallback) {
    alert.actionCallback()
  }
}

// 监听系统组件状态变化
watch(() => systemStore.components, () => {
  checkSystemStatus()
}, {deep: true})

// 监听数据库状态变化
watch(() => systemStore.database, () => {
  checkSystemStatus()
}, {deep: true})

onMounted(() => {
  checkSystemStatus()
})
</script>

<style scoped>
.system-alerts {
  margin-bottom: 20px;
  background: linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.alerts-header {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.header-icon {
  font-size: 20px;
  color: #ff9800;
  margin-right: 8px;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  flex: 1;
}

.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.alert-item {
  background: white;
  border-radius: 8px;
  padding: 12px 16px;
  border-left: 4px solid;
  transition: all 0.3s ease;
}

.alert-item:hover {
  transform: translateX(4px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.alert-database {
  border-color: #ff6b6b;
}

.alert-config {
  border-color: #4ecdc4;
}

.alert-security {
  border-color: #f7b731;
}

.alert-error {
  border-color: #ee5a6f;
}

.alert-warning {
  border-color: #f39c12;
}

.alert-info {
  border-color: #3498db;
}

.alert-content {
  display: flex;
  align-items: center;
  gap: 12px;
  justify-content: space-between;
}

.alert-main {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.alert-icon {
  font-size: 24px;
  flex-shrink: 0;
}

.alert-database .alert-icon {
  color: #ff6b6b;
}

.alert-config .alert-icon {
  color: #4ecdc4;
}

.alert-security .alert-icon {
  color: #f7b731;
}

.alert-text {
  flex: 1;
}

.alert-title {
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
}

.alert-description {
  font-size: 14px;
  color: #666;
  line-height: 1.4;
}

/* 动画效果 */
.alert-list-enter-active,
.alert-list-leave-active {
  transition: all 0.3s ease;
}

.alert-list-enter-from {
  opacity: 0;
  transform: translateX(-20px);
}

.alert-list-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

.alert-list-move {
  transition: transform 0.3s ease;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .alert-content {
    flex-direction: column;
    align-items: flex-start;
  }

  .alert-icon {
    margin-bottom: 8px;
  }
}
</style>