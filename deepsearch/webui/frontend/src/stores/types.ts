/**
 * Zustand Store 类型定义
 */

// 数据库连接类型
export interface DatabaseConnection {
  id: number
  name: string
  type: 'postgresql' | 'mysql' | 'sqlite' | 'duckdb'
  host?: string
  port?: number
  database: string
  username?: string
  password?: string
  isDefault: boolean
  connected: boolean
  status: 'connected' | 'disconnected' | 'connecting' | 'error'
  lastHealthCheck?: string
  error?: string
}

// 创建连接DTO
export interface CreateConnectionDTO {
  name: string
  type: 'postgresql' | 'mysql' | 'sqlite' | 'duckdb'
  host?: string
  port?: number
  database: string
  username?: string
  password?: string
  isDefault?: boolean
}

// 更新连接DTO
export interface UpdateConnectionDTO extends Partial<CreateConnectionDTO> {}

// 测试结果
export interface TestResult {
  success: boolean
  message: string
  latency?: number
  error?: string
}

// 数据源类型
export interface DataSource {
  id: string
  name: string
  type: string
  enabled: boolean
  priority: number
  config: Record<string, any>
  status: 'online' | 'offline' | 'error' | 'checking'
  lastCheck?: string
  statistics?: DataSourceStatistics
}

// 数据源统计
export interface DataSourceStatistics {
  totalRequests: number
  successfulRequests: number
  failedRequests: number
  avgResponseTime: number
  lastRequestTime?: string
  errorRate: number
  cacheHitRate: number
}

// 数据源状态
export interface DataSourceStatus {
  available: boolean
  message: string
  details: Record<string, any>
}

// 缓存条目
export interface CacheEntry<T = any> {
  data: T
  timestamp: number
  ttl: number
  key: string
}

// 通用错误类型
export interface StoreError {
  code: string
  message: string
  details?: any
  timestamp: number
}