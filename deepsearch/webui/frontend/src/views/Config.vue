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

      <el-tab-pane label="数据存储" name="database">
        <div class="database-tab-content">
        <el-card shadow="never" style="margin-bottom: 20px">
          <template #header>
            <div class="card-header">
              <span>主数据库配置</span>
              <div class="header-right">
                <el-tag size="small" type="info">用于存储交易数据、历史记录等</el-tag>
                <el-button
                    :loading="mainDbSaving"
                    :type="hasMainDbChanges ? 'warning' : 'success'"
                    size="small"
                    style="margin-left: 10px"
                    @click="saveMainDatabase"
                >
                  <el-icon style="margin-right: 4px">
                    <i-ep-document-checked/>
                  </el-icon>
                  {{ hasMainDbChanges ? '保存配置 *' : '保存配置' }}
                </el-button>
                <el-button
                    :loading="mainDbTesting"
                    size="small"
                    style="margin-left: 10px"
                    type="primary"
                    @click="testMainDatabase"
                >
                  测试连接
                </el-button>
                <el-tag
                    v-if="mainDbStatus !== null"
                    :type="mainDbStatus.success ? 'success' : 'danger'"
                    size="small"
                    style="margin-left: 10px"
                >
                  {{ mainDbStatus.success ? '已连接' : '未连接' }}
                </el-tag>
              </div>
            </div>
          </template>
          <el-form :model="config.database.main" class="database-form" label-width="140px">
            <el-form-item label="数据库类型">
              <el-select v-model="config.database.main.type">
                <el-option label="PostgreSQL" value="postgresql"/>
                <el-option label="MySQL" value="mysql"/>
                <el-option label="SQLite" value="sqlite"/>
              </el-select>
            </el-form-item>
            <el-form-item v-if="config.database.main.type !== 'sqlite'" label="主机地址">
              <el-input v-model="config.database.main.host"/>
            </el-form-item>
            <el-form-item v-if="config.database.main.type !== 'sqlite'" label="端口">
              <el-input-number v-model="config.database.main.port" :max="65535" :min="1"/>
            </el-form-item>
            <el-form-item v-if="config.database.main.type !== 'sqlite'" label="数据库名">
              <el-input v-model="config.database.main.database"/>
            </el-form-item>
            <el-form-item v-if="config.database.main.type !== 'sqlite'" label="用户名">
              <el-input v-model="config.database.main.username"/>
            </el-form-item>
            <el-form-item v-if="config.database.main.type !== 'sqlite'" label="密码">
              <div style="display: flex; align-items: center; width: 100%;">
                <el-input v-model="config.database.main.password" show-password style="flex: 1;" type="password"/>
                <el-checkbox v-model="rememberMainDbPassword" style="margin-left: 12px;">记住密码</el-checkbox>
              </div>
            </el-form-item>
            <el-form-item v-if="config.database.main.type === 'sqlite'" label="文件路径">
              <el-input v-model="config.database.main.path" placeholder="例如: ./data/deepsearch.db"/>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>缓存配置 (Redis)</span>
              <div class="header-right">
                <el-tag size="small" type="success">用于高速缓存、消息队列等</el-tag>
                <el-button
                    :disabled="!config.database.cache.enabled"
                    :loading="cacheDbSaving"
                    :type="hasCacheDbChanges ? 'warning' : 'success'"
                    size="small"
                    style="margin-left: 10px"
                    @click="saveCacheDatabase"
                >
                  <el-icon style="margin-right: 4px">
                    <i-ep-document-checked/>
                  </el-icon>
                  {{ hasCacheDbChanges ? '保存配置 *' : '保存配置' }}
                </el-button>
                <el-button
                    :disabled="!config.database.cache.enabled"
                    :loading="cacheDbTesting"
                    size="small"
                    style="margin-left: 10px"
                    type="primary"
                    @click="testCacheDatabase"
                >
                  测试连接
                </el-button>
                <el-tag
                    v-if="cacheDbStatus !== null"
                    :type="cacheDbStatus.success ? 'success' : 'danger'"
                    size="small"
                    style="margin-left: 10px"
                >
                  {{ cacheDbStatus.success ? '已连接' : '未连接' }}
                </el-tag>
              </div>
            </div>
          </template>
          <el-form :model="config.database.cache" class="database-form" label-width="140px">
            <el-form-item label="启用缓存">
              <el-switch v-model="config.database.cache.enabled"/>
            </el-form-item>
            <el-form-item v-if="config.database.cache.enabled" label="Redis 主机">
              <el-input v-model="config.database.cache.host"/>
            </el-form-item>
            <el-form-item v-if="config.database.cache.enabled" label="Redis 端口">
              <el-input-number v-model="config.database.cache.port" :max="65535" :min="1"/>
            </el-form-item>
            <el-form-item v-if="config.database.cache.enabled" label="Redis 密码">
              <el-input v-model="config.database.cache.password" show-password type="password"/>
            </el-form-item>
            <el-form-item v-if="config.database.cache.enabled" label="数据库索引">
              <el-input-number v-model="config.database.cache.db" :max="15" :min="0"/>
            </el-form-item>
            <el-form-item v-if="config.database.cache.enabled" label="连接池大小">
              <el-input-number v-model="config.database.cache.poolSize" :max="100" :min="1"/>
            </el-form-item>
          </el-form>
        </el-card>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import {onMounted, ref, watch} from 'vue'
import {ElMessage, ElNotification} from 'element-plus'

const activeTab = ref('basic')
const mainDbTesting = ref(false)
const cacheDbTesting = ref(false)
const mainDbStatus = ref(null)
const cacheDbStatus = ref(null)
const mainDbSaving = ref(false)
const cacheDbSaving = ref(false)
const originalConfig = ref(null)
const hasMainDbChanges = ref(false)
const hasCacheDbChanges = ref(false)
const rememberMainDbPassword = ref(false)

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
    main: {
      type: 'postgresql',
      host: 'localhost',
      port: 5432,
      database: 'deepsearch',
      username: 'postgres',
      password: '',
      path: './data/deepsearch.db'
    },
    cache: {
      enabled: true,
      host: 'localhost',
      port: 6379,
      password: '',
      db: 0,
      poolSize: 10
    }
  }
})

const loadConfig = async () => {
  try {
    const response = await fetch('/api/config')
    if (response.ok) {
      const data = await response.json()

      // 检查是否配置文件缺失
      if (data.config_missing) {
        ElMessage.error({
          message: data.message,
          duration: 0,
          showClose: true
        })
        // 显示配置文件路径和环境信息
        ElNotification({
          title: '配置文件不存在',
          message: `环境: ${data.env}\n路径: ${data.config_path}`,
          type: 'error',
          duration: 0
        })
        return
      }
      
      // 合并配置，保留前端的数据结构
      if (data.app) {
        Object.assign(config.value.basic, data.app)
      }
      if (data.event) {
        Object.assign(config.value.event, data.event)
      }
      if (data.log) {
        Object.assign(config.value.log, data.log)
      }
      // 处理数据库配置
      if (data.database) {
        // 新格式，直接合并
        if (data.database.main) {
          Object.assign(config.value.database.main, data.database.main)
          // 如果密码是脱敏的，清空显示
          if (data.database.main.password === '***') {
            config.value.database.main.password = ''
          }
        }
        if (data.database.cache) {
          Object.assign(config.value.database.cache, data.database.cache)
          // 如果密码是脱敏的，清空显示
          if (data.database.cache.password === '***') {
            config.value.database.cache.password = ''
          }
        }
      }

      // 保存原始配置的深拷贝，用于检测变化
      originalConfig.value = JSON.parse(JSON.stringify(config.value))
    }
  } catch (error) {
    console.error('Failed to load config:', error)
    ElMessage.error('加载配置失败: ' + error.message)
  }
}

const saveConfig = async () => {
  try {
    // 转换数据格式以匹配后端期望的格式
    const dataToSave = {
      app: config.value.basic,
      event: config.value.event,
      log: config.value.log,
      database: {
        // 使用新格式
        main: config.value.database.main,
        cache: config.value.database.cache
      }
    }

    const response = await fetch('/api/config/save', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(dataToSave)
    })

    const result = await response.json()

    if (result.success) {
      ElMessage.success(result.message || '配置保存成功')
    } else {
      ElMessage.error(result.message || '保存失败')
    }
  } catch (error) {
    ElMessage.error('保存失败: ' + error.message)
  }
}

const testMainDatabase = async () => {
  mainDbTesting.value = true
  mainDbStatus.value = null

  try {
    const testConfig = {
      db_type: config.value.database.main.type,
      host: config.value.database.main.host,
      port: config.value.database.main.port,
      database: config.value.database.main.database,
      username: config.value.database.main.username,
      password: config.value.database.main.password,
      path: config.value.database.main.path
    }

    const response = await fetch('/api/config/test-database', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(testConfig)
    })

    const result = await response.json()
    mainDbStatus.value = result

    if (result.success) {
      ElMessage.success(result.message)
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    mainDbStatus.value = {success: false}
    // 前端网络错误的友好提示
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      ElMessage.error('网络请求失败，请检查服务是否正常运行')
    } else {
      ElMessage.error('无法连接到服务器')
    }
  } finally {
    mainDbTesting.value = false
  }
}

const testCacheDatabase = async () => {
  cacheDbTesting.value = true
  cacheDbStatus.value = null

  try {
    const testConfig = {
      host: config.value.database.cache.host,
      port: config.value.database.cache.port,
      password: config.value.database.cache.password,
      db: config.value.database.cache.db
    }

    const response = await fetch('/api/config/test-cache', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(testConfig)
    })

    const result = await response.json()
    cacheDbStatus.value = result

    if (result.success) {
      ElMessage.success(result.message)
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    cacheDbStatus.value = {success: false}
    // 前端网络错误的友好提示
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      ElMessage.error('网络请求失败，请检查服务是否正常运行')
    } else {
      ElMessage.error('无法连接到服务器')
    }
  } finally {
    cacheDbTesting.value = false
  }
}

const saveMainDatabase = async () => {
  mainDbSaving.value = true

  try {
    // 只保存数据库相关配置
    const dataToSave = {
      database: {
        main: {
          ...config.value.database.main,
          rememberPassword: rememberMainDbPassword.value
        },
        cache: config.value.database.cache
      }
    }

    const response = await fetch('/api/config/save', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(dataToSave)
    })

    const result = await response.json()

    if (result.success) {
      ElMessage.success('主数据库配置保存成功')
      // 更新原始配置，重置变化状态
      if (originalConfig.value) {
        originalConfig.value.database.main = JSON.parse(JSON.stringify(config.value.database.main))
      }
      hasMainDbChanges.value = false
      // 保存成功后自动测试连接
      await testMainDatabase()
    } else {
      ElMessage.error(result.message || '保存失败')
    }
  } catch (error) {
    ElMessage.error('保存失败: ' + error.message)
  } finally {
    mainDbSaving.value = false
  }
}

const saveCacheDatabase = async () => {
  cacheDbSaving.value = true

  try {
    // 只保存数据库相关配置
    const dataToSave = {
      database: {
        main: config.value.database.main,
        cache: config.value.database.cache
      }
    }

    const response = await fetch('/api/config/save', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(dataToSave)
    })

    const result = await response.json()

    if (result.success) {
      ElMessage.success('缓存配置保存成功')
      // 更新原始配置，重置变化状态
      if (originalConfig.value) {
        originalConfig.value.database.cache = JSON.parse(JSON.stringify(config.value.database.cache))
      }
      hasCacheDbChanges.value = false
      // 如果启用了缓存，保存成功后自动测试连接
      if (config.value.database.cache.enabled) {
        await testCacheDatabase()
      }
    } else {
      ElMessage.error(result.message || '保存失败')
    }
  } catch (error) {
    ElMessage.error('保存失败: ' + error.message)
  } finally {
    cacheDbSaving.value = false
  }
}

// 监听主数据库配置变化
watch(() => config.value.database.main, (newVal) => {
  if (originalConfig.value) {
    const original = originalConfig.value.database.main
    // 比较配置是否有变化（忽略密码字段的空值）
    hasMainDbChanges.value = JSON.stringify({
      ...newVal,
      password: newVal.password || undefined
    }) !== JSON.stringify({
      ...original,
      password: original.password || undefined
    })
  }
}, {deep: true})

// 监听缓存配置变化
watch(() => config.value.database.cache, (newVal) => {
  if (originalConfig.value) {
    const original = originalConfig.value.database.cache
    // 比较配置是否有变化（忽略密码字段的空值）
    hasCacheDbChanges.value = JSON.stringify({
      ...newVal,
      password: newVal.password || undefined
    }) !== JSON.stringify({
      ...original,
      password: original.password || undefined
    })
  }
}, {deep: true})

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

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0;

  span {
    font-weight: 600;
    font-size: 18px;
    color: #1f2329;
    display: flex;
    align-items: center;

    &::before {
      content: '';
      width: 4px;
      height: 20px;
      background: linear-gradient(180deg, #409eff 0%, #79bbff 100%);
      border-radius: 2px;
      margin-right: 12px;
    }
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .el-tag {
    border-radius: 4px;
    padding: 2px 12px;
    font-size: 13px;
  }

  .el-button {
    border-radius: 6px;
    height: 32px;
    padding: 0 16px;
    font-size: 14px;
  }
}

/* 数据库配置卡片样式 */
.el-card {
  border-radius: 12px;
  border: 1px solid #e8ecef;

  &:hover {
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
    transform: translateY(-2px);
    transition: all 0.3s ease;
  }
}

/* 数据库表单样式 */
.database-form {
  padding: 10px 20px;

  .el-form-item {
    margin-bottom: 24px;

    &:last-child {
      margin-bottom: 16px;
    }
  }

  .el-input, .el-select {
    width: 100%;
  }

  .el-input__inner {
    border-radius: 6px;
    height: 40px;

    &:focus {
      border-color: #409eff;
      box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.15);
    }
  }

  .el-select .el-input__inner {
    cursor: pointer;
  }

  .el-input-number {
    width: 200px;

    .el-input__inner {
      text-align: left;
    }
  }

  .el-form-item__label {
    font-weight: 500;
    color: #333;
    font-size: 14px;
  }
}

/* 保存按钮样式优化 */
.header-right .el-button[type="success"] {
  font-weight: 500;

  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(103, 194, 58, 0.3);
  }
}

.header-right .el-button[type="warning"] {
  font-weight: 600;
  animation: pulse 2s infinite;
  
  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(230, 162, 60, 0.3);
  }
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(230, 162, 60, 0.4);
  }
  70% {
    box-shadow: 0 0 0 10px rgba(230, 162, 60, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(230, 162, 60, 0);
  }
}

/* 数据库页签内容样式 */
.database-tab-content {
  .el-card {
    margin-bottom: 24px;

    &:last-child {
      margin-bottom: 0;
    }
  }

  /* 密码记住选项样式 */

  .el-checkbox {
    font-size: 14px;
    color: #606266;

    .el-checkbox__label {
      padding-left: 8px;
    }
  }
}

/* 连接状态标签样式优化 */
.el-tag[type="success"] {
  background-color: #f0f9ff;
  border-color: #d0f0ff;
  color: #10b981;
}

.el-tag[type="danger"] {
  background-color: #fef2f2;
  border-color: #fee2e2;
  color: #ef4444;
}

.el-tag[type="info"] {
  background-color: #f5f7fa;
  border-color: #e4e7ed;
  color: #909399;
}
</style>