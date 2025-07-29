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

      <el-tab-pane name="database">
        <template #label>
          <span>数据存储</span>
          <el-icon v-if="hasDbConnectionIssue" style="margin-left: 4px; color: #ff6b6b;">
            <Warning/>
          </el-icon>
        </template>
        <div class="database-tab-content">
        <el-card shadow="never" style="margin-bottom: 20px">
          <template #header>
            <div class="card-header">
              <span>主数据库配置</span>
              <div class="header-right">
                <el-button
                    :loading="mainDbTesting"
                    size="small"
                    style="margin-left: 10px"
                    :type="mainDbStatus?.success ? 'danger' : 'primary'"
                    @click="toggleMainDatabase"
                >
                  {{ mainDbStatus?.success ? '断开连接' : '连接' }}
                </el-button>
                <el-tag
                    v-if="mainDbStatus !== null"
                    :type="mainDbStatus.success ? 'success' : 'danger'"
                    size="small"
                    style="margin-left: 10px"
                >
                  <el-icon style="margin-right: 4px">
                    <CircleCheck v-if="mainDbStatus.success"/>
                    <CircleClose v-else/>
                  </el-icon>
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
            <el-form-item v-if="config.database.main.type !== 'sqlite'" label="连接地址" required>
              <div style="display: flex; gap: 10px; width: 100%;">
                <el-input
                    v-model="config.database.main.host"
                    :class="{'is-error': !config.database.main.host && showValidation}"
                    placeholder="主机地址"
                    style="flex: 1;"
                >
                  <template #prepend>主机</template>
                </el-input>
                <el-input-number
                    v-model="config.database.main.port"
                    :max="65535"
                    :min="1"
                    controls-position="right"
                    placeholder="端口"
                    style="width: 120px;"
                />
              </div>
              <div v-if="!config.database.main.host && showValidation" class="el-form-item__error">
                请输入主机地址
              </div>
            </el-form-item>
            <el-form-item v-if="config.database.main.type !== 'sqlite'" label="数据库名" required>
              <el-input
                  v-model="config.database.main.database"
                  :class="{'is-error': !config.database.main.database && showValidation}"
                  placeholder="输入数据库名称"
              />
              <div v-if="!config.database.main.database && showValidation" class="el-form-item__error">
                请输入数据库名称
              </div>
            </el-form-item>
            <el-form-item v-if="config.database.main.type !== 'sqlite'" label="用户名" required>
              <el-input
                  v-model="config.database.main.username"
                  :class="{'is-error': !config.database.main.username && showValidation}"
                  placeholder="输入数据库用户名"
              />
              <div v-if="!config.database.main.username && showValidation" class="el-form-item__error">
                请输入用户名
              </div>
            </el-form-item>
            <el-form-item v-if="config.database.main.type !== 'sqlite'" label="密码">
              <div style="display: flex; align-items: center; width: 100%;">
                <el-input
                    v-model="config.database.main.password"
                    :placeholder="config.database.main.password === '***' ? '已保存密码（留空保持不变）' : '请输入密码'"
                    show-password
                    style="flex: 1;"
                    type="password"
                />
                <el-tag
                    v-if="config.database.main.password === '***'"
                    size="small"
                    style="margin-left: 8px;"
                    type="success"
                >
                  已保存
                </el-tag>
                <el-checkbox v-model="rememberMainDbPassword" style="margin-left: 12px;">记住密码</el-checkbox>
              </div>
            </el-form-item>
            <el-form-item label="连接选项">
              <el-checkbox v-model="config.database.main.auto_connect">启动时自动连接数据库</el-checkbox>
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
                <el-button
                    :disabled="!config.database.cache.enabled"
                    :loading="cacheDbTesting"
                    size="small"
                    style="margin-left: 10px"
                    :type="cacheDbStatus?.success ? 'danger' : 'primary'"
                    @click="toggleCacheDatabase"
                >
                  {{ cacheDbStatus?.success ? '断开连接' : '连接' }}
                </el-button>
                <el-tag
                    v-if="cacheDbStatus !== null"
                    :type="cacheDbStatus.success ? 'success' : 'danger'"
                    size="small"
                    style="margin-left: 10px"
                >
                  <el-icon style="margin-right: 4px">
                    <CircleCheck v-if="cacheDbStatus.success"/>
                    <CircleClose v-else/>
                  </el-icon>
                  {{ cacheDbStatus.success ? '已连接' : '未连接' }}
                </el-tag>
              </div>
            </div>
          </template>
          <el-form :model="config.database.cache" class="database-form" label-width="140px">
            <el-form-item label="启用缓存">
              <el-switch v-model="config.database.cache.enabled"/>
            </el-form-item>
            <el-form-item v-if="config.database.cache.enabled" label="连接地址">
              <div style="display: flex; gap: 10px; width: 100%;">
                <el-input
                    v-model="config.database.cache.host"
                    placeholder="主机地址"
                    style="flex: 1;"
                >
                  <template #prepend>主机</template>
                </el-input>
                <el-input-number
                    v-model="config.database.cache.port"
                    :max="65535"
                    :min="1"
                    controls-position="right"
                    placeholder="端口"
                    style="width: 120px;"
                />
              </div>
            </el-form-item>
            <el-form-item v-if="config.database.cache.enabled" label="Redis 密码">
              <div style="display: flex; align-items: center; width: 100%;">
                <el-input
                    v-model="config.database.cache.password"
                    :placeholder="config.database.cache.password === '***' ? '已保存密码（留空保持不变）' : '请输入密码'"
                    show-password
                    style="flex: 1;"
                    type="password"
                />
                <el-tag
                    v-if="config.database.cache.password === '***'"
                    size="small"
                    style="margin-left: 8px;"
                    type="success"
                >
                  已保存
                </el-tag>
              </div>
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
import {computed, onMounted, ref} from 'vue'
import {ElMessage, ElNotification} from 'element-plus'
import {CircleCheck, CircleClose, Warning} from '@element-plus/icons-vue'

const activeTab = ref('basic')
const mainDbTesting = ref(false)
const cacheDbTesting = ref(false)
const mainDbStatus = ref(null)
const cacheDbStatus = ref(null)
const originalConfig = ref(null)
const rememberMainDbPassword = ref(false)
const showValidation = ref(false)

// 计算属性：检查是否有数据库连接问题
const hasDbConnectionIssue = computed(() => {
  const mainDbNotConnected = config.value.database.main.enabled &&
      (!mainDbStatus.value || !mainDbStatus.value.success)
  const cacheDbNotConnected = config.value.database.cache.enabled &&
      (!cacheDbStatus.value || !cacheDbStatus.value.success)
  return mainDbNotConnected || cacheDbNotConnected
})

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
      path: './data/deepsearch.db',
      auto_connect: false
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
          // 先保存has_saved_password状态
          const hasSavedPassword = data.database.main.has_saved_password
          Object.assign(config.value.database.main, data.database.main)
          // 如果密码是脱敏的，根据是否有保存的密码决定如何处理
          if (data.database.main.password === '***') {
            if (hasSavedPassword) {
              // 如果有保存的密码，保留脱敏标记，并设置记住密码为true
              config.value.database.main.password = '***'
              rememberMainDbPassword.value = true
            } else {
              // 如果没有保存的密码，清空显示
              config.value.database.main.password = ''
              rememberMainDbPassword.value = false
            }
          }
        }
        if (data.database.cache) {
          // 先保存has_saved_password状态
          const hasSavedPassword = data.database.cache.has_saved_password
          Object.assign(config.value.database.cache, data.database.cache)
          // 如果密码是脱敏的，根据是否有保存的密码决定如何处理
          if (data.database.cache.password === '***') {
            if (hasSavedPassword) {
              // 如果有保存的密码，保留脱敏标记
              config.value.database.cache.password = '***'
            } else {
              // 如果没有保存的密码，清空显示
              config.value.database.cache.password = ''
            }
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
      ElMessage.success(result.message || '配置保存成功')

      // 保存成功后自动尝试连接
      if (config.value.database.main.enabled && rememberMainDbPassword.value && config.value.database.main.password && config.value.database.main.password !== '***') {
        // 如果启用了主数据库、勾选了记住密码、且有新密码，自动连接
        await connectMainDatabase()
      }

      if (config.value.database.cache.enabled && config.value.database.cache.password) {
        // 如果启用了缓存且有密码，自动连接
        await connectCacheDatabase()
      }
    } else {
      ElMessage.error(result.message || '保存失败')
    }
  } catch (error) {
    ElMessage.error('保存失败: ' + error.message)
  }
}

const toggleMainDatabase = async () => {
  if (mainDbStatus.value?.success) {
    // 断开连接
    await disconnectMainDatabase()
  } else {
    // 建立连接
    await connectMainDatabase()
  }
}

const connectMainDatabase = async () => {
  mainDbTesting.value = true

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

    if (!result.success) {
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

const disconnectMainDatabase = async () => {
  // TODO: 实现断开连接的API
  mainDbStatus.value = {success: false}
  ElMessage.success('数据库连接已断开')
}

const toggleCacheDatabase = async () => {
  if (cacheDbStatus.value?.success) {
    // 断开连接
    await disconnectCacheDatabase()
  } else {
    // 建立连接
    await connectCacheDatabase()
  }
}

const connectCacheDatabase = async () => {
  cacheDbTesting.value = true

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

    if (!result.success) {
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

const disconnectCacheDatabase = async () => {
  // TODO: 实现断开连接的API
  cacheDbStatus.value = {success: false}
  ElMessage.success('Redis连接已断开')
}


// 检查数据库连接状态
const checkConnectionStatus = async () => {
  // 检查主数据库状态
  if (config.value.database.main.enabled) {
    try {
      await connectMainDatabase()
    } catch (error) {
      console.log('主数据库未连接')
    }
  }

  // 检查缓存数据库状态
  if (config.value.database.cache.enabled) {
    try {
      await connectCacheDatabase()
    } catch (error) {
      console.log('缓存数据库未连接')
    }
  }
}

onMounted(async () => {
  await loadConfig()
  // 不再自动检查连接状态，避免不必要的弹窗
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

/* 必填项标记 */
.el-form-item[required] .el-form-item__label::before {
  content: '*';
  color: #ff4d4f;
  margin-right: 4px;
}

/* 错误输入框样式 */
.el-input.is-error .el-input__wrapper {
  box-shadow: 0 0 0 1px #ff4d4f inset;
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