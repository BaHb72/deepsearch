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
        <el-card shadow="never" style="margin-bottom: 20px">
          <template #header>
            <div class="card-header">
              <span>主数据库配置</span>
              <el-tag size="small" type="info">用于存储交易数据、历史记录等</el-tag>
            </div>
          </template>
          <el-form :model="config.database.main" label-width="120px">
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
              <el-input v-model="config.database.main.password" show-password type="password"/>
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
              <el-tag size="small" type="success">用于高速缓存、消息队列等</el-tag>
            </div>
          </template>
          <el-form :model="config.database.cache" label-width="120px">
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
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import {onMounted, ref} from 'vue'
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
      // 合并配置，保留前端的数据结构
      if (data.basic) {
        Object.assign(config.value.basic, data.basic)
      }
      if (data.event) {
        Object.assign(config.value.event, data.event)
      }
      if (data.log) {
        Object.assign(config.value.log, data.log)
      }
      // 处理数据库配置
      if (data.database) {
        // 如果后端返回旧格式，转换为新格式
        if (data.database.redisHost !== undefined) {
          config.value.database.cache = {
            enabled: true,
            host: data.database.redisHost || 'localhost',
            port: data.database.redisPort || 6379,
            password: data.database.redisPassword || '',
            db: data.database.redisDb || 0,
            poolSize: data.database.poolSize || 10
          }
        } else if (data.database.main || data.database.cache) {
          // 新格式，直接合并
          if (data.database.main) {
            Object.assign(config.value.database.main, data.database.main)
          }
          if (data.database.cache) {
            Object.assign(config.value.database.cache, data.database.cache)
          }
        }
      }
    }
  } catch (error) {
    console.error('Failed to load config:', error)
  }
}

const saveConfig = async () => {
  try {
    // 转换数据格式以匹配后端期望的格式
    const dataToSave = {
      basic: config.value.basic,
      event: config.value.event,
      log: config.value.log,
      database: {
        // 根据后端需求，可能需要转换格式
        // 暂时保持新格式
        main: config.value.database.main,
        cache: config.value.database.cache
      }
    }
    
    const response = await fetch('/api/config', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(dataToSave)
    })

    if (response.ok) {
      ElMessage.success('配置保存成功')
    } else {
      const errorData = await response.json()
      ElMessage.error(errorData.message || '保存失败')
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

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;

  span {
    font-weight: 600;
    font-size: 16px;
  }

  .el-tag {
    margin-left: 10px;
  }
}

/* 数据库配置卡片样式 */
.el-card {
  border-radius: 8px;

  &:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    transition: box-shadow 0.3s ease;
  }
}
</style>