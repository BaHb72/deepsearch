import request from './request'

// 系统信息接口
export interface SystemInfo {
  version: string
  environment: string
  uptime: number
  cpu_usage: number
  memory_usage: number
  disk_usage: number
}

// 健康检查响应
export interface HealthCheckResponse {
  status: string
  timestamp: string
  components: {
    [key: string]: {
      status: 'healthy' | 'unhealthy' | 'degraded'
      message?: string
    }
  }
}

// 系统配置
export interface SystemConfig {
  basic: {
    appName: string
    env: 'dev' | 'test' | 'prod'
    debug: boolean
  }
  server: {
    host: string
    port: number
    workers: number
  }
  database: {
    type: string
    host: string
    port: number
    name: string
  }
  cache: {
    enabled: boolean
    ttl: number
    maxSize: number
  }
}

// 系统API服务
class SystemService {
  // 获取系统信息
  async getSystemInfo() {
    return request.get<SystemInfo>('/system/info')
  }
  
  // 健康检查
  async healthCheck() {
    return request.get<HealthCheckResponse>('/health')
  }
  
  // 获取系统配置
  async getConfig() {
    return request.get<SystemConfig>('/system/config')
  }
  
  // 更新系统配置
  async updateConfig(config: Partial<SystemConfig>) {
    return request.post('/system/config', config)
  }
  
  // 重启系统
  async restart() {
    return request.post('/system/restart')
  }
  
  // 获取系统日志
  async getLogs(params?: {
    level?: 'debug' | 'info' | 'warning' | 'error'
    start_time?: string
    end_time?: string
    limit?: number
  }) {
    return request.get('/system/logs', params)
  }
  
  // 清理缓存
  async clearCache() {
    return request.post('/system/cache/clear')
  }
  
  // 获取系统统计
  async getStatistics() {
    return request.get('/system/statistics')
  }
}

export default new SystemService()