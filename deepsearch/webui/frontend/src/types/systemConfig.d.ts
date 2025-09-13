/**
 * 系统配置相关的类型定义
 */

export interface DataSource {
  id: number
  name: string
  type: 'akshare' | 'amazingdata' | 'qmt' | 'cloudflare'
  enabled: boolean
  priority: number
  config: {
    host?: string
    port?: number
    apiKey?: string
    workerUrl?: string
    timeout?: number
    retryCount?: number
    rateLimit?: number
  }
  status: 'online' | 'offline' | 'error' | 'degraded'
  lastCheck?: string
  successRate?: number
  avgResponseTime?: number
  error?: string
}

export interface DatabaseConnection {
  id: number
  name: string
  type: 'postgresql' | 'mysql' | 'duckdb' | 'redis' | 'mongodb'
  host?: string
  port?: number
  database?: string
  username?: string
  password?: string
  status: 'connected' | 'disconnected' | 'error'
  isDefault?: boolean
  poolSize?: number
  maxConnections?: number
  connectionTimeout?: number
  lastConnected?: string
  error?: string
}

export interface SystemModule {
  id: string
  name: string
  description: string
  status: 'running' | 'stopped' | 'error' | 'starting' | 'stopping'
  autoStart: boolean
  uptime?: number
  cpu?: number
  memory?: number
  lastStarted?: string
  lastStopped?: string
  errorCount?: number
  config?: Record<string, any>
  dependencies?: string[]
  version?: string
}

export interface ModuleLog {
  timestamp: string
  level: 'info' | 'warning' | 'error'
  message: string
}

export interface DataSourceFormProps {
  initialValues?: DataSource
  onSubmit: (values: DataSource) => Promise<void>
}

export interface DatabaseFormProps {
  initialValues?: DatabaseConnection
  onSubmit: (values: DatabaseConnection) => Promise<void>
}

export interface RateLimitEditorProps {
  value: number
  onChange: (value: number) => void
}