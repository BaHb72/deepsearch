/**
 * API 日志系统
 * 记录和管理所有 API 请求的日志
 */

import {ApiCategory, ApiError, HttpMethod, LogFilter, RequestLog} from './types'

// 循环缓冲区，用于限制日志大小
class CircularBuffer<T> {
  private buffer: T[] = []
  private pointer: number = 0
  private size: number = 0

  constructor(private capacity: number) {}

  push(item: T): void {
    if (this.size < this.capacity) {
      this.buffer.push(item)
      this.size++
    } else {
      this.buffer[this.pointer] = item
      this.pointer = (this.pointer + 1) % this.capacity
    }
  }

  getAll(): T[] {
    if (this.size < this.capacity) {
      return [...this.buffer]
    }
    // 返回正确顺序的元素
    return [
      ...this.buffer.slice(this.pointer),
      ...this.buffer.slice(0, this.pointer)
    ]
  }

  clear(): void {
    this.buffer = []
    this.pointer = 0
    this.size = 0
  }

  getSize(): number {
    return this.size
  }
}

/**
 * API 日志管理器
 */
export class ApiLogger {
  private static instance: ApiLogger
  private logs: CircularBuffer<RequestLog>
  private readonly maxLogs: number = 1000
  private logLevel: 'debug' | 'info' | 'warn' | 'error' = 'info'
  private subscribers: Set<(log: RequestLog) => void> = new Set()

  private constructor() {
    this.logs = new CircularBuffer<RequestLog>(this.maxLogs)

    // 在开发环境启用 debug 级别
    if (import.meta.env.DEV) {
      this.logLevel = 'debug'
    }
  }

  /**
   * 获取单例实例
   */
  public static getInstance(): ApiLogger {
    if (!ApiLogger.instance) {
      ApiLogger.instance = new ApiLogger()
    }
    return ApiLogger.instance
  }

  /**
   * 记录请求开始
   */
  public logRequestStart(params: {
    requestId: string
    method: HttpMethod
    url: string
    data?: any
    params?: any
      category?: ApiCategory
  }): void {
    const log: Partial<RequestLog> = {
      id: params.requestId,
      timestamp: Date.now(),
      method: params.method,
      url: params.url,
      fullUrl: this.getFullUrl(params.url),
      params: params.params,
      data: params.data,
        category: params.category ?? ApiCategory.SYSTEM,
      trace: [
        `Request started at ${new Date().toISOString()}`,
        `Method: ${params.method}`,
        `URL: ${params.url}`
      ]
    }

    this.addLog(log as RequestLog)

    if (this.logLevel === 'debug') {
        console.group(`[API Request ${params.requestId}]`)
      console.log('Method:', params.method)
      console.log('URL:', params.url)
      if (params.params) console.log('Params:', params.params)
      if (params.data) console.log('Data:', params.data)
      console.groupEnd()
    }
  }

  /**
   * 记录响应成功
   */
  public logResponseSuccess(params: {
    requestId: string
    status: number
    data: any
    duration: number
  }): void {
    const log = this.findLog(params.requestId)
    if (log) {
      log.status = params.status
      log.statusText = this.getStatusText(params.status)
      log.responseData = params.data
      log.duration = params.duration
      log.trace.push(
        `Response received at ${new Date().toISOString()}`,
        `Status: ${params.status}`,
        `Duration: ${params.duration}ms`
      )

      this.updateLog(log)
    }

    if (this.logLevel === 'debug') {
        console.group(`[API Response ${params.requestId}]`)
      console.log('Status:', params.status)
      console.log('Duration:', params.duration + 'ms')
      console.log('Data:', params.data)
      console.groupEnd()
    }
  }

  /**
   * 记录响应错误
   */
  public logResponseError(params: {
    requestId: string
    error: any
    duration: number
  }): void {
    const log = this.findLog(params.requestId)
    if (log) {
      log.status = params.error.response?.status || 0
      log.statusText = params.error.message
      log.error = this.normalizeError(params.error)
      log.errorMessage = params.error.message
      log.errorStack = params.error.stack
      log.duration = params.duration
      log.trace.push(
        `Error occurred at ${new Date().toISOString()}`,
        `Error: ${params.error.message}`,
        `Duration: ${params.duration}ms`
      )

      this.updateLog(log)
    }

    if (this.logLevel !== 'error') {
      console.group(`❌ API Error [${params.requestId}]`)
      console.error('Error:', params.error)
      console.log('Duration:', params.duration + 'ms')
      console.groupEnd()
    }
  }

  /**
   * 记录去重
   */
  public logDedupe(requestId: string, dedupeKey: string): void {
    if (this.logLevel === 'debug') {
        console.log(`Deduplicated request [${requestId}] with key: ${dedupeKey}`)
    }
  }

  /**
   * 记录重试
   */
  public logRetry(requestId: string, remainingRetries: number): void {
    const log = this.findLog(requestId)
    if (log) {
      log.trace.push(
        `Retry attempt at ${new Date().toISOString()}`,
        `Remaining retries: ${remainingRetries}`
      )
      this.updateLog(log)
    }

    if (this.logLevel === 'info' || this.logLevel === 'debug') {
        console.log(`Retrying request [${requestId}], ${remainingRetries} attempts left`)
    }
  }

  /**
   * 记录通用错误
   */
  public logError(error: any): void {
    console.error('[API Error]', error)
  }

  /**
   * 添加日志
   */
  private addLog(log: RequestLog): void {
    this.logs.push(log)
    this.notifySubscribers(log)
  }

  /**
   * 更新日志
   */
  private updateLog(log: RequestLog): void {
    this.notifySubscribers(log)
  }

  /**
   * 查找日志
   */
  private findLog(requestId: string): RequestLog | undefined {
    return this.logs.getAll().find(log => log.id === requestId)
  }

  /**
   * 获取完整 URL
   */
  private getFullUrl(url: string): string {
    try {
      // 如果是绝对 URL，直接返回
      if (url.startsWith('http://') || url.startsWith('https://')) {
        return url
      }

      // 否则，构建完整 URL
      const baseUrl = import.meta.env.DEV
        ? 'http://localhost:8000/api'
        : `${window.location.protocol}//${window.location.hostname}:8000/api`

      return new URL(url, baseUrl).href
    } catch {
      return url
    }
  }

  /**
   * 获取状态文本
   */
  private getStatusText(status: number): string {
    const statusTexts: Record<number, string> = {
      200: 'OK',
      201: 'Created',
      204: 'No Content',
      400: 'Bad Request',
      401: 'Unauthorized',
      403: 'Forbidden',
      404: 'Not Found',
      429: 'Too Many Requests',
      500: 'Internal Server Error',
      502: 'Bad Gateway',
      503: 'Service Unavailable',
      504: 'Gateway Timeout'
    }
    return statusTexts[status] || 'Unknown'
  }

  /**
   * 标准化错误对象
   */
  private normalizeError(error: any): ApiError | undefined {
    if (!error) return undefined

    return {
      name: error.name || 'Error',
      message: error.message || 'Unknown error',
      code: error.code || 5000,
      status: error.response?.status,
      statusText: error.response?.statusText,
      requestId: error.config?.metadata?.requestId,
      timestamp: Date.now(),
      stack: error.stack
    } as ApiError
  }

  /**
   * 通知订阅者
   */
  private notifySubscribers(log: RequestLog): void {
    this.subscribers.forEach(callback => {
      try {
        callback(log)
      } catch (error) {
        console.error('Subscriber callback error:', error)
      }
    })
  }

  // ========== 公共方法 ==========

  /**
   * 获取所有日志
   */
  public getAllLogs(): RequestLog[] {
    return this.logs.getAll()
  }

  /**
   * 查询日志
   */
  public queryLogs(filter: LogFilter): RequestLog[] {
    let logs = this.getAllLogs()

    // 时间过滤
    if (filter.startTime) {
      logs = logs.filter(log => log.timestamp >= filter.startTime!)
    }
    if (filter.endTime) {
      logs = logs.filter(log => log.timestamp <= filter.endTime!)
    }

    // 分类过滤
    if (filter.category) {
      logs = logs.filter(log => log.category === filter.category)
    }

    // 状态过滤
    if (filter.status && filter.status.length > 0) {
      logs = logs.filter(log => log.status && filter.status!.includes(log.status))
    }

    // 方法过滤
    if (filter.method && filter.method.length > 0) {
      logs = logs.filter(log => filter.method!.includes(log.method))
    }

    // URL 过滤
    if (filter.url) {
        logs = logs.filter(log => log.url.includes(filter.url!))
    }

    // 错误过滤
    if (filter.hasError !== undefined) {
      logs = logs.filter(log => (log.error !== undefined) === filter.hasError)
    }

    // 性能过滤
    if (filter.minDuration) {
      logs = logs.filter(log => log.duration && log.duration >= filter.minDuration!)
    }
    if (filter.maxDuration) {
      logs = logs.filter(log => log.duration && log.duration <= filter.maxDuration!)
    }

    // 限制数量
    if (filter.limit) {
      logs = logs.slice(0, filter.limit)
    }

    return logs
  }

  /**
   * 导出日志
   */
  public exportLogs(format: 'json' | 'csv' = 'json'): string {
    const logs = this.getAllLogs()

    if (format === 'json') {
      return JSON.stringify(logs, null, 2)
    }

    // CSV 格式
    const headers = [
      'ID', 'Timestamp', 'Method', 'URL', 'Status',
      'Duration', 'Error', 'Category'
    ]

    const rows = logs.map(log => [
      log.id,
      new Date(log.timestamp).toISOString(),
      log.method,
      log.url,
      log.status || '',
      log.duration || '',
      log.errorMessage || '',
      log.category || ''
    ])

    const csv = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n')

    return csv
  }

  /**
   * 清除日志
   */
  public clearLogs(): void {
    this.logs.clear()
  }

  /**
   * 订阅日志更新
   */
  public subscribe(callback: (log: RequestLog) => void): () => void {
    this.subscribers.add(callback)
    return () => this.subscribers.delete(callback)
  }

  /**
   * 设置日志级别
   */
  public setLogLevel(level: 'debug' | 'info' | 'warn' | 'error'): void {
    this.logLevel = level
  }

  /**
   * 获取统计信息
   */
  public getStatistics() {
    const logs = this.getAllLogs()
    const now = Date.now()
    const recentLogs = logs.filter(log => now - log.timestamp < 60000) // 最近1分钟

    return {
      total: logs.length,
      recent: recentLogs.length,
      errors: logs.filter(log => log.error).length,
      avgDuration: this.calculateAverage(logs.map(log => log.duration || 0)),
      categories: this.groupByCategory(logs),
      statusCodes: this.groupByStatus(logs)
    }
  }

  private calculateAverage(numbers: number[]): number {
    if (numbers.length === 0) return 0
    return numbers.reduce((a, b) => a + b, 0) / numbers.length
  }

  private groupByCategory(logs: RequestLog[]) {
    const groups: Record<string, number> = {}
    logs.forEach(log => {
      const category = log.category || 'unknown'
      groups[category] = (groups[category] || 0) + 1
    })
    return groups
  }

  private groupByStatus(logs: RequestLog[]) {
    const groups: Record<string, number> = {}
    logs.forEach(log => {
      if (log.status) {
        const statusGroup = `${Math.floor(log.status / 100)}xx`
        groups[statusGroup] = (groups[statusGroup] || 0) + 1
      }
    })
    return groups
  }
}
