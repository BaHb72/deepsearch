/**
 * 统一的 API 客户端
 * 所有 API 请求的单一入口
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { 
  ApiConfig, 
  ApiResponse, 
  ApiError,
  HttpMethod,
  ApiErrorCode,
  RequestLog,
  ApiCategory
} from './types'
import { ApiLogger } from './logger'
import { ApiMonitor } from './monitor'
import { ErrorHandler } from './error-handler'
import { RequestInterceptorManager } from './interceptors'

// 请求去重映射
interface PendingRequest {
  promise: Promise<any>
  timestamp: number
  config: ApiConfig
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
  private interceptorManager: RequestInterceptorManager
  
  // 请求管理
  private pendingRequests: Map<string, PendingRequest> = new Map()
  private requestCounter: number = 0
  private readonly dedupeWindow: number = 100 // 去重时间窗口(ms)
  
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
      timeout: 30000,
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
   * 设置拦截器
   */
  private setupInterceptors(): void {
    // 请求拦截器
    this.axiosInstance.interceptors.request.use(
      (config) => {
        // 添加请求 ID
        const requestId = this.generateRequestId()
        config.headers['X-Request-ID'] = requestId
        config.metadata = { ...config.metadata, requestId }
        
        // 记录请求开始
        this.logger.logRequestStart({
          requestId,
          method: config.method?.toUpperCase() as HttpMethod,
          url: config.url || '',
          data: config.data,
          params: config.params
        })
        
        return config
      },
      (error) => {
        this.logger.logError(error)
        return Promise.reject(error)
      }
    )
    
    // 响应拦截器
    this.axiosInstance.interceptors.response.use(
      (response) => {
        const requestId = response.config.headers?.['X-Request-ID'] as string
        
        // 记录响应
        this.logger.logResponseSuccess({
          requestId,
          status: response.status,
          data: response.data,
          duration: Date.now() - (response.config.metadata?.startTime || Date.now())
        })
        
        return response
      },
      (error) => {
        const requestId = error.config?.headers?.['X-Request-ID'] as string
        
        // 记录错误
        this.logger.logResponseError({
          requestId,
          error,
          duration: Date.now() - (error.config?.metadata?.startTime || Date.now())
        })
        
        return Promise.reject(error)
      }
    )
  }
  
  /**
   * 发起请求（主要方法）
   */
  public async request<T = any>(config: ApiConfig): Promise<ApiResponse<T>> {
    const startTime = Date.now()
    const requestId = this.generateRequestId()
    
    try {
      // 检查去重
      if (config.dedupe !== false) {
        const dedupeKey = this.getDedupeKey(config)
        const pending = this.checkPendingRequest(dedupeKey)
        if (pending) {
          this.logger.logDedupe(requestId, dedupeKey)
          return pending.promise
        }
      }
      
      // 准备 axios 配置
      const axiosConfig: AxiosRequestConfig = {
        url: config.url,
        method: config.method || HttpMethod.GET,
        params: config.params,
        data: config.data,
        headers: {
          ...config.headers,
          'X-Request-ID': requestId
        },
        timeout: config.timeout,
        metadata: {
          requestId,
          startTime,
          category: config.category,
          ...config.metadata
        }
      }
      
      // 创建请求 promise
      const requestPromise = this.executeRequest<T>(axiosConfig, config)
      
      // 如果需要去重，添加到待处理映射
      if (config.dedupe !== false) {
        const dedupeKey = this.getDedupeKey(config)
        this.addPendingRequest(dedupeKey, requestPromise, config)
      }
      
      return await requestPromise
      
    } catch (error) {
      // 处理错误
      const apiError = this.errorHandler.handle(error, requestId)
      
      // 检查是否需要重试
      if (config.retries && config.retries > 0) {
        this.logger.logRetry(requestId, config.retries)
        return this.retryRequest<T>(config, config.retries - 1)
      }
      
      throw apiError
    } finally {
      // 清理去重映射
      if (config.dedupe !== false) {
        const dedupeKey = this.getDedupeKey(config)
        this.removePendingRequest(dedupeKey)
      }
      
      // 更新监控指标
      this.monitor.recordRequest({
        requestId,
        duration: Date.now() - startTime,
        category: config.category || ApiCategory.SYSTEM,
        success: true
      })
    }
  }
  
  /**
   * 执行实际请求
   */
  private async executeRequest<T>(
    axiosConfig: AxiosRequestConfig,
    apiConfig: ApiConfig
  ): Promise<ApiResponse<T>> {
    const response: AxiosResponse<T> = await this.axiosInstance.request<T>(axiosConfig)
    
    return {
      data: response.data,
      status: response.status,
      statusText: response.statusText,
      headers: response.headers as Record<string, string>,
      requestId: axiosConfig.metadata?.requestId,
      timestamp: Date.now(),
      duration: Date.now() - axiosConfig.metadata?.startTime,
      cached: false,
      retryCount: apiConfig.metadata?.retryCount || 0
    }
  }
  
  /**
   * 重试请求
   */
  private async retryRequest<T>(
    config: ApiConfig,
    remainingRetries: number
  ): Promise<ApiResponse<T>> {
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
  
  /**
   * 添加待处理请求
   */
  private addPendingRequest(
    key: string, 
    promise: Promise<any>, 
    config: ApiConfig
  ): void {
    this.pendingRequests.set(key, {
      promise,
      timestamp: Date.now(),
      config
    })
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
  public get<T = any>(url: string, params?: any, config?: Partial<ApiConfig>): Promise<ApiResponse<T>> {
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
  public post<T = any>(url: string, data?: any, config?: Partial<ApiConfig>): Promise<ApiResponse<T>> {
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
  public put<T = any>(url: string, data?: any, config?: Partial<ApiConfig>): Promise<ApiResponse<T>> {
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
  public delete<T = any>(url: string, config?: Partial<ApiConfig>): Promise<ApiResponse<T>> {
    return this.request<T>({
      ...config,
      url,
      method: HttpMethod.DELETE
    })
  }
  
  // ========== 管理方法 ==========
  
  /**
   * 获取日志
   */
  public getLogs(): RequestLog[] {
    return this.logger.getAllLogs()
  }
  
  /**
   * 获取监控指标
   */
  public getMetrics() {
    return this.monitor.getMetrics()
  }
  
  /**
   * 清除缓存
   */
  public clearCache(): void {
    // TODO: 实现缓存清除
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