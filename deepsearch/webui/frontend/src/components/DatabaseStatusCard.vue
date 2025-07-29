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
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import {onMounted, ref, watch} from 'vue'
import {useRouter} from 'vue-router'
import {useSystemStore} from '@/stores/system'
import {CircleCheck, Connection, Link, Setting} from '@element-plus/icons-vue'

const router = useRouter()
const systemStore = useSystemStore()
const isConnected = ref(false)
const statusMessage = ref('')

// 检查数据库连接状态
const checkDatabaseStatus = () => {
  const components = systemStore.components || []
  const dbComponent = components.find(c => c.name === 'database')

  if (dbComponent) {
    isConnected.value = dbComponent.status === 'running' &&
        dbComponent.info?.connection_status === 'connected'

    if (isConnected.value) {
      statusMessage.value = '数据管理功能已就绪，可以正常使用'
    } else if (dbComponent.status === 'initialized' && !dbComponent.engine) {
      statusMessage.value = '请检查数据库配置并设置密码'
    } else if (dbComponent.status === 'error') {
      statusMessage.value = '数据库连接失败，请检查配置和服务状态'
    } else {
      statusMessage.value = '请先配置数据库连接以使用数据管理功能'
    }
  } else {
    isConnected.value = false
    statusMessage.value = '数据库组件未加载，请检查系统配置'
  }
}

// 跳转到配置页面
const goToConfig = () => {
  router.push({
    name: 'config',
    query: {tab: 'database'}
  })
}

// 监听系统组件状态变化
watch(() => systemStore.components, () => {
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

/* 响应式设计 */
@media (max-width: 768px) {
  .status-content {
    flex-direction: column;
    text-align: center;
  }

  .status-actions {
    justify-content: center;
  }
}
</style>