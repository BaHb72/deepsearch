<template>
  <div class="cloudflare-tunnel-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1>Cloudflare Tunnel 管理</h1>
      <div class="header-actions">
        <el-button
            icon="el-icon-plus"
            type="primary"
            @click="showCreateDialog = true"
        >
          创建 Tunnel
        </el-button>
        <el-button
            icon="el-icon-refresh"
            @click="refreshData"
        >
          刷新
        </el-button>
      </div>
    </div>

    <!-- 状态概览卡片 -->
    <el-row :gutter="20" class="status-cards">
      <el-col :md="6" :sm="12" :xs="24">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-value">{{ tunnelStats.total }}</div>
            <div class="stat-label">总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :md="6" :sm="12" :xs="24">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-value text-success">{{ tunnelStats.running }}</div>
            <div class="stat-label">运行中</div>
          </div>
        </el-card>
      </el-col>
      <el-col :md="6" :sm="12" :xs="24">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-value text-warning">{{ tunnelStats.stopped }}</div>
            <div class="stat-label">已停止</div>
          </div>
        </el-card>
      </el-col>
      <el-col :md="6" :sm="12" :xs="24">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-value text-danger">{{ tunnelStats.error }}</div>
            <div class="stat-label">错误</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Tunnel 列表 -->
    <el-card class="tunnel-list-card">
      <div slot="header" class="card-header">
        <span>Tunnel 列表</span>
      </div>

      <el-table
          v-loading="loading"
          :data="tunnelList"
          style="width: 100%"
      >
        <el-table-column
            label="名称"
            min-width="150"
            prop="name"
        />

        <el-table-column
            label="状态"
            prop="status.state"
            width="120"
        >
          <template slot-scope="scope">
            <el-tag
                :type="getStatusType(scope.row.status.state)"
                size="small"
            >
              {{ getStatusText(scope.row.status.state) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column
            label="连接"
            prop="status.connected"
            width="100"
        >
          <template slot-scope="scope">
            <i
                :class="scope.row.status.connected ? 'el-icon-success text-success' : 'el-icon-error text-danger'"
            />
          </template>
        </el-table-column>

        <el-table-column
            label="主机名"
            min-width="200"
            prop="config.hostnames"
        >
          <template slot-scope="scope">
            <div v-if="scope.row.config.hostnames.length > 0">
              <el-tag
                  v-for="(hostname, index) in scope.row.config.hostnames"
                  :key="index"
                  class="hostname-tag"
                  size="mini"
              >
                {{ hostname.hostname }}
              </el-tag>
            </div>
            <span v-else class="text-muted">未配置</span>
          </template>
        </el-table-column>

        <el-table-column
            label="运行时间"
            prop="uptime_seconds"
            width="120"
        >
          <template slot-scope="scope">
            {{ formatUptime(scope.row.uptime_seconds) }}
          </template>
        </el-table-column>

        <el-table-column
            fixed="right"
            label="操作"
            width="250"
        >
          <template slot-scope="scope">
            <el-button-group>
              <el-button
                  v-if="scope.row.status.state === 'stopped'"
                  icon="el-icon-video-play"
                  size="mini"
                  type="success"
                  @click="startTunnel(scope.row.name)"
              >
                启动
              </el-button>
              <el-button
                  v-else-if="scope.row.status.state === 'running'"
                  icon="el-icon-video-pause"
                  size="mini"
                  type="danger"
                  @click="stopTunnel(scope.row.name)"
              >
                停止
              </el-button>
              <el-button
                  icon="el-icon-refresh"
                  size="mini"
                  type="warning"
                  @click="restartTunnel(scope.row.name)"
              >
                重启
              </el-button>
              <el-button
                  icon="el-icon-edit"
                  size="mini"
                  type="primary"
                  @click="editTunnel(scope.row)"
              >
                编辑
              </el-button>
              <el-button
                  icon="el-icon-delete"
                  size="mini"
                  type="danger"
                  @click="deleteTunnel(scope.row.name)"
              >
                删除
              </el-button>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建/编辑 Tunnel 对话框 -->
    <el-dialog
        :title="editMode ? '编辑 Tunnel' : '创建 Tunnel'"
        :visible.sync="showCreateDialog"
        width="60%"
        @close="resetForm"
    >
      <el-form
          ref="tunnelForm"
          :model="tunnelForm"
          :rules="formRules"
          label-width="120px"
      >
        <el-tabs v-model="activeTab">
          <!-- 基本配置 -->
          <el-tab-pane label="基本配置" name="basic">
            <el-form-item label="名称" prop="name">
              <el-input
                  v-model="tunnelForm.name"
                  :disabled="editMode"
                  placeholder="输入 Tunnel 名称"
              />
            </el-form-item>

            <el-form-item label="Token" prop="token">
              <el-input
                  v-model="tunnelForm.token"
                  :rows="3"
                  placeholder="输入 Tunnel Token (可选)"
                  type="textarea"
              />
            </el-form-item>

            <el-form-item label="协议" prop="protocol">
              <el-select v-model="tunnelForm.protocol" placeholder="选择协议">
                <el-option label="QUIC" value="quic"/>
                <el-option label="HTTP2" value="http2"/>
              </el-select>
            </el-form-item>

            <el-form-item label="日志级别" prop="loglevel">
              <el-select v-model="tunnelForm.loglevel" placeholder="选择日志级别">
                <el-option label="Debug" value="debug"/>
                <el-option label="Info" value="info"/>
                <el-option label="Warning" value="warning"/>
                <el-option label="Error" value="error"/>
              </el-select>
            </el-form-item>
          </el-tab-pane>

          <!-- 主机名配置 -->
          <el-tab-pane label="主机名配置" name="hostnames">
            <div class="hostname-section">
              <el-button
                  class="mb-2"
                  icon="el-icon-plus"
                  size="small"
                  type="primary"
                  @click="addHostname"
              >
                添加主机名
              </el-button>

              <div
                  v-for="(hostname, index) in tunnelForm.hostnames"
                  :key="index"
                  class="hostname-item"
              >
                <el-card shadow="never">
                  <el-row :gutter="10">
                    <el-col :span="8">
                      <el-form-item label="域名">
                        <el-input
                            v-model="hostname.hostname"
                            placeholder="例如: api.example.com"
                        />
                      </el-form-item>
                    </el-col>
                    <el-col :span="5">
                      <el-form-item label="服务类型">
                        <el-select v-model="hostname.service_type">
                          <el-option label="HTTP" value="http"/>
                          <el-option label="HTTPS" value="https"/>
                          <el-option label="TCP" value="tcp"/>
                          <el-option label="SSH" value="ssh"/>
                        </el-select>
                      </el-form-item>
                    </el-col>
                    <el-col :span="8">
                      <el-form-item label="服务地址">
                        <el-input
                            v-model="hostname.service_url"
                            placeholder="例如: localhost:8000"
                        />
                      </el-form-item>
                    </el-col>
                    <el-col :span="3">
                      <el-button
                          icon="el-icon-delete"
                          size="small"
                          type="danger"
                          @click="removeHostname(index)"
                      />
                    </el-col>
                  </el-row>
                </el-card>
              </div>
            </div>
          </el-tab-pane>

          <!-- 高级配置 -->
          <el-tab-pane label="高级配置" name="advanced">
            <el-form-item label="自动重启">
              <el-switch v-model="tunnelForm.auto_restart"/>
            </el-form-item>

            <el-form-item
                v-if="tunnelForm.auto_restart"
                label="重启延迟"
            >
              <el-input-number
                  v-model="tunnelForm.restart_delay"
                  :max="60"
                  :min="1"
              />
              <span class="ml-2">秒</span>
            </el-form-item>

            <el-form-item label="启用指标">
              <el-switch v-model="tunnelForm.metrics_enabled"/>
            </el-form-item>

            <el-form-item
                v-if="tunnelForm.metrics_enabled"
                label="指标端口"
            >
              <el-input-number
                  v-model="tunnelForm.metrics_port"
                  :max="65535"
                  :min="1024"
              />
            </el-form-item>
          </el-tab-pane>
        </el-tabs>
      </el-form>

      <span slot="footer" class="dialog-footer">
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button
            :loading="saving"
            type="primary"
            @click="saveTunnel"
        >
          {{ editMode ? '更新' : '创建' }}
        </el-button>
      </span>
    </el-dialog>
  </div>
</template>

<script>
import axios from 'axios'

export default {
  name: 'CloudflareTunnel',

  data() {
    return {
      // 列表数据
      tunnelList: [],
      loading: false,

      // 统计数据
      tunnelStats: {
        total: 0,
        running: 0,
        stopped: 0,
        error: 0
      },

      // 表单相关
      showCreateDialog: false,
      editMode: false,
      activeTab: 'basic',
      saving: false,

      // 表单数据
      tunnelForm: {
        name: '',
        token: '',
        protocol: 'quic',
        loglevel: 'info',
        hostnames: [],
        auto_restart: true,
        restart_delay: 5,
        metrics_enabled: true,
        metrics_port: 2000
      },

      // 表单验证规则
      formRules: {
        name: [
          {required: true, message: '请输入 Tunnel 名称', trigger: 'blur'}
        ]
      },

      // 自动刷新
      refreshTimer: null
    }
  },

  mounted() {
    this.fetchTunnelList()
    // 每 5 秒自动刷新
    this.refreshTimer = setInterval(() => {
      this.fetchTunnelList(true)
    }, 5000)
  },

  beforeDestroy() {
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer)
    }
  },

  methods: {
    // 获取 Tunnel 列表
    async fetchTunnelList(silent = false) {
      if (!silent) {
        this.loading = true
      }

      try {
        const response = await axios.get('/api/tunnel/list')
        if (response.data.success) {
          this.tunnelList = response.data.data
          this.updateStats()
        }
      } catch (error) {
        this.$message.error('获取 Tunnel 列表失败: ' + error.message)
      } finally {
        this.loading = false
      }
    },

    // 更新统计数据
    updateStats() {
      this.tunnelStats = {
        total: this.tunnelList.length,
        running: this.tunnelList.filter(t => t.status.state === 'running').length,
        stopped: this.tunnelList.filter(t => t.status.state === 'stopped').length,
        error: this.tunnelList.filter(t => t.status.state === 'error').length
      }
    },

    // 刷新数据
    refreshData() {
      this.fetchTunnelList()
      this.$message.success('已刷新')
    },

    // 启动 Tunnel
    async startTunnel(name) {
      try {
        const response = await axios.post(`/api/tunnel/${name}/start`)
        if (response.data.success) {
          this.$message.success(`Tunnel ${name} 已启动`)
          this.fetchTunnelList()
        }
      } catch (error) {
        this.$message.error('启动失败: ' + error.message)
      }
    },

    // 停止 Tunnel
    async stopTunnel(name) {
      try {
        const response = await axios.post(`/api/tunnel/${name}/stop`)
        if (response.data.success) {
          this.$message.success(`Tunnel ${name} 已停止`)
          this.fetchTunnelList()
        }
      } catch (error) {
        this.$message.error('停止失败: ' + error.message)
      }
    },

    // 重启 Tunnel
    async restartTunnel(name) {
      try {
        const response = await axios.post(`/api/tunnel/${name}/restart`)
        if (response.data.success) {
          this.$message.success(`Tunnel ${name} 已重启`)
          this.fetchTunnelList()
        }
      } catch (error) {
        this.$message.error('重启失败: ' + error.message)
      }
    },

    // 编辑 Tunnel
    editTunnel(tunnel) {
      this.editMode = true
      this.tunnelForm = {...tunnel.config}
      this.showCreateDialog = true
    },

    // 删除 Tunnel
    async deleteTunnel(name) {
      try {
        await this.$confirm(`确定要删除 Tunnel ${name} 吗?`, '确认删除', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })

        const response = await axios.delete(`/api/tunnel/${name}`)
        if (response.data.success) {
          this.$message.success(`Tunnel ${name} 已删除`)
          this.fetchTunnelList()
        }
      } catch (error) {
        if (error !== 'cancel') {
          this.$message.error('删除失败: ' + error.message)
        }
      }
    },

    // 添加主机名
    addHostname() {
      this.tunnelForm.hostnames.push({
        hostname: '',
        service_type: 'http',
        service_url: 'localhost:8000',
        path: null
      })
    },

    // 移除主机名
    removeHostname(index) {
      this.tunnelForm.hostnames.splice(index, 1)
    },

    // 保存 Tunnel
    async saveTunnel() {
      this.$refs.tunnelForm.validate(async (valid) => {
        if (!valid) {
          return
        }

        this.saving = true

        try {
          let response
          if (this.editMode) {
            response = await axios.put(
                `/api/tunnel/${this.tunnelForm.name}/config`,
                this.tunnelForm
            )
          } else {
            response = await axios.post('/api/tunnel/create', this.tunnelForm)
          }

          if (response.data.success) {
            this.$message.success(this.editMode ? '更新成功' : '创建成功')
            this.showCreateDialog = false
            this.fetchTunnelList()
            this.resetForm()
          }
        } catch (error) {
          this.$message.error('操作失败: ' + error.message)
        } finally {
          this.saving = false
        }
      })
    },

    // 重置表单
    resetForm() {
      this.editMode = false
      this.activeTab = 'basic'
      this.tunnelForm = {
        name: '',
        token: '',
        protocol: 'quic',
        loglevel: 'info',
        hostnames: [],
        auto_restart: true,
        restart_delay: 5,
        metrics_enabled: true,
        metrics_port: 2000
      }
      if (this.$refs.tunnelForm) {
        this.$refs.tunnelForm.clearValidate()
      }
    },

    // 获取状态类型
    getStatusType(state) {
      const types = {
        running: 'success',
        stopped: 'info',
        starting: 'warning',
        stopping: 'warning',
        error: 'danger',
        unknown: 'info'
      }
      return types[state] || 'info'
    },

    // 获取状态文本
    getStatusText(state) {
      const texts = {
        running: '运行中',
        stopped: '已停止',
        starting: '启动中',
        stopping: '停止中',
        error: '错误',
        unknown: '未知'
      }
      return texts[state] || state
    },

    // 格式化运行时间
    formatUptime(seconds) {
      if (!seconds) return '-'

      const days = Math.floor(seconds / 86400)
      const hours = Math.floor((seconds % 86400) / 3600)
      const minutes = Math.floor((seconds % 3600) / 60)

      if (days > 0) {
        return `${days}天${hours}时`
      } else if (hours > 0) {
        return `${hours}时${minutes}分`
      } else {
        return `${minutes}分`
      }
    }
  }
}
</script>

<style scoped>
.cloudflare-tunnel-page {
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
  text-align: center;
  padding: 10px;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #303133;
  line-height: 1.2;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 5px;
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

.text-muted {
  color: #909399;
}

.tunnel-list-card {
  margin-top: 20px;
}

.card-header {
  font-size: 16px;
  font-weight: 500;
}

.hostname-tag {
  margin-right: 5px;
  margin-bottom: 5px;
}

.hostname-section {
  padding: 10px;
}

.hostname-item {
  margin-bottom: 15px;
}

.mb-2 {
  margin-bottom: 10px;
}

.ml-2 {
  margin-left: 10px;
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

  .el-button-group {
    display: flex;
    flex-wrap: wrap;
  }
}
</style>