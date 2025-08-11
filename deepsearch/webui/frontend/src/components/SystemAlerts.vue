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

<style lang="scss" scoped>
@use '@/assets/styles/design-tokens.scss' as tokens;

.system-alerts {
  margin-bottom: tokens.$spacing-5;
  background: linear-gradient(135deg, rgba(tokens.$color-warning, 0.05) 0%, rgba(tokens.$color-warning, 0.1) 100%);
  border-radius: tokens.$radius-lg;
  padding: tokens.$spacing-4;
  box-shadow: tokens.$shadow-sm;
  border: 1px solid rgba(tokens.$color-warning, 0.2);
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    @include tokens.gradient-bg(tokens.$color-warning, tokens.$color-warning-dark);
  }
}

.alerts-header {
  display: flex;
  align-items: center;
  margin-bottom: tokens.$spacing-3;
  padding-bottom: tokens.$spacing-3;
  border-bottom: 1px solid rgba(tokens.$color-warning, 0.15);
}

.header-icon {
  font-size: 20px;
  color: tokens.$color-warning;
  margin-right: tokens.$spacing-2;
  animation: pulse 2s infinite;
}

.header-title {
  font-size: tokens.$font-size-base;
  font-weight: tokens.$font-weight-semibold;
  color: var(--text-primary);
  flex: 1;
}

.alerts-list {
  display: flex;
  flex-direction: column;
  gap: tokens.$spacing-2;
}

.alert-item {
  background: var(--card-bg);
  border-radius: tokens.$radius-base;
  padding: tokens.$spacing-3 tokens.$spacing-4;
  border-left: 4px solid;
  transition: all tokens.$duration-base tokens.$ease-out;
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    top: 0;
    right: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
    transition: right tokens.$duration-slow;
  }
}

.alert-item:hover {
  transform: translateX(4px);
  box-shadow: tokens.$shadow-md;

  &::before {
    right: 100%;
  }
}

.alert-database {
  border-color: tokens.$color-danger;
  background: linear-gradient(to right, rgba(tokens.$color-danger, 0.05), transparent);
}

.alert-config {
  border-color: tokens.$brand-accent;
  background: linear-gradient(to right, rgba(tokens.$brand-accent, 0.05), transparent);
}

.alert-security {
  border-color: tokens.$color-warning;
  background: linear-gradient(to right, rgba(tokens.$color-warning, 0.05), transparent);
}

.alert-error {
  border-color: tokens.$color-danger-dark;
  background: linear-gradient(to right, rgba(tokens.$color-danger, 0.08), transparent);
}

.alert-warning {
  border-color: tokens.$color-warning;
  background: linear-gradient(to right, rgba(tokens.$color-warning, 0.05), transparent);
}

.alert-info {
  border-color: tokens.$color-info;
  background: linear-gradient(to right, rgba(tokens.$color-info, 0.05), transparent);
}

.alert-content {
  display: flex;
  align-items: center;
  gap: tokens.$spacing-3;
  justify-content: space-between;
}

.alert-main {
  display: flex;
  align-items: center;
  gap: tokens.$spacing-3;
  flex: 1;
}

.alert-icon {
  font-size: 24px;
  flex-shrink: 0;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.1));
}

.alert-database .alert-icon {
  color: tokens.$color-danger;
}

.alert-config .alert-icon {
  color: tokens.$brand-accent;
}

.alert-security .alert-icon {
  color: tokens.$color-warning;
}

.alert-text {
  flex: 1;
}

.alert-title {
  font-weight: tokens.$font-weight-semibold;
  color: var(--text-primary);
  margin-bottom: tokens.$spacing-1;
  font-size: tokens.$font-size-base;
}

.alert-description {
  font-size: tokens.$font-size-sm;
  color: var(--text-secondary);
  line-height: tokens.$line-height-relaxed;
}

/* 动画效果 */
.alert-list-enter-active,
.alert-list-leave-active {
  transition: all tokens.$duration-base tokens.$ease-out;
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
  transition: transform tokens.$duration-base tokens.$ease-out;
}

/* 按钮样式 */
.alert-item {
  .el-button {
    font-size: tokens.$font-size-sm;
    padding: tokens.$spacing-1 tokens.$spacing-3;
    height: 28px;
    border-radius: tokens.$radius-base;
    font-weight: tokens.$font-weight-medium;
  }
}

/* 响应式设计 */
@media (max-width: tokens.$breakpoint-md) {
  .system-alerts {
    padding: tokens.$spacing-3;
  }
  
  .alert-content {
    flex-direction: column;
    align-items: flex-start;
    gap: tokens.$spacing-2;
  }

  .alert-main {
    width: 100%;
  }

  .alert-icon {
    margin-bottom: tokens.$spacing-2;
  }
}

/* 暗色主题 */
.dark {
  .system-alerts {
    background: linear-gradient(135deg, rgba(tokens.$color-warning, 0.1) 0%, rgba(tokens.$color-warning, 0.15) 100%);
    border-color: rgba(tokens.$color-warning, 0.3);
  }

  .alert-item {
    background: var(--card-bg);

    &:hover {
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
    }
  }
}
</style>