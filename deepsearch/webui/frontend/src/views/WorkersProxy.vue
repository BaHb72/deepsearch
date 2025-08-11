<template>
  <div class="workers-proxy-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1>Cloudflare Workers 代理管理</h1>
      <div class="header-actions">
        <el-button
            :icon="proxyEnabled ? 'el-icon-switch-button' : 'el-icon-open'"
            :loading="toggleLoading"
            :type="proxyEnabled ? 'danger' : 'success'"
            @click="toggleProxy"
        >
          {{ proxyEnabled ? '关闭代理' : '开启代理' }}
        </el-button>
        <el-button
            icon="el-icon-refresh"
            @click="refreshStatus"
        >
          刷新
        </el-button>
      </div>
    </div>

    <!-- 状态卡片 -->
    <el-row :gutter="20" class="status-cards">
      <el-col :md="6" :sm="12" :xs="24">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-icon">
              <i :class="proxyEnabled ? 'el-icon-success text-success' : 'el-icon-error text-danger'"></i>
            </div>
            <div class="stat-content">
              <div class="stat-value">{{ proxyEnabled ? '已启用' : '已禁用' }}</div>
              <div class="stat-label">代理状态</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :md="6" :sm="12" :xs="24">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-icon">
              <i class="el-icon-link text-primary"></i>
            </div>
            <div class="stat-content">
              <div class="stat-value">{{ statistics.total_requests || 0 }}</div>
              <div class="stat-label">总请求数</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :md="6" :sm="12" :xs="24">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-icon">
              <i class="el-icon-circle-check text-success"></i>
            </div>
            <div class="stat-content">
              <div class="stat-value">{{ successRate }}%</div>
              <div class="stat-label">成功率</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :md="6" :sm="12" :xs="24">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-icon">
              <i class="el-icon-timer text-warning"></i>
            </div>
            <div class="stat-content">
              <div class="stat-value">{{ avgResponseTime }}ms</div>
              <div class="stat-label">平均响应时间</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 配置和状态 -->
    <el-row :gutter="20" class="main-content">
      <!-- 配置面板 -->
      <el-col :md="12" :xs="24">
        <el-card>
          <div slot="header" class="card-header">
            <span>代理配置</span>
            <el-button
                :loading="saving"
                size="small"
                type="primary"
                @click="saveConfig"
            >
              保存配置
            </el-button>
          </div>

          <el-form :model="config" label-width="120px">
            <el-form-item label="Workers URLs">
              <div class="workers-list">
                <div v-for="(worker, index) in config.workers" :key="index" class="worker-item">
                  <el-input
                      v-model="config.workers[index]"
                      class="worker-input"
                      placeholder="例如: your-worker.workers.dev"
                  >
                    <template slot="prepend">https://</template>
                  </el-input>
                  <el-button
                      :disabled="config.workers.length <= 1"
                      circle
                      class="delete-btn"
                      icon="el-icon-delete"
                      size="small"
                      type="danger"
                      @click="removeWorker(index)"
                  />
                </div>
                <el-button
                    class="add-worker-btn"
                    icon="el-icon-plus"
                    size="small"
                    type="primary"
                    @click="addWorker"
                >
                  添加 Worker
                </el-button>
              </div>
            </el-form-item>

            <el-form-item label="API 密钥">
              <el-input
                  v-model="config.api_key"
                  placeholder="可选：填写你的 Cloudflare Worker 自定义密钥/令牌（非全局 Cloudflare API Key）"
                  show-password
                  type="password"
              />
              <div class="form-tip">说明：这里应填写你在 Cloudflare Worker 中自定义用于校验的密钥（例如通过请求头
                X-API-Key 或 Bearer Token 校验）。不要填 Cloudflare 账户的全局 API Key。
              </div>
            </el-form-item>

            <el-form-item label="超时时间">
              <el-input-number
                  v-model="config.timeout"
                  :max="120"
                  :min="5"
              />
              <span class="ml-2">秒</span>
            </el-form-item>

            <el-form-item label="重试次数">
              <el-input-number
                  v-model="config.retry_count"
                  :max="5"
                  :min="0"
              />
            </el-form-item>

            <el-form-item label="故障转移">
              <el-switch
                  v-model="config.fallback_to_direct"
                  active-text="启用"
                  inactive-text="禁用"
              />
              <div class="form-tip">Workers 失败时自动切换到直连</div>
            </el-form-item>

            <el-form-item label="启用缓存">
              <el-switch
                  v-model="config.cache_enabled"
                  active-text="启用"
                  inactive-text="禁用"
              />
            </el-form-item>

            <el-form-item v-if="config.cache_enabled" label="缓存时间">
              <el-input-number
                  v-model="config.cache_ttl"
                  :max="3600"
                  :min="60"
              />
              <span class="ml-2">秒</span>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 统计面板 -->
      <el-col :md="12" :xs="24">
        <el-card>
          <div slot="header" class="card-header">
            <span>运行统计</span>
            <el-button-group>
              <el-button
                  :loading="testing"
                  size="small"
                  @click="testConnection"
              >
                测试连接
              </el-button>
              <el-button
                  size="small"
                  @click="clearCache"
              >
                清空缓存
              </el-button>
              <el-button
                  size="small"
                  @click="resetStatistics"
              >
                重置统计
              </el-button>
            </el-button-group>
          </div>

          <div class="statistics-panel">
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="总请求数">
                {{ statistics.total_requests || 0 }}
              </el-descriptions-item>
              <el-descriptions-item label="成功请求">
                <span class="text-success">{{ statistics.successful_requests || 0 }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="失败请求">
                <span class="text-danger">{{ statistics.failed_requests || 0 }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="降级次数">
                <span class="text-warning">{{ statistics.fallback_count || 0 }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="平均响应时间">
                {{ (statistics.avg_response_time || 0).toFixed(2) }} ms
              </el-descriptions-item>
              <el-descriptions-item label="最后响应时间">
                {{ (statistics.last_response_time || 0).toFixed(2) }} ms
              </el-descriptions-item>
              <el-descriptions-item label="发送数据">
                {{ formatBytes(statistics.bytes_sent || 0) }}
              </el-descriptions-item>
              <el-descriptions-item label="接收数据">
                {{ formatBytes(statistics.bytes_received || 0) }}
              </el-descriptions-item>
              <el-descriptions-item label="缓存大小">
                {{ cacheSize }} 项
              </el-descriptions-item>
              <el-descriptions-item label="最后请求">
                {{ formatTime(statistics.last_request_at) }}
              </el-descriptions-item>
            </el-descriptions>

            <!-- 错误信息 -->
            <el-alert
                v-if="statistics.last_error"
                :closable="false"
                :description="statistics.last_error"
                :title="'最后错误: ' + formatTime(statistics.last_error_at)"
                class="mt-3"
                type="error"
            />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 测试结果对话框 -->
    <el-dialog
        v-model="showTestResult"
        title="连接测试结果"
        width="500px"
    >
      <div v-if="testResult">
        <el-result
            :icon="testResult.success ? 'success' : 'error'"
            :title="testResult.success ? '连接成功' : '连接失败'"
        >
          <template slot="subTitle">
            <p>响应时间: {{ testResult.response_time.toFixed(2) }} ms</p>
            <p v-if="testResult.workers_version">Workers 版本: {{ testResult.workers_version }}</p>
          </template>
          <template slot="extra">
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="消息">
                {{ testResult.message }}
              </el-descriptions-item>
              <el-descriptions-item v-if="testResult.status_code" label="状态码">
                {{ testResult.status_code }}
              </el-descriptions-item>
              <el-descriptions-item v-if="testResult.error" label="错误">
                <span class="text-danger">{{ testResult.error }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="测试时间">
                {{ formatTime(testResult.timestamp) }}
              </el-descriptions-item>
            </el-descriptions>
          </template>
        </el-result>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import request from '@/api/request'

export default {
  name: 'WorkersProxy',

  data() {
    return {
      // 代理状态
      proxyEnabled: false,
      proxyStatus: 'disabled',

      // 配置
      config: {
        enabled: false,
        workers: ['wandering-sea-d394.934073514.workers.dev'],  // 改为数组
        api_key: '',
        timeout: 30,
        retry_count: 3,
        retry_delay: 1,
        fallback_to_direct: true,
        cache_enabled: true,
        cache_ttl: 300
      },

      // 统计信息
      statistics: {},
      cacheSize: 0,

      // 加载状态
      loading: false,
      saving: false,
      testing: false,
      toggleLoading: false,

      // 测试结果
      showTestResult: false,
      testResult: null,

      // 自动刷新
      refreshTimer: null
    }
  },

  computed: {
    successRate() {
      const total = this.statistics.total_requests || 0
      const success = this.statistics.successful_requests || 0
      return total > 0 ? ((success / total) * 100).toFixed(1) : 0
    },

    avgResponseTime() {
      return (this.statistics.avg_response_time || 0).toFixed(0)
    }
  },

  mounted() {
    this.fetchStatus()
    // 每10秒自动刷新统计
    this.refreshTimer = setInterval(() => {
      this.fetchStatus(true)
    }, 10000)
  },

  beforeDestroy() {
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer)
    }
  },

  methods: {
    // 获取状态
    async fetchStatus(silent = false) {
      if (!silent) {
        this.loading = true
      }

      try {
        const response = await request.get('/workers/status')
        if (response.success) {
          const data = response.data
          this.proxyEnabled = data.enabled
          this.proxyStatus = data.status

          // 保存当前的 API 密钥（如果有）
          const currentApiKey = this.config.api_key

          // 更新配置
          this.config = {...data.config}

          // 处理 workers 配置：兼容新旧格式
          if (data.config.workers && Array.isArray(data.config.workers) && data.config.workers.length > 0) {
            // 使用 workers 数组
            this.config.workers = data.config.workers
          } else if (data.config.url) {
            // 向后兼容：单个 url 转换为数组
            this.config.workers = [data.config.url]
          } else {
            // 默认值
            this.config.workers = ['wandering-sea-d394.934073514.workers.dev']
          }

          // 如果服务器返回的是掩码值，保留本地输入的 API 密钥
          if (data.config.api_key === '******' && currentApiKey) {
            this.config.api_key = currentApiKey
          }

          this.statistics = data.statistics || {}
          this.cacheSize = data.cache_size || 0
        }
      } catch (error) {
        if (!silent) {
          this.$message.error('获取状态失败: ' + error.message)
        }
      } finally {
        this.loading = false
      }
    },

    // 刷新状态
    refreshStatus() {
      this.fetchStatus()
      this.$message.success('已刷新')
    },

    // 切换代理
    async toggleProxy() {
      this.toggleLoading = true

      try {
        const response = await request.post('/workers/toggle')
        if (response.success) {
          this.proxyEnabled = response.enabled
          this.$message.success(
              this.proxyEnabled ? '代理已启用' : '代理已禁用'
          )
          this.fetchStatus()
        }
      } catch (error) {
        this.$message.error('切换失败: ' + error.message)
      } finally {
        this.toggleLoading = false
      }
    },

    // 保存配置
    async saveConfig() {
      this.saving = true

      try {
        const response = await request.post('/workers/config', this.config)
        if (response.success) {
          this.$message.success('配置已保存')
          this.fetchStatus()
        }
      } catch (error) {
        this.$message.error('保存失败: ' + error.message)
      } finally {
        this.saving = false
      }
    },

    // 测试连接
    async testConnection() {
      this.testing = true

      try {
        const response = await request.get('/workers/test')
        if (response.success) {
          this.testResult = response.data
          this.showTestResult = true
        }
      } catch (error) {
        this.$message.error('测试失败: ' + error.message)
      } finally {
        this.testing = false
      }
    },

    // 清空缓存
    async clearCache() {
      try {
        await this.$confirm('确定要清空缓存吗?', '确认', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })

        const response = await request.post('/workers/clear-cache')
        if (response.success) {
          this.$message.success('缓存已清空')
          this.fetchStatus()
        }
      } catch (error) {
        if (error !== 'cancel') {
          this.$message.error('操作失败: ' + error.message)
        }
      }
    },

    // 重置统计
    async resetStatistics() {
      try {
        await this.$confirm('确定要重置统计信息吗?', '确认', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })

        const response = await request.post('/workers/reset-statistics')
        if (response.success) {
          this.$message.success('统计已重置')
          this.fetchStatus()
        }
      } catch (error) {
        if (error !== 'cancel') {
          this.$message.error('操作失败: ' + error.message)
        }
      }
    },

    // 格式化字节数
    formatBytes(bytes) {
      if (bytes === 0) return '0 B'
      const k = 1024
      const sizes = ['B', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
    },

    // 格式化时间
    formatTime(timestamp) {
      if (!timestamp) return '-'
      const date = new Date(timestamp)
      return date.toLocaleString('zh-CN')
    },

    // 添加 Worker
    addWorker() {
      this.config.workers.push('')
      this.$message.success('已添加新的 Worker 配置项')
    },

    // 移除 Worker
    removeWorker(index) {
      if (this.config.workers.length > 1) {
        this.config.workers.splice(index, 1)
        this.$message.success('已移除 Worker 配置项')
      } else {
        this.$message.warning('至少需要保留一个 Worker URL')
      }
    }
  }
}
</script>

<style scoped>
.workers-proxy-page {
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
  font-size: 24px;
  color: #303133;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.status-cards {
  margin-bottom: 20px;
}

.stat-item {
  display: flex;
  align-items: center;
  padding: 10px;
}

.stat-icon {
  font-size: 32px;
  margin-right: 15px;
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
  line-height: 1.2;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 5px;
}

.main-content {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}

.statistics-panel {
  padding: 10px 0;
}

.text-success {
  color: #67c23a;
}

.text-warning {
  color: #e6a23c;
}

.text-danger {
  color: #f56c6c;
}

.text-primary {
  color: #409eff;
}

.ml-2 {
  margin-left: 10px;
}

.mt-3 {
  margin-top: 15px;
}

/* Workers 列表样式 */
.workers-list {
  width: 100%;
}

.worker-item {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
  gap: 10px;
}

.worker-input {
  flex: 1;
}

.delete-btn {
  flex-shrink: 0;
}

.add-worker-btn {
  margin-top: 5px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .header-actions {
    margin-top: 10px;
  }
}
</style>