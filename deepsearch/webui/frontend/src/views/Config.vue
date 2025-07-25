<template>
  <div class="config-view">
    <div class="page-header">
      <h1>系统配置</h1>
      <el-button type="primary" @click="saveConfig">保存配置</el-button>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="基础配置" name="basic">
        <el-form :model="config.basic" label-width="120px">
          <el-form-item label="应用名称">
            <el-input v-model="config.basic.appName"/>
          </el-form-item>
          <el-form-item label="环境">
            <el-select v-model="config.basic.env">
              <el-option label="开发" value="dev"/>
              <el-option label="测试" value="test"/>
              <el-option label="生产" value="prod"/>
            </el-select>
          </el-form-item>
          <el-form-item label="调试模式">
            <el-switch v-model="config.basic.debug"/>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <el-tab-pane label="事件引擎" name="event">
        <el-form :model="config.event" label-width="120px">
          <el-form-item label="队列大小">
            <el-input-number v-model="config.event.queueSize" :max="100000" :min="1000"/>
          </el-form-item>
          <el-form-item label="工作线程数">
            <el-input-number v-model="config.event.maxWorkers" :max="64" :min="1"/>
          </el-form-item>
          <el-form-item label="批处理大小">
            <el-input-number v-model="config.event.batchSize" :max="1000" :min="1"/>
          </el-form-item>
          <el-form-item label="批处理超时">
            <el-input-number v-model="config.event.batchTimeout" :max="1" :min="0.01" :step="0.01"/>
            <span style="margin-left: 10px">秒</span>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <el-tab-pane label="日志配置" name="log">
        <el-form :model="config.log" label-width="120px">
          <el-form-item label="日志级别">
            <el-select v-model="config.log.level">
              <el-option label="DEBUG" value="DEBUG"/>
              <el-option label="INFO" value="INFO"/>
              <el-option label="WARNING" value="WARNING"/>
              <el-option label="ERROR" value="ERROR"/>
            </el-select>
          </el-form-item>
          <el-form-item label="输出格式">
            <el-select v-model="config.log.format">
              <el-option label="简单" value="simple"/>
              <el-option label="详细" value="verbose"/>
              <el-option label="JSON" value="json"/>
            </el-select>
          </el-form-item>
          <el-form-item label="文件输出">
            <el-switch v-model="config.log.toFile"/>
          </el-form-item>
          <el-form-item label="控制台输出">
            <el-switch v-model="config.log.toConsole"/>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <el-tab-pane label="数据库配置" name="database">
        <el-form :model="config.database" label-width="120px">
          <el-form-item label="Redis 主机">
            <el-input v-model="config.database.redisHost"/>
          </el-form-item>
          <el-form-item label="Redis 端口">
            <el-input-number v-model="config.database.redisPort" :max="65535" :min="1"/>
          </el-form-item>
          <el-form-item label="Redis 密码">
            <el-input v-model="config.database.redisPassword" show-password type="password"/>
          </el-form-item>
          <el-form-item label="连接池大小">
            <el-input-number v-model="config.database.poolSize" :max="100" :min="1"/>
          </el-form-item>
        </el-form>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import {ref, onMounted} from 'vue'
import {ElMessage} from 'element-plus'

const activeTab = ref('basic')

const config = ref({
  basic: {
    appName: 'DeepSearch',
    env: 'dev',
    debug: true
  },
  event: {
    queueSize: 10000,
    maxWorkers: 32,
    batchSize: 100,
    batchTimeout: 0.1
  },
  log: {
    level: 'INFO',
    format: 'verbose',
    toFile: true,
    toConsole: true
  },
  database: {
    redisHost: 'localhost',
    redisPort: 6379,
    redisPassword: '',
    poolSize: 10
  }
})

const loadConfig = async () => {
  try {
    const response = await fetch('/api/config')
    if (response.ok) {
      const data = await response.json()
      Object.assign(config.value, data)
    }
  } catch (error) {
    console.error('Failed to load config:', error)
  }
}

const saveConfig = async () => {
  try {
    const response = await fetch('/api/config', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(config.value)
    })

    if (response.ok) {
      ElMessage.success('配置保存成功')
    } else {
      ElMessage.error('保存失败')
    }
  } catch (error) {
    ElMessage.error('保存失败: ' + error.message)
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.config-view {
  padding: 20px;
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

.el-tabs {
  background: white;
  padding: 20px;
  border-radius: 4px;
}
</style>