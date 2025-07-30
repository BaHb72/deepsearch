<template>
  <el-alert
      v-if="!isConnected"
      :closable="false"
      show-icon
      style="margin-bottom: 20px"
      title="数据库未连接"
      type="warning"
  >
    <template #default>
      <div style="display: flex; align-items: center; justify-content: space-between;">
        <span>{{ message || connectionMessage || '请先配置并连接数据库才能使用此功能' }}</span>
        <el-button size="small" type="primary" @click="goToConfig">
          前往配置
        </el-button>
      </div>
    </template>
  </el-alert>
</template>

<script setup>
import {onMounted, ref, watch} from 'vue'
import {useRouter} from 'vue-router'
import {useSystemStore} from '@/stores/system'

// 定义组件名称
defineOptions({
  name: 'DatabaseAlert'
})

const props = defineProps({
  message: {
    type: String,
    default: ''
  }
})

const router = useRouter()
const systemStore = useSystemStore()
const isConnected = ref(false)
const connectionMessage = ref('')

// 检查数据库连接状态
const checkDatabaseStatus = () => {
  const components = systemStore.components || []
  const dbComponent = components.find(c => c.name === 'database')
  if (dbComponent) {
    // 检查组件是否正在运行且已连接
    isConnected.value = dbComponent.status === 'running' && dbComponent.info?.connection_status === 'connected'

    // 根据组件状态设置消息
    if (dbComponent.status === 'initialized' && !dbComponent.engine) {
      connectionMessage.value = '数据库配置不完整或密码未设置，请检查配置'
    } else if (dbComponent.status === 'error') {
      connectionMessage.value = '数据库连接失败，请检查配置和服务状态'
    } else if (!isConnected.value) {
      connectionMessage.value = '数据库未连接，请先配置并连接数据库'
    }
  } else {
    isConnected.value = false
    connectionMessage.value = '数据库组件未加载'
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