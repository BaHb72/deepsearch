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
          <!-- 数据库状态卡片 -->
          <DatabaseStatusCard style="margin-bottom: 20px"/>

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
                    @blur="handlePasswordBlur"
                    @focus="handlePasswordFocus"
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

          <!-- Redis 缓存状态卡片 -->
          <CacheStatusCard style="margin-bottom: 20px"/>

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
                    :type="systemStore.isCacheConnected ? 'danger' : 'primary'"
                    @click="toggleCacheDatabase"
                >
                  {{ systemStore.isCacheConnected ? '断开连接' : '连接' }}
                </el-button>
                <el-tag
                    v-if="systemStore.cacheStatus.connectionStatus"
                    :type="systemStore.isCacheConnected ? 'success' : 'danger'"
                    size="small"
                    style="margin-left: 10px"
                >
                  <el-icon style="margin-right: 4px">
                    <CircleCheck v-if="systemStore.isCacheConnected"/>
                    <CircleClose v-else/>
                  </el-icon>
                  {{ systemStore.isCacheConnected ? '已连接' : '未连接' }}
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
                    @blur="handlePasswordBlur"
                    @focus="handlePasswordFocus"
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
            <el-form-item v-if="config.database.cache.enabled" label="连接选项">
              <el-checkbox v-model="config.database.cache.auto_connect">启动时自动连接 Redis</el-checkbox>
            </el-form-item>
          </el-form>
        </el-card>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import {computed, onMounted, ref, watch} from 'vue'
import {ElMessage, ElNotification} from 'element-plus'
import {CircleCheck, CircleClose, Warning} from '@element-plus/icons-vue'
import {connectDatabase, disconnectDatabase} from '@/api/database'
import {connectCache, disconnectCache} from '@/api/cache'
import {getAllComponents} from '@/api/system'
import {useSystemStore} from '@/stores/system'
import DatabaseStatusCard from '@/components/DatabaseStatusCard.vue'
import CacheStatusCard from '@/components/CacheStatusCard.vue'

// 定义组件名称
defineOptions({
  name: 'Config'
})

const systemStore = useSystemStore()
const activeTab = ref('basic')
const mainDbTesting = ref(false)
const cacheDbTesting = ref(false)
const mainDbStatus = ref(null)
// 移除本地缓存状态，直接使用 store
const originalConfig = ref(null)
const rememberMainDbPassword = ref(false)
const showValidation = ref(false)

// 计算属性：检查是否有数据库连接问题
const hasDbConnectionIssue = computed(() => {
  // 使用 store 的统一状态
  return systemStore.hasDatabaseIssue
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
      poolSize: 10,
      auto_connect: true
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
    // 验证密码是否为空
    if (config.value.database.main.type !== 'sqlite' && !config.value.database.main.password) {
      ElMessage.error('请先输入数据库密码')
      mainDbStatus.value = {success: false}
      mainDbTesting.value = false
      return
    }

    // 调用连接数据库 API，传递密码
    const result = await connectDatabase(config.value.database.main.password)

    if (result.success) {
      mainDbStatus.value = {success: true}
      ElMessage.success(result.message || '数据库连接成功')

      // 更新数据库状态
      await updateDatabaseStatus()

      // 更新组件状态到 systemStore
      await refreshComponentsStatus()

      // 更新 store 中的数据库状态
      systemStore.updateDatabaseConnection(true)

      // 连接成功后保存配置（包括密码）
      if (config.value.database.main.password && config.value.database.main.password !== '***') {
        await saveConfig()
      }
    } else {
      mainDbStatus.value = {success: false}
      ElMessage.error(result.message || '数据库连接失败')
    }
  } catch (error) {
    mainDbStatus.value = {success: false}

    // 处理不同类型的错误
    if (error.response) {
      // 服务器返回错误
      const errorData = error.response.data
      ElMessage.error(errorData.detail || errorData.message || '数据库连接失败')
    } else if (error.request) {
      // 网络错误
      ElMessage.error('网络请求失败，请检查服务是否正常运行')
    } else {
      // 其他错误
      ElMessage.error('连接失败：' + error.message)
    }
  } finally {
    mainDbTesting.value = false
  }
}

const disconnectMainDatabase = async () => {
  mainDbTesting.value = true

  try {
    // 调用断开数据库 API
    const result = await disconnectDatabase()

    if (result.success) {
      mainDbStatus.value = {success: false}
      ElMessage.success(result.message || '数据库连接已断开')

      // 更新数据库状态
      await updateDatabaseStatus()

      // 更新组件状态到 systemStore
      await refreshComponentsStatus()

      // 更新 store 中的数据库状态
      systemStore.updateDatabaseConnection(false, '用户手动断开连接')
    } else {
      ElMessage.error(result.message || '断开连接失败')
    }
  } catch (error) {
    // 处理错误
    if (error.response) {
      const errorData = error.response.data
      ElMessage.error(errorData.detail || errorData.message || '断开连接失败')
    } else {
      ElMessage.error('断开连接失败：' + error.message)
    }
  } finally {
    mainDbTesting.value = false
  }
}

// 新增：刷新组件状态到 systemStore
const refreshComponentsStatus = async () => {
  try {
    const res = await getAllComponents()
    // 转换成数组格式
    const components = Object.entries(res.components || {}).map(([name, info]) => ({
      name,
      ...info
    }))
    // 更新到 systemStore
    systemStore.updateComponents(components)
  } catch (error) {
    console.error('刷新组件状态失败:', error)
  }
}

// 新增：更新数据库状态
const updateDatabaseStatus = async () => {
  try {
    // 使用 store 获取数据库状态
    await systemStore.fetchDatabaseStatus()
    const status = systemStore.databaseStatus
    mainDbStatus.value = {
      success: status.connected,
      ...status
    }
  } catch (error) {
    console.error('获取数据库状态失败:', error)
  }
}

// 缓存状态通过 store 统一管理，无需本地更新函数

const toggleCacheDatabase = async () => {
  if (systemStore.isCacheConnected) {
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
    // 调用连接缓存 API，传递密码
    const result = await connectCache(config.value.database.cache.password)

    if (result.success) {
      ElMessage.success(result.message || 'Redis 缓存连接成功')

      // 更新缓存状态到 store
      await systemStore.fetchCacheStatus()

      // 更新组件状态到 systemStore
      await refreshComponentsStatus()

      // 更新 store 中的缓存状态
      systemStore.updateCacheConnection(true)

      // 连接成功后保存配置（包括密码）
      if (config.value.database.cache.password) {
        await saveConfig()
      }
    } else {
      ElMessage.error(result.message || 'Redis 缓存连接失败')
    }
  } catch (error) {

    // 处理不同类型的错误
    if (error.response) {
      // 服务器返回错误
      const errorData = error.response.data
      ElMessage.error(errorData.detail || errorData.message || 'Redis 缓存连接失败')
    } else if (error.request) {
      // 网络错误
      ElMessage.error('网络请求失败，请检查服务是否正常运行')
    } else {
      // 其他错误
      ElMessage.error('连接失败：' + error.message)
    }
  } finally {
    cacheDbTesting.value = false
  }
}

const disconnectCacheDatabase = async () => {
  cacheDbTesting.value = true

  try {
    // 调用断开缓存 API
    const result = await disconnectCache()

    if (result.success) {
      ElMessage.success(result.message || 'Redis 缓存连接已断开')

      // 更新缓存状态到 store
      await systemStore.fetchCacheStatus()

      // 更新组件状态到 systemStore
      await refreshComponentsStatus()

      // 更新 store 中的缓存状态
      systemStore.updateCacheConnection(false, '用户手动断开连接')
    } else {
      ElMessage.error(result.message || '断开连接失败')
    }
  } catch (error) {
    // 处理错误
    if (error.response) {
      const errorData = error.response.data
      ElMessage.error(errorData.detail || errorData.message || '断开连接失败')
    } else {
      ElMessage.error('断开连接失败：' + error.message)
    }
  } finally {
    cacheDbTesting.value = false
  }
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

// 处理密码输入框焦点事件，用于处理浏览器扩展干扰
const handlePasswordFocus = (event) => {
  try {
    // 忽略浏览器密码管理器的干扰
    event.target.setAttribute('autocomplete', 'new-password')
  } catch (error) {
    console.warn('忽略密码输入框焦点错误:', error)
  }
}

const handlePasswordBlur = (event) => {
  try {
    // 清理可能的浏览器扩展事件
    event.stopPropagation()
  } catch (error) {
    console.warn('忽略密码输入框失焦错误:', error)
  }
}

// 监听 store 中的数据库状态变化
watch(() => systemStore.isDatabaseConnected, (newVal) => {
  if (mainDbStatus.value) {
    mainDbStatus.value.success = newVal
  }
})

// 监听 store 中的缓存状态变化（无需更新本地状态）
watch(() => systemStore.isCacheConnected, (newVal) => {
  // 状态已经在 store 中，无需本地更新
})

onMounted(async () => {
  // 从 URL 参数获取当前标签
  const urlParams = new URLSearchParams(window.location.search)
  const tab = urlParams.get('tab')
  if (tab) {
    activeTab.value = tab
  }
  
  await loadConfig()
  // 加载后更新数据库连接状态
  await updateDatabaseStatus()
  // 初始加载时刷新组件状态（这会更新所有状态到 store）
  await refreshComponentsStatus()
  // 确保数据库状态也被初始化
  await systemStore.fetchDatabaseStatus()
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