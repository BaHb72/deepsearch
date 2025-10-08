import request from '../api/request'

const systemService = {
  // 获取系统信息
  async getSystemInfo() {
    try {
      const response = await request.get('/system/info')
      return { data: response }
    } catch (error) {
      console.error('获取系统信息失败:', error)
      return { data: {} }
    }
  },

  // 健康检查
  async healthCheck() {
    try {
      const response = await request.get('/health')
      return { data: response }
    } catch (error) {
      console.error('健康检查失败:', error)
      return { 
        data: {
          status: 'unhealthy',
          components: {}
        }
      }
    }
  },

  // 获取统计数据
  async getStatistics() {
    try {
      const response = await request.get('/system/statistics')
      return { data: response }
    } catch (error) {
      console.error('获取统计数据失败:', error)
      return { 
        data: {
          api_requests: 0,
          active_connections: 0,
          api_requests_trend: 0
        }
      }
    }
  },

  // 获取系统状态
  async getSystemStatus() {
    try {
      const response = await request.get('/system/status')
      return { data: response }
    } catch (error) {
      console.error('获取系统状态失败:', error)
      return { data: {} }
    }
  },

  // 获取系统配置
  async getSystemConfig() {
    try {
      const response = await request.get('/config')
      return { data: response }
    } catch (error) {
      console.error('获取系统配置失败:', error)
      return { data: {} }
    }
  },

  // 更新系统配置
  async updateSystemConfig(config) {
    try {
      const response = await request.post('/config', config)
      return { data: response, success: true }
    } catch (error) {
      console.error('更新系统配置失败:', error)
      return { success: false, error: error.message }
    }
  },

  // 重启系统
  async restartSystem() {
    try {
      const response = await request.post('/system/restart')
      return { data: response, success: true }
    } catch (error) {
      console.error('重启系统失败:', error)
      return { success: false, error: error.message }
    }
  },

  // 获取组件状态
  async getComponentStatus() {
    try {
      const response = await request.get('/system/components/status')
      return { data: response }
    } catch (error) {
      console.error('获取组件状态失败:', error)
      return { 
        data: {
          event_engine: 'unknown',
          message_bus: 'unknown',
          data_provider: 'unknown',
          cache_system: 'unknown',
          gateway: 'unknown',
          database: 'unknown'
        }
      }
    }
  },

  // 获取系统告警
  async getAlerts() {
    try {
      const response = await request.get('/system/alerts')
      return { data: response }
    } catch (error) {
      console.error('获取系统告警失败:', error)
      return { data: [] }
    }
  },

  // 获取性能指标
  async getPerformanceMetrics() {
    try {
      const response = await request.get('/system/performance')
      return { data: response }
    } catch (error) {
      console.error('获取性能指标失败:', error)
      return { 
        data: {
          event_rate: 0,
          queue_depth: 0,
          cache_hit_rate: 0,
          avg_response_time: 0
        }
      }
    }
  }
}

export default systemService