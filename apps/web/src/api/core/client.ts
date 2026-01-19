/**
 * 统一的 API 客户端
 * 所有 API 请求的单一入口
 */

import axios, {AxiosInstance, AxiosRequestConfig, AxiosResponse, InternalAxiosRequestConfig,} from 'axios'
import {
    ApiCategory,
    ApiConfig,
    HttpApiResponse,
    ErrorInterceptor,
    HttpMethod,
    RequestInterceptor,
    RequestLog,
    RequestMetadata,
    RequestMetadataInput,
    ResponseInterceptor,
} from './types'
import {ApiLogger} from './logger'
import {ApiMonitor} from './monitor'
import {ErrorHandler} from './error-handler'
import {RequestInterceptorManager} from './interceptors'

// 请求去重映射
interface PendingRequest<T = any> {
    promise: Promise<HttpApiResponse<T>>
  timestamp: number
}

// 超时配置（从后端同步）
interface TimeoutConfig {
  clientTimeoutMs: number
  timeoutsByOperation: Record<string, number>
  initialized: boolean
}

// 默认超时配置（后端同步前使用）
const DEFAULT_TIMEOUT_CONFIG: TimeoutConfig = {
  clientTimeoutMs: 90000,  // 90秒，覆盖首次调用场景
  timeoutsByOperation: {
    default: 30000,
    data_fetch: 90000,
    health_check: 5000,
    config_save: 10000,
  },
  initialized: false,
}

/**
 * 统一的 API 客户端类
 */
export class ApiClient {
  private static instance: ApiClient
  private axiosInstance: AxiosInstance
  private logger: ApiLogger
  private monitor: ApiMonitor
  private errorHandler: ErrorHandler
    private readonly interceptorManager: RequestInterceptorManager

  // 请求管理
  private pendingRequests: Map<string, PendingRequest> = new Map()
  private requestCounter: number = 0
  private readonly dedupeWindow: number = 100 // 去重时间窗口(ms)

  // 超时配置（从后端同步）
  private timeoutConfig: TimeoutConfig = { ...DEFAULT_TIMEOUT_CONFIG }

  private constructor() {
    // 初始化 axios 实例
    this.axiosInstance = this.createAxiosInstance()

    // 初始化各个模块
    this.logger = ApiLogger.getInstance()
    this.monitor = ApiMonitor.getInstance()
    this.errorHandler = new ErrorHandler()
    this.interceptorManager = new RequestInterceptorManager(this.axiosInstance)

    // 设置拦截器
    this.setupInterceptors()

    // 启动监控
    this.monitor.start()
  }

  /**
   * 获取单例实例
   */
  public static getInstance(): ApiClient {
    if (!ApiClient.instance) {
      ApiClient.instance = new ApiClient()
    }
    return ApiClient.instance
  }

  /**
   * 创建 axios 实例
   */
  private createAxiosInstance(): AxiosInstance {
    const instance = axios.create({
      // 使用配置的超时值（默认 90s，覆盖首次调用场景）
      timeout: this.timeoutConfig.clientTimeoutMs,
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      }
    })

    // 动态设置 baseURL
    const isDev = import.meta.env.DEV
    if (isDev) {
      // 开发环境使用代理
      instance.defaults.baseURL = '/api'
    } else {
      // 生产环境直接连接
      instance.defaults.baseURL = `${window.location.protocol}//${window.location.hostname}:8000/api`
    }

    return instance
  }

  /**
   * 从后端同步超时配置
   * 应在应用启动时调用，确保前后端超时一致
   */
  public async syncTimeoutConfig(): Promise<void> {
    if (this.timeoutConfig.initialized) {
      return  // 已初始化，跳过
    }

    try {
      // 直接使用 axios 避免循环依赖
      const response = await this.axiosInstance.get('/config/timeouts', {
        timeout: 5000,  // 获取配置的超时时间较短
      })

      if (response.data) {
        const config = response.data
        this.timeoutConfig = {
          clientTimeoutMs: config.client_timeout_ms ?? DEFAULT_TIMEOUT_CONFIG.clientTimeoutMs,
          timeoutsByOperation: config.timeouts_by_operation ?? DEFAULT_TIMEOUT_CONFIG.timeoutsByOperation,
          initialized: true,
        }

        // 更新 axios 实例的默认超时
        this.axiosInstance.defaults.timeout = this.timeoutConfig.clientTimeoutMs

        if (import.meta.env.DEV) {
          console.debug('[ApiClient] 超时配置已同步:', this.timeoutConfig)
        }
      }
    } catch (error) {
      // 同步失败时使用默认配置，不阻塞应用启动
      console.warn('[ApiClient] 同步超时配置失败，使用默认值:', error)
      this.timeoutConfig.initialized = true  // 标记为已初始化，避免重复尝试
    }
  }

  /**
   * 获取指定操作类型的超时时间
   */
  public getTimeoutForOperation(operation: string): number {
    return this.timeoutConfig.timeoutsByOperation[operation]
      ?? this.timeoutConfig.timeoutsByOperation['default']
      ?? this.timeoutConfig.clientTimeoutMs
  }

  /**
   * 发起请求（主要方法）
   */
  public async request<T = any>(config: ApiConfig): Promise<HttpApiResponse<T>> {
    const startTime = Date.now()
      const requestId = config.requestId ?? this.generateRequestId()
      const dedupeEnabled = config.dedupe !== false
      const dedupeKey = dedupeEnabled ? this.getDedupeKey(config) : null
      const method = config.method ?? HttpMethod.GET
      const metadataOverrides: Partial<RequestMetadata> = {
          requestId,
          startTime,
          category: config.category ?? ApiCategory.SYSTEM,
          retryCount: config.metadata?.retryCount ?? 0,
      }
      if (dedupeKey) {
          metadataOverrides.dedupeKey = dedupeKey
      }
      const metadata = this.mergeMetadata(config.metadata, metadataOverrides)
      let success = false

    try {
        if (dedupeEnabled && dedupeKey) {
        const pending = this.checkPendingRequest(dedupeKey)
        if (pending) {
          this.logger.logDedupe(requestId, dedupeKey)
          return pending.promise
        }
      }

      const axiosConfig: AxiosRequestConfig = {
        url: config.url,
          method,
        params: config.params,
        data: config.data,
        headers: {
            ...(config.headers ?? {}),
            'X-Request-ID': metadata.requestId,
        } as AxiosRequestConfig['headers'],
        timeout: config.timeout,
          metadata,
      }

      const requestPromise = this.executeRequest<T>(axiosConfig, config)

        if (dedupeEnabled && dedupeKey) {
            this.addPendingRequest(dedupeKey, requestPromise)
      }

        const result = await requestPromise
        success = true
        return result
    } catch (error) {
      const apiError = this.errorHandler.handle(error, requestId)

        const retries = config.retries ?? 0
        if (retries > 0) {
            this.logger.logRetry(requestId, retries)
            return this.retryRequest<T>(config, retries - 1)
      }

      throw apiError
    } finally {
        if (dedupeEnabled && dedupeKey) {
        this.removePendingRequest(dedupeKey)
      }

      this.monitor.recordRequest({
        requestId,
        duration: Date.now() - startTime,
          category: config.category ?? ApiCategory.SYSTEM,
          success,
          method,
          url: config.url,
      })
    }
  }

  /**
   * 获取日志
   */
  public useRequestInterceptor(name: string, interceptor: RequestInterceptor): void {
      this.interceptorManager.addRequestInterceptor(name, interceptor)
  }

    public useResponseInterceptor(name: string, interceptor: ResponseInterceptor): void {
        this.interceptorManager.addResponseInterceptor(name, interceptor)
    }

    public useErrorInterceptor(name: string, interceptor: ErrorInterceptor): void {
        this.interceptorManager.addErrorInterceptor(name, interceptor)
    }

    /**
     * 清除缓存
     */
    public clearCache(): void {
        this.pendingRequests.clear()
        this.monitor.reset()
        this.logger.clearLogs()
        if (import.meta.env.DEV) {
            console.debug('[ApiClient] 请求缓存已清空')
        }
    }

    /**
     * 设置拦截器
     */
    private setHeader(config: InternalAxiosRequestConfig, key: string, value: string): void {
        if (config.headers && typeof (config.headers as any).set === 'function') {
            (config.headers as any).set(key, value)
            return
        }

        const headers =
            config.headers && typeof config.headers === 'object'
                ? {...(config.headers as Record<string, string>)}
                : {}
        headers[key] = value
        config.headers = headers as typeof config.headers
    }

  /**
   * 重试请求
   */
  private async retryRequest<T>(
    config: ApiConfig,
    remainingRetries: number
  ): Promise<HttpApiResponse<T>> {
    // 等待一段时间后重试（指数退避）
    const delay = Math.min(1000 * Math.pow(2, config.retries! - remainingRetries), 10000)
    await new Promise(resolve => setTimeout(resolve, delay))

    return this.request<T>({
      ...config,
      retries: remainingRetries,
      metadata: {
        ...config.metadata,
        retryCount: (config.metadata?.retryCount || 0) + 1
      }
    })
  }

  /**
   * 生成请求 ID
   */
  private generateRequestId(): string {
    return `req_${Date.now()}_${++this.requestCounter}`
  }

  /**
   * 获取去重键
   */
  private getDedupeKey(config: ApiConfig): string {
    const method = config.method || HttpMethod.GET
    const url = config.url
    const params = JSON.stringify(config.params || {})
    const data = JSON.stringify(config.data || {})
    return `${method}:${url}:${params}:${data}`
  }

  /**
   * 检查待处理请求
   */
  private checkPendingRequest(key: string): PendingRequest | null {
    const pending = this.pendingRequests.get(key)
    if (pending) {
      const age = Date.now() - pending.timestamp
      if (age < this.dedupeWindow) {
        return pending
      }
      // 过期的请求，移除
      this.pendingRequests.delete(key)
    }
    return null
  }

    private getHeader(config: InternalAxiosRequestConfig, key: string): string | undefined {
        if (!config.headers) {
            return undefined
        }

        if (typeof (config.headers as any).get === 'function') {
            return (config.headers as any).get(key)
        }

        return (config.headers as Record<string, string | undefined>)[key] as string | undefined
    }

    private mergeMetadata(
        base: RequestMetadataInput | undefined,
        overrides: Partial<RequestMetadata>
    ): RequestMetadata {
        const result: Record<string, RequestMetadata[keyof RequestMetadata]> = {}

        if (base) {
            for (const [key, value] of Object.entries(base)) {
                if (value !== undefined) {
                    result[key] = value as RequestMetadata[keyof RequestMetadata]
                }
            }
        }

        for (const [key, value] of Object.entries(overrides)) {
            if (value !== undefined) {
                result[key] = value as RequestMetadata[keyof RequestMetadata]
            }
        }

        const requestId =
            (overrides.requestId ?? base?.requestId) ?? this.generateRequestId()
        const startTime = overrides.startTime ?? base?.startTime ?? Date.now()

        result.requestId = requestId
        result.startTime = startTime

        return result as RequestMetadata
    }

  /**
   * 移除待处理请求
   */
  private removePendingRequest(key: string): void {
    this.pendingRequests.delete(key)
  }

  // ========== 便捷方法 ==========

  /**
   * GET 请求
   */
  public get<T = any>(url: string, params?: any, config?: Partial<ApiConfig>): Promise<HttpApiResponse<T>> {
    return this.request<T>({
      ...config,
      url,
      method: HttpMethod.GET,
      params
    })
  }

  /**
   * POST 请求
   */
  public post<T = any>(url: string, data?: any, config?: Partial<ApiConfig>): Promise<HttpApiResponse<T>> {
    return this.request<T>({
      ...config,
      url,
      method: HttpMethod.POST,
      data
    })
  }

  /**
   * PUT 请求
   */
  public put<T = any>(url: string, data?: any, config?: Partial<ApiConfig>): Promise<HttpApiResponse<T>> {
    return this.request<T>({
      ...config,
      url,
      method: HttpMethod.PUT,
      data
    })
  }

  /**
   * DELETE 请求
   */
  public delete<T = any>(url: string, config?: Partial<ApiConfig>): Promise<HttpApiResponse<T>> {
    return this.request<T>({
      ...config,
      url,
      method: HttpMethod.DELETE
    })
  }

  // ========== 管理方法 ==========

    private ensureRequestMetadata(config: InternalAxiosRequestConfig): RequestMetadata {
        const existingHeader = this.getHeader(config, 'X-Request-ID')
        const metadata = this.mergeMetadata(config.metadata, {
            requestId: existingHeader ?? config.metadata?.requestId,
            startTime: config.metadata?.startTime,
        })

        this.setHeader(config, 'X-Request-ID', metadata.requestId)
        config.metadata = metadata

        return metadata
    }

    private setupInterceptors(): void {
        this.axiosInstance.interceptors.request.use(
            (config) => {
                const requestConfig = config as InternalAxiosRequestConfig
                const metadata = this.ensureRequestMetadata(requestConfig)
                const requestId = metadata.requestId
                const method = (requestConfig.method ?? HttpMethod.GET)
                    .toString()
                    .toUpperCase() as HttpMethod

                this.logger.logRequestStart({
                    requestId,
                    method,
                    url: requestConfig.url ?? '',
                    data: requestConfig.data,
                    params: requestConfig.params,
                    category: metadata.category ?? ApiCategory.SYSTEM
                })

                return requestConfig
            },
            (error) => {
                this.logger.logError(error)
                return Promise.reject(error)
            }
        )

        this.axiosInstance.interceptors.response.use(
            (response) => {
                const requestConfig = response.config as InternalAxiosRequestConfig
                const metadata = requestConfig.metadata
                const headerRequestId = this.getHeader(requestConfig, 'X-Request-ID')
                const requestId = headerRequestId ?? metadata?.requestId ?? 'unknown'
                const startTime = metadata?.startTime ?? Date.now()

                this.logger.logResponseSuccess({
                    requestId,
                    status: response.status,
                    data: response.data,
                    duration: Date.now() - startTime
                })

                return response
            },
            (error) => {
                const requestConfig = error?.config as InternalAxiosRequestConfig | undefined
                const metadata = requestConfig?.metadata
                const headerRequestId = requestConfig ? this.getHeader(requestConfig, 'X-Request-ID') : undefined
                const requestId = headerRequestId ?? metadata?.requestId ?? 'unknown'
                const startTime = metadata?.startTime ?? Date.now()

                this.logger.logResponseError({
                    requestId,
                    error,
                    duration: Date.now() - startTime
                })

                return Promise.reject(error)
            }
        )
    }

    private async executeRequest<T>(
        axiosConfig: AxiosRequestConfig,
        apiConfig: ApiConfig
    ): Promise<HttpApiResponse<T>> {
        const response: AxiosResponse<T> = await this.axiosInstance.request<T>(axiosConfig)
        const metadata = this.mergeMetadata(axiosConfig.metadata, {
            requestId: axiosConfig.metadata?.requestId ?? apiConfig.metadata?.requestId,
            startTime: axiosConfig.metadata?.startTime ?? Date.now(),
            retryCount: axiosConfig.metadata?.retryCount ?? apiConfig.metadata?.retryCount,
        })
        axiosConfig.metadata = metadata
        const startTime = metadata.startTime

        return {
            data: response.data,
            status: response.status,
            statusText: response.statusText,
            headers: response.headers as Record<string, string>,
            requestId: metadata.requestId,
            timestamp: Date.now(),
            duration: Date.now() - startTime,
            cached: false,
            retryCount: metadata.retryCount ?? 0,
        }
    }

  public getLogs(): RequestLog[] {
    return this.logger.getAllLogs()
  }

  /**
   * 获取监控指标
   */
  public getMetrics() {
    return this.monitor.getMetrics()
  }

    private addPendingRequest<T>(
        key: string,
        promise: Promise<HttpApiResponse<T>>
    ): void {
        this.pendingRequests.set(key, {
            promise,
            timestamp: Date.now()
        })
    }

  /**
   * 取消所有待处理请求
   */
  public cancelAll(): void {
    this.pendingRequests.clear()
  }
}

// 导出单例实例
export const apiClient = ApiClient.getInstance()
