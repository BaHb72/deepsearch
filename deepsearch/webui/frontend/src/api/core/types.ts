/**
 * API 核心类型定义
 * 统一的数据接口层类型系统
 */

// HTTP 方法枚举
export enum HttpMethod {
  GET = 'GET',
  POST = 'POST',
  PUT = 'PUT',
  DELETE = 'DELETE',
  PATCH = 'PATCH'
}

// API 分类枚举
export enum ApiCategory {
  SYSTEM = 'system',      // 系统管理
  DATABASE = 'database',  // 数据库操作
  MARKET = 'market',      // 市场数据
  TRADING = 'trading',    // 交易相关
  MONITOR = 'monitor',    // 监控相关
  DATA_SOURCE = 'dataSource' // 数据源管理
}

// 错误码标准化
export enum ApiErrorCode {
  // 客户端错误 4xxx
  INVALID_REQUEST = 4001,
  UNAUTHORIZED = 4010,
  FORBIDDEN = 4030,
  NOT_FOUND = 4040,
  RATE_LIMITED = 4290,
  
  // 服务端错误 5xxx
  INTERNAL_ERROR = 5000,
  SERVICE_UNAVAILABLE = 5030,
  GATEWAY_TIMEOUT = 5040,
  DATA_SOURCE_ERROR = 5100
}

// API 配置接口
export interface ApiConfig {
  // 基础配置
  url: string
  method?: HttpMethod
  params?: Record<string, any>
  data?: any
  headers?: Record<string, string>
  
  // 高级配置
  timeout?: number
  retries?: number
  cache?: boolean
  cacheDuration?: number
  dedupe?: boolean
  skipInterceptor?: boolean
  
  // 元数据
  category?: ApiCategory
  requestId?: string
  metadata?: Record<string, any>
}

// API 响应接口
export interface ApiResponse<T = any> {
  // 响应数据
  data: T
  status: number
  statusText: string
  headers: Record<string, string>
  
  // 元数据
  requestId: string
  timestamp: number
  duration: number
  cached?: boolean
  retryCount?: number
}

// API 错误接口
export interface ApiError extends Error {
  code: ApiErrorCode
  status?: number
  statusText?: string
  response?: ApiResponse
  requestId?: string
  timestamp?: number
  retry?: boolean
}

// 请求日志接口
export interface RequestLog {
  // 基础信息
  id: string
  timestamp: number
  category: ApiCategory
  
  // 请求信息
  method: HttpMethod
  url: string
  fullUrl: string
  params?: any
  data?: any
  headers?: Record<string, string>
  
  // 响应信息
  status?: number
  statusText?: string
  responseData?: any
  responseHeaders?: Record<string, string>
  
  // 性能指标
  duration?: number
  size?: number
  
  // 错误信息
  error?: ApiError
  errorMessage?: string
  errorStack?: string
  
  // 追踪信息
  trace: string[]
  metadata?: Record<string, any>
}

// 接口端点定义
export interface ApiEndpoint {
  // 基础信息
  id: string
  path: string
  method: HttpMethod
  category: ApiCategory
  
  // 描述信息
  name: string
  description: string
  version?: string
  deprecated?: boolean
  
  // 验证模式
  requestSchema?: any
  responseSchema?: any
  
  // 配置
  timeout?: number
  retries?: number
  cache?: CacheConfig
  rateLimit?: RateLimitConfig
  
  // 权限
  requireAuth?: boolean
  permissions?: string[]
}

// 缓存配置
export interface CacheConfig {
  enabled: boolean
  duration: number // 毫秒
  key?: string | ((config: ApiConfig) => string)
  invalidateOn?: string[] // 其他会使缓存失效的端点
}

// 限流配置
export interface RateLimitConfig {
  maxRequests: number
  windowMs: number
  message?: string
}

// 日志过滤器
export interface LogFilter {
  startTime?: number
  endTime?: number
  category?: ApiCategory
  status?: number[]
  method?: HttpMethod[]
  url?: string
  hasError?: boolean
  minDuration?: number
  maxDuration?: number
  limit?: number
}

// 健康检查规则
export interface HealthRule {
  name: string
  description: string
  check: (logs: RequestLog[]) => boolean
  threshold?: number
  action?: 'alert' | 'recover' | 'throttle'
}

// 健康问题
export interface HealthIssue {
  rule: HealthRule
  timestamp: number
  severity: 'low' | 'medium' | 'high' | 'critical'
  message: string
  affectedEndpoints?: string[]
  suggestedAction?: string
}

// 请求拦截器
export type RequestInterceptor = (config: ApiConfig) => ApiConfig | Promise<ApiConfig>

// 响应拦截器
export type ResponseInterceptor = (response: ApiResponse) => ApiResponse | Promise<ApiResponse>

// 错误拦截器
export type ErrorInterceptor = (error: ApiError) => ApiError | Promise<ApiError>

// 导出类型守卫函数
export function isApiError(error: any): error is ApiError {
  return error instanceof Error && 'code' in error
}

export function isApiResponse<T = any>(response: any): response is ApiResponse<T> {
  return response && 'data' in response && 'status' in response
}