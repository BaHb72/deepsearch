import type {JsonObject} from './common'

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
  status:
    | 'draft'
    | 'pending_test'
    | 'testing'
    | 'ready'
    | 'active'
    | 'degraded'
    | 'error'
    | 'offline'
  available?: boolean
  lastCheck?: string
  lastTestTime?: string
  successRate?: number
  avgResponseTime?: number
  error?: string
  reason?: string
  hasSavedCredential?: boolean
  rememberCredential?: boolean
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
  status: string
  isDefault?: boolean
  poolSize?: number
  maxConnections?: number
  connectionTimeout?: number
  lastConnected?: string
  error?: string
  activation?: {
    state: 'active' | 'inactive' | 'pending' | 'error' | 'unknown'
    enabled: boolean
    updatedAt?: string
    error?: string | null
  }
  connectivity?: {
    state: 'connected' | 'connecting' | 'disconnected' | 'error' | 'unknown'
    lastSuccessAt?: string
    lastError?: string | null
    retrying?: boolean
  }
  deprecated?: {
    enabled?: boolean
    connected?: boolean
    status?: string
  }
  statusSource?: 'runtime' | 'stored'
  statusDetail?: string
  activeConnection?: boolean
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
  config?: JsonObject
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

export interface LogArchiveSettings {
    enabled: boolean
    format: string
    directory: string
    archive_after_days: number
    purge_after_days?: number | null
}

export interface ModuleLogSettings {
    enabled: boolean
    directory: string
    max_depth: number
    rotation?: string | null
    retention_days?: number | null
}

export interface LogSettings {
    level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL'
    rotation: string
    retention_days: number
    enable_json: boolean
    archive: LogArchiveSettings
    modules: ModuleLogSettings
}
