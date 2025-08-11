<template>
  <div class="config-view">
    <div class="page-header">
      <div class="header-content">
        <h1 class="page-title">
          <el-icon class="title-icon">
            <Setting/>
          </el-icon>
          系统配置
        </h1>
        <p class="page-subtitle">管理系统各项参数配置，优化系统性能</p>
      </div>
      <div class="header-actions">
        <el-button @click="resetConfig">
          <el-icon>
            <RefreshLeft/>
          </el-icon>
          重置配置
        </el-button>
        <el-button type="primary" @click="saveConfig">
          <el-icon>
            <Check/>
          </el-icon>
          保存配置
        </el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="config-tabs">
      <el-tab-pane name="basic">
        <template #label>
          <span class="tab-label">
            <el-icon><Platform/></el-icon>
            基础配置
          </span>
        </template>
        <el-card class="config-card">
          <el-form :model="config.basic" label-width="140px">
            <el-form-item label="应用名称">
              <el-input
                  v-model="config.basic.appName"
                  clearable
                  placeholder="输入应用名称"
              >
                <template #prefix>
                  <el-icon>
                    <Promotion/>
                  </el-icon>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item label="运行环境">
              <el-select v-model="config.basic.env" placeholder="选择运行环境">
                <el-option label="开发环境" value="dev">
                  <span class="option-label">
                    <el-icon><Edit/></el-icon>
                    开发环境
                  </span>
                </el-option>
                <el-option label="测试环境" value="test">
                  <span class="option-label">
                    <el-icon><Cpu/></el-icon>
                    测试环境
                  </span>
                </el-option>
                <el-option label="生产环境" value="prod">
                  <span class="option-label">
                    <el-icon><Trophy/></el-icon>
                    生产环境
                  </span>
                </el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="调试模式">
              <el-switch
                  v-model="config.basic.debug"
                  active-text="开启"
                  inactive-text="关闭"
              />
              <span class="form-item-tip">开启后将输出详细调试信息</span>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <el-tab-pane name="event">
        <template #label>
          <span class="tab-label">
            <el-icon><Connection/></el-icon>
            事件引擎
          </span>
        </template>
        <el-card class="config-card">
          <el-form :model="config.event" label-width="140px">
            <el-form-item label="队列大小">
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-input-number
                      v-model="config.event.queueSize"
                      :max="100000"
                      :min="1000"
                      :step="1000"
                      controls-position="right"
                      style="width: 100%"
                  />
                </el-col>
                <el-col :span="12">
                  <el-progress
                      :format="() => config.event.queueSize + ' 个'"
                      :percentage="(config.event.queueSize / 100000) * 100"
                      :stroke-width="10"
                  />
                </el-col>
              </el-row>
            </el-form-item>
            <el-form-item label="工作线程数">
              <el-row :gutter="20" align="middle">
                <el-col :span="12">
                  <el-slider
                      v-model="config.event.maxWorkers"
                      :max="64"
                      :min="1"
                      show-input
                  />
                </el-col>
                <el-col :span="12">
                  <span class="form-item-tip">推荐值: CPU核心数 * 2</span>
                </el-col>
              </el-row>
            </el-form-item>
            <el-form-item label="批处理大小">
              <el-input-number
                  v-model="config.event.batchSize"
                  :max="1000"
                  :min="1"
                  :step="10"
                  controls-position="right"
              />
              <span class="form-item-tip">每批次处理的事件数量</span>
            </el-form-item>
            <el-form-item label="批处理超时">
              <el-input-number
                  v-model="config.event.batchTimeout"
                  :max="1"
                  :min="0.01"
                  :precision="2"
                  :step="0.01"
                  controls-position="right"
              />
              <span style="margin-left: 10px">秒</span>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <el-tab-pane name="log">
        <template #label>
          <span class="tab-label">
            <el-icon><Document/></el-icon>
            日志配置
          </span>
        </template>
        <el-card class="config-card">
          <el-form :model="config.log" label-width="140px">
            <el-form-item label="日志级别">
              <el-radio-group v-model="config.log.level">
                <el-radio-button value="DEBUG">
                  <el-icon>
                    <View/>
                  </el-icon>
                  DEBUG
                </el-radio-button>
                <el-radio-button value="INFO">
                  <el-icon>
                    <InfoFilled/>
                  </el-icon>
                  INFO
                </el-radio-button>
                <el-radio-button value="WARNING">
                  <el-icon>
                    <WarningFilled/>
                  </el-icon>
                  WARNING
                </el-radio-button>
                <el-radio-button value="ERROR">
                  <el-icon>
                    <CircleCloseFilled/>
                  </el-icon>
                  ERROR
                </el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="输出格式">
              <el-select v-model="config.log.format" placeholder="选择输出格式">
                <el-option label="简单格式" value="simple">
                  <span class="option-label">
                    <el-icon><Memo/></el-icon>
                    简单格式 - 基本日志信息
                  </span>
                </el-option>
                <el-option label="详细格式" value="verbose">
                  <span class="option-label">
                    <el-icon><Tickets/></el-icon>
                    详细格式 - 包含完整上下文
                  </span>
                </el-option>
                <el-option label="JSON格式" value="json">
                  <span class="option-label">
                    <el-icon><DocumentCopy/></el-icon>
                    JSON格式 - 便于机器解析
                  </span>
                </el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="输出位置">
              <div class="output-options">
                <div class="output-option">
                  <el-switch
                      v-model="config.log.toFile"
                      active-text="文件输出"
                      inactive-text="不输出到文件"
                  />
                  <el-icon :class="{ active: config.log.toFile }" class="option-icon">
                    <FolderOpened/>
                  </el-icon>
                </div>
                <div class="output-option">
                  <el-switch
                      v-model="config.log.toConsole"
                      active-text="控制台输出"
                      inactive-text="不输出到控制台"
                  />
                  <el-icon :class="{ active: config.log.toConsole }" class="option-icon">
                    <Monitor/>
                  </el-icon>
                </div>
              </div>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <el-tab-pane name="database">
        <template #label>
          <span class="tab-label">
            <el-icon><Coin/></el-icon>
            数据存储
            <el-badge v-if="hasDbConnectionIssue" class="tab-badge" is-dot/>
          </span>
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
import {ElMessage, ElMessageBox, ElNotification} from 'element-plus'
import {
  Check,
  CircleCheck,
  CircleClose,
  CircleCloseFilled,
  Coin,
  Connection,
  Cpu,
  Document,
  DocumentCopy,
  Edit,
  FolderOpened,
  InfoFilled,
  Memo,
  Monitor,
  Platform,
  Promotion,
  RefreshLeft,
  Setting,
  Tickets,
  Trophy,
  View,
  WarningFilled
} from '@element-plus/icons-vue'
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

const resetConfig = async () => {
  try {
    await ElMessageBox.confirm(
        '确定要重置所有配置为默认值吗？此操作不可恢复。',
        '重置配置',
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning',
        }
    )

    // 重新加载配置
    await loadConfig()
    ElMessage.success('配置已重置为默认值')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('重置配置失败')
    }
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

<style lang="scss" scoped>
@use '@/assets/styles/design-tokens.scss' as tokens;

.config-view {
  padding: tokens.$spacing-6;
  background: var(--bg-color);
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: tokens.$spacing-8;
  padding: tokens.$spacing-6;
  background: var(--card-bg);
  border-radius: tokens.$radius-xl;
  box-shadow: tokens.$shadow-sm;

  .header-content {
    .page-title {
      margin: 0 0 tokens.$spacing-2 0;
      font-size: tokens.$font-size-3xl;
      font-weight: tokens.$font-weight-bold;
      color: var(--text-primary);
      display: flex;
      align-items: center;
      gap: tokens.$spacing-3;

      .title-icon {
        font-size: 36px;
        @include tokens.gradient-text(tokens.$brand-primary, tokens.$brand-secondary);
      }
    }

    .page-subtitle {
      margin: 0;
      font-size: tokens.$font-size-base;
      color: var(--text-secondary);
      padding-left: 48px;
    }
  }

  .header-actions {
    display: flex;
    gap: tokens.$spacing-3;

    .el-button {
      padding: tokens.$spacing-2 tokens.$spacing-4;
      height: 40px;

      .el-icon {
        margin-right: tokens.$spacing-1;
      }
    }
  }
}

.config-tabs {
  background: transparent;

  :deep(.el-tabs__nav-wrap) {
    &::after {
      display: none;
    }
  }

  :deep(.el-tabs__item) {
    height: 48px;
    padding: 0 tokens.$spacing-5;
    font-size: tokens.$font-size-base;
    font-weight: tokens.$font-weight-medium;
    color: var(--text-secondary);
    border: none;
    transition: all tokens.$duration-base;

    &:hover {
      color: tokens.$brand-primary;
    }

    &.is-active {
      color: tokens.$brand-primary;
      background: rgba(tokens.$brand-primary, 0.1);
      border-radius: tokens.$radius-base;

      .tab-label {
        font-weight: tokens.$font-weight-semibold;
      }
    }
  }

  .tab-label {
    display: flex;
    align-items: center;
    gap: tokens.$spacing-2;

    .el-icon {
      font-size: 18px;
    }
  }

  .tab-badge {
    margin-left: tokens.$spacing-2;
  }
}

.config-card {
  margin-top: tokens.$spacing-5;
  border-radius: tokens.$radius-lg;
  box-shadow: tokens.$shadow-sm;

  &:hover {
    box-shadow: tokens.$shadow-md;
  }

  :deep(.el-form) {
    padding: tokens.$spacing-2 0;

    .el-form-item {
      margin-bottom: tokens.$spacing-6;

      &__label {
        font-weight: tokens.$font-weight-medium;
        color: var(--text-primary);
      }
    }
  }

  .form-item-tip {
    margin-left: tokens.$spacing-3;
    font-size: tokens.$font-size-sm;
    color: var(--text-secondary);
  }

  .option-label {
    display: flex;
    align-items: center;
    gap: tokens.$spacing-2;

    .el-icon {
      font-size: 16px;
    }
  }

  .output-options {
    display: flex;
    gap: tokens.$spacing-8;

    .output-option {
      display: flex;
      align-items: center;
      gap: tokens.$spacing-3;

      .option-icon {
        font-size: 24px;
        color: var(--text-secondary);
        transition: all tokens.$duration-base;

        &.active {
          color: tokens.$brand-primary;
        }
      }
    }
  }
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: tokens.$spacing-1 0;

  span {
    font-weight: tokens.$font-weight-semibold;
    font-size: tokens.$font-size-lg;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    position: relative;
    padding-left: tokens.$spacing-6;

    &::before {
      content: '';
      position: absolute;
      left: 0;
      width: 4px;
      height: 24px;
      @include tokens.gradient-bg(tokens.$brand-primary, tokens.$brand-secondary);
      border-radius: tokens.$radius-sm;
    }
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: tokens.$spacing-3;
  }

  .el-tag {
    border-radius: tokens.$radius-full;
    padding: tokens.$spacing-1 tokens.$spacing-3;
    font-size: tokens.$font-size-sm;
    font-weight: tokens.$font-weight-medium;
  }

  .el-button {
    border-radius: tokens.$radius-base;
    height: 36px;
    padding: 0 tokens.$spacing-4;
    font-size: tokens.$font-size-sm;
  }
}

/* 数据库配置卡片样式 */
.el-card {
  border-radius: tokens.$radius-lg;
  border: none;
  transition: all tokens.$duration-base tokens.$ease-out;

  &:hover {
    box-shadow: tokens.$shadow-md;
    transform: translateY(-2px);
  }
}

/* 数据库表单样式 */
.database-form {
  padding: tokens.$spacing-3 tokens.$spacing-5;

  .el-form-item {
    margin-bottom: tokens.$spacing-6;

    &:last-child {
      margin-bottom: tokens.$spacing-4;
    }
  }

  .el-input, .el-select {
    width: 100%;
  }

  :deep(.el-input__inner) {
    border-radius: tokens.$radius-base;
    height: 40px;
    transition: all tokens.$duration-fast;

    &:focus {
      border-color: tokens.$brand-primary;
      box-shadow: 0 0 0 3px rgba(tokens.$brand-primary, 0.15);
    }
  }

  :deep(.el-select .el-input__inner) {
    cursor: pointer;
  }

  .el-input-number {
    width: 200px;

    :deep(.el-input__inner) {
      text-align: left;
    }
  }

  :deep(.el-form-item__label) {
    font-weight: tokens.$font-weight-medium;
    color: var(--text-primary);
    font-size: tokens.$font-size-sm;
  }
}

/* 保存按钮样式优化 */
.header-right {
  .el-button[type="success"] {
    font-weight: tokens.$font-weight-medium;

    &:hover {
      transform: translateY(-1px);
      box-shadow: tokens.$shadow-success;
    }
  }

  .el-button[type="warning"] {
    font-weight: tokens.$font-weight-semibold;
    animation: pulse 2s infinite;

    &:hover {
      transform: translateY(-1px);
      box-shadow: 0 2px 8px rgba(tokens.$color-warning, 0.3);
    }
  }
}

/* 数据库页签内容样式 */
.database-tab-content {
  .el-card {
    margin-bottom: tokens.$spacing-6;

    &:last-child {
      margin-bottom: 0;
    }
  }

  /* 密码记住选项样式 */
  .el-checkbox {
    font-size: tokens.$font-size-sm;
    color: var(--text-regular);

    :deep(.el-checkbox__label) {
      padding-left: tokens.$spacing-2;
    }
  }
}

/* 必填项标记 */
:deep(.el-form-item.is-required) {
  .el-form-item__label::before {
    content: '*';
    color: tokens.$color-danger;
    margin-right: tokens.$spacing-1;
  }
}

/* 错误输入框样式 */
:deep(.el-input.is-error .el-input__wrapper) {
  box-shadow: 0 0 0 1px tokens.$color-danger inset;
}

/* 响应式 */
@media (max-width: tokens.$breakpoint-md) {
  .config-view {
    padding: tokens.$spacing-4;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: tokens.$spacing-4;

    .header-content {
      .page-title {
        font-size: tokens.$font-size-2xl;
      }
    }

    .header-actions {
      width: 100%;
      justify-content: flex-end;
    }
  }

  .config-tabs {
    :deep(.el-tabs__item) {
      padding: 0 tokens.$spacing-3;

      .tab-label {
        font-size: tokens.$font-size-sm;

        .el-icon {
          font-size: 16px;
        }
      }
    }
  }
}

/* 暗色主题 */
.dark {
  .config-card {
    @include tokens.dark-glassmorphism(0.95, 5px);
  }
}
</style>