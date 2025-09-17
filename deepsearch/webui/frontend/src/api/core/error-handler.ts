/**
 * 统一错误处理器
 * 处理和标准化所有 API 错误
 */

import { ApiError, ApiErrorCode } from './types'

/**
 * 错误处理器类
 */
export class ErrorHandler {
  private errorHandlers: Map<ApiErrorCode, (error: ApiError) => void> = new Map()
  
  constructor() {
    this.setupDefaultHandlers()
  }
  
  /**
   * 设置默认错误处理器
   */
  private setupDefaultHandlers(): void {
    // 未授权错误
    this.errorHandlers.set(ApiErrorCode.UNAUTHORIZED, (error) => {
      console.error('未授权访问，请登录')
      // TODO: 跳转到登录页
    })
    
    // 权限不足
    this.errorHandlers.set(ApiErrorCode.FORBIDDEN, (error) => {
      console.error('权限不足')
      // TODO: 显示权限提示
    })
    
    // 请求限流
    this.errorHandlers.set(ApiErrorCode.RATE_LIMITED, (error) => {
      console.warn('请求过于频繁，请稍后再试')
    })
    
    // 服务不可用
    this.errorHandlers.set(ApiErrorCode.SERVICE_UNAVAILABLE, (error) => {
      console.error('服务暂时不可用，请稍后再试')
    })
    
    // 网关超时
    this.errorHandlers.set(ApiErrorCode.GATEWAY_TIMEOUT, (error) => {
      console.error('请求超时，请检查网络连接')
    })
  }
  
  /**
   * 处理错误
   */
  public handle(error: any, requestId: string): ApiError {
    const apiError = this.normalizeError(error, requestId)
    
    // 调用特定的错误处理器
    const handler = this.errorHandlers.get(apiError.code)
    if (handler) {
      handler(apiError)
    } else {
      // 默认处理
      this.defaultHandler(apiError)
    }
    
    return apiError
  }
  
  /**
   * 标准化错误对象
   */
  private normalizeError(error: any, requestId: string): ApiError {
    // 如果已经是 ApiError，直接返回
    if (this.isApiError(error)) {
      return error
    }
    
    // Axios 错误
    if (error.response) {
      return this.createApiError({
        code: this.mapStatusToErrorCode(error.response.status),
        message: error.response.data?.message || error.message,
        status: error.response.status,
        statusText: error.response.statusText,
        response: error.response.data,
        requestId,
        timestamp: Date.now(),
        retry: this.shouldRetry(error.response.status)
      })
    }
    
    // 网络错误
    if (error.request) {
      return this.createApiError({
        code: ApiErrorCode.SERVICE_UNAVAILABLE,
        message: '网络连接失败',
        requestId,
        timestamp: Date.now(),
        retry: true
      })
    }
    
    // 其他错误
    return this.createApiError({
      code: ApiErrorCode.INTERNAL_ERROR,
      message: error.message || '未知错误',
      requestId,
      timestamp: Date.now(),
      retry: false
    })
  }
  
  /**
   * 创建 ApiError 对象
   */
  private createApiError(params: Partial<ApiError> & { message: string }): ApiError {
    const error = new Error(params.message) as ApiError
    error.name = 'ApiError'
    error.code = params.code || ApiErrorCode.INTERNAL_ERROR
    error.status = params.status
    error.statusText = params.statusText
    error.response = params.response
    error.requestId = params.requestId
    error.timestamp = params.timestamp || Date.now()
    error.retry = params.retry
    return error
  }
  
  /**
   * 判断是否为 ApiError
   */
  private isApiError(error: any): error is ApiError {
    return error instanceof Error && 'code' in error && 'requestId' in error
  }
  
  /**
   * 映射 HTTP 状态码到错误码
   */
  private mapStatusToErrorCode(status: number): ApiErrorCode {
    const statusMap: Record<number, ApiErrorCode> = {
      400: ApiErrorCode.INVALID_REQUEST,
      401: ApiErrorCode.UNAUTHORIZED,
      403: ApiErrorCode.FORBIDDEN,
      404: ApiErrorCode.NOT_FOUND,
      429: ApiErrorCode.RATE_LIMITED,
      500: ApiErrorCode.INTERNAL_ERROR,
      502: ApiErrorCode.GATEWAY_TIMEOUT,
      503: ApiErrorCode.SERVICE_UNAVAILABLE,
      504: ApiErrorCode.GATEWAY_TIMEOUT
    }
    
    return statusMap[status] || ApiErrorCode.INTERNAL_ERROR
  }
  
  /**
   * 判断是否应该重试
   */
  private shouldRetry(status: number): boolean {
    // 5xx 错误和 429 可以重试
    return status >= 500 || status === 429
  }
  
  /**
   * 默认错误处理器
   */
  private defaultHandler(error: ApiError): void {
    console.error('[API Error]', {
      code: error.code,
      message: error.message,
      status: error.status,
      requestId: error.requestId
    })
  }
  
  /**
   * 注册错误处理器
   */
  public registerHandler(code: ApiErrorCode, handler: (error: ApiError) => void): void {
    this.errorHandlers.set(code, handler)
  }
  
  /**
   * 获取用户友好的错误消息
   */
  public getUserMessage(error: ApiError): string {
    const messages: Record<ApiErrorCode, string> = {
      [ApiErrorCode.INVALID_REQUEST]: '请求参数错误',
      [ApiErrorCode.UNAUTHORIZED]: '请先登录',
      [ApiErrorCode.FORBIDDEN]: '权限不足',
      [ApiErrorCode.NOT_FOUND]: '资源不存在',
      [ApiErrorCode.RATE_LIMITED]: '请求过于频繁',
      [ApiErrorCode.INTERNAL_ERROR]: '服务器错误',
      [ApiErrorCode.SERVICE_UNAVAILABLE]: '服务暂时不可用',
      [ApiErrorCode.GATEWAY_TIMEOUT]: '请求超时',
      [ApiErrorCode.DATA_SOURCE_ERROR]: '数据源错误'
    }
    
    return messages[error.code] || error.message || '未知错误'
  }
  
  /**
   * 格式化错误详情
   */
  public formatErrorDetails(error: ApiError): string {
    const details = [
      `错误码: ${error.code}`,
      `消息: ${error.message}`,
      `请求ID: ${error.requestId || 'N/A'}`,
      `时间: ${new Date(error.timestamp || Date.now()).toLocaleString()}`
    ]
    
    if (error.status) {
      details.push(`HTTP状态: ${error.status}`)
    }
    
    return details.join('\n')
  }
}