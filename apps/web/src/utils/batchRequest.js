/**
 * 请求批处理器
 *
 * 特性：
 * - 自动合并相同端点的请求
 * - 可配置的批处理延迟
 * - 请求去重
 * - 错误处理和重试
 */

import logger from '@/utils/logger'

const batchRequestLogger = logger.child('utils:batch-request')

class BatchRequestManager {
  constructor(options = {}) {
    this.queue = new Map() // endpoint -> requests[]
    this.timer = null
    this.processing = false

    // 配置选项
    this.batchDelay = options.batchDelay || 100 // 批处理延迟（毫秒）
    this.maxBatchSize = options.maxBatchSize || 50 // 最大批次大小
    this.timeout = options.timeout || 30000 // 请求超时
    this.retryAttempts = options.retryAttempts || 2 // 重试次数
    this.retryDelay = options.retryDelay || 1000 // 重试延迟

    // 统计信息
    this.stats = {
      totalRequests: 0,
      batchedRequests: 0,
      failedRequests: 0,
      averageBatchSize: 0,
      totalBatches: 0
    }

    // 请求缓存（用于去重）
    this.pendingRequests = new Map()
  }

  /**
   * 添加请求到批处理队列
   * @param {string} endpoint - API端点
   * @param {Object} params - 请求参数
   * @param {Object} options - 请求选项
   * @returns {Promise} 请求结果
   */
  add(endpoint, params = {}, options = {}) {
    return new Promise((resolve, reject) => {
      const {
        method = 'POST',
        headers = {},
        priority = 0,
        dedupe = true,
        cacheKey = null
      } = options

      // 生成请求键（用于去重）
      const requestKey = cacheKey || this.generateRequestKey(endpoint, params, method)

      // 检查是否有相同的pending请求（去重）
      if (dedupe && this.pendingRequests.has(requestKey)) {
        batchRequestLogger.info(`[BatchRequest] Deduping request: ${requestKey}`)
        // 返回已存在的promise
        return this.pendingRequests.get(requestKey)
      }

      // 创建请求对象
      const request = {
        id: this.generateRequestId(),
        endpoint,
        method,
        params,
        headers,
        priority,
        resolve,
        reject,
        timestamp: Date.now(),
        attempts: 0
      }

      // 添加到队列
      const queueKey = `${method}:${endpoint}`
      if (!this.queue.has(queueKey)) {
        this.queue.set(queueKey, [])
      }

      this.queue.get(queueKey).push(request)

      // 按优先级排序
      if (priority !== 0) {
        this.queue.get(queueKey).sort((a, b) => b.priority - a.priority)
      }

      // 保存promise用于去重
      const promise = new Promise((resolve, reject) => {
        request.resolve = resolve
        request.reject = reject
      })

      if (dedupe) {
        this.pendingRequests.set(requestKey, promise)
        // 请求完成后清理
        promise.finally(() => {
          this.pendingRequests.delete(requestKey)
        })
      }

      // 更新统计
      this.stats.totalRequests++

      // 启动批处理定时器
      this.scheduleBatch()

      return promise
    })
  }

  /**
   * 安排批处理
   */
  scheduleBatch() {
    if (this.timer) return

    this.timer = setTimeout(() => {
      this.flush()
    }, this.batchDelay)
  }

  /**
   * 执行批处理
   */
  async flush() {
    if (this.processing || this.queue.size === 0) {
      this.timer = null
      return
    }

    this.processing = true
    this.timer = null

    // 复制队列并清空
    const batch = new Map(this.queue)
    this.queue.clear()

    // 处理每个端点的批次
    const promises = []
    for (const [queueKey, requests] of batch) {
      // 分割成小批次
      const batches = this.splitIntoBatches(requests, this.maxBatchSize)

      for (const batchRequests of batches) {
        promises.push(this.processBatch(queueKey, batchRequests))
      }
    }

    // 等待所有批次完成
    await Promise.allSettled(promises)

    this.processing = false

    // 如果还有新请求，继续处理
    if (this.queue.size > 0) {
      this.scheduleBatch()
    }
  }

  /**
   * 处理单个批次
   */
  async processBatch(queueKey, requests) {
    const [method, endpoint] = queueKey.split(':')

    batchRequestLogger.info(`[BatchRequest] Processing batch: ${endpoint} (${requests.length} requests)`)

    // 更新统计
    this.stats.batchedRequests += requests.length
    this.stats.totalBatches++
    this.stats.averageBatchSize = this.stats.batchedRequests / this.stats.totalBatches

    try {
      // 判断是否可以批处理
      const supportsBatch = this.checkBatchSupport(endpoint)

      if (supportsBatch && requests.length > 1) {
        // 批量请求
        await this.executeBatchRequest(endpoint, method, requests)
      } else {
        // 并行单独请求
        await this.executeParallelRequests(endpoint, method, requests)
      }
    } catch (error) {
      batchRequestLogger.error(`[BatchRequest] Batch processing error:`, error)
      // 批处理失败，尝试单独处理每个请求
      await this.fallbackToIndividualRequests(endpoint, method, requests)
    }
  }

  /**
   * 执行批量请求
   */
  async executeBatchRequest(endpoint, method, requests) {
    const batchParams = requests.map(r => r.params)

    try {
      const response = await this.fetchWithTimeout(endpoint, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'X-Batch-Request': 'true',
          ...requests[0].headers
        },
        body: JSON.stringify({
          batch: batchParams,
          _batch_meta: {
            count: requests.length,
            timestamp: Date.now()
          }
        })
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const result = await response.json()

      // 分发结果
      if (Array.isArray(result.batch)) {
        requests.forEach((request, index) => {
          const data = result.batch[index]
          if (data && data.error) {
            request.reject(new Error(data.error))
            this.stats.failedRequests++
          } else {
            request.resolve(data)
          }
        })
      } else {
        // 如果服务器不支持批处理格式，回退到单独请求
        throw new Error('Server does not support batch format')
      }

    } catch (error) {
      // 批处理失败，回退到单独请求
      batchRequestLogger.error(`[BatchRequest] Batch request failed:`, error)
      await this.fallbackToIndividualRequests(endpoint, method, requests)
    }
  }

  /**
   * 并行执行单独请求
   */
  async executeParallelRequests(endpoint, method, requests) {
    const promises = requests.map(request =>
      this.executeSingleRequest(endpoint, method, request)
    )

    await Promise.allSettled(promises)
  }

  /**
   * 执行单个请求
   */
  async executeSingleRequest(endpoint, method, request, attempt = 1) {
    try {
      const options = {
        method,
        headers: {
          'Content-Type': 'application/json',
          ...request.headers
        }
      }

      if (method !== 'GET' && method !== 'HEAD') {
        options.body = JSON.stringify(request.params)
      } else {
        // GET请求将参数添加到URL
        const url = new URL(endpoint, window.location.origin)
        Object.entries(request.params).forEach(([key, value]) => {
          url.searchParams.append(key, value)
        })
        endpoint = url.toString()
      }

      const response = await this.fetchWithTimeout(endpoint, options)

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const data = await response.json()
      request.resolve(data)

    } catch (error) {
      request.attempts = attempt

      // 重试逻辑
      if (attempt < this.retryAttempts) {
        batchRequestLogger.info(`[BatchRequest] Retrying request (attempt ${attempt + 1}/${this.retryAttempts})`)
        await this.delay(this.retryDelay * attempt) // 指数退避
        return this.executeSingleRequest(endpoint, method, request, attempt + 1)
      }

      // 最终失败
      batchRequestLogger.error(`[BatchRequest] Request failed after ${attempt} attempts:`, error)
      request.reject(error)
      this.stats.failedRequests++
    }
  }

  /**
   * 回退到单独请求
   */
  async fallbackToIndividualRequests(endpoint, method, requests) {
    batchRequestLogger.info(`[BatchRequest] Falling back to individual requests for ${endpoint}`)

    for (const request of requests) {
      await this.executeSingleRequest(endpoint, method, request)
    }
  }

  /**
   * 带超时的fetch
   */
  async fetchWithTimeout(url, options = {}) {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), this.timeout)

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal
      })
      clearTimeout(timeout)
      return response
    } catch (error) {
      clearTimeout(timeout)
      if (error.name === 'AbortError') {
        throw new Error('Request timeout')
      }
      throw error
    }
  }

  /**
   * 检查端点是否支持批处理
   */
  checkBatchSupport(endpoint) {
    // 可以根据端点配置或动态检测
    const batchSupportedEndpoints = [
      '/api/data/batch',
      '/api/chart/batch',
      '/api/market/batch',
      '/api/quotes/batch'
    ]

    return batchSupportedEndpoints.some(pattern =>
      endpoint.includes(pattern.replace('/batch', ''))
    )
  }

  /**
   * 分割成小批次
   */
  splitIntoBatches(items, batchSize) {
    const batches = []
    for (let i = 0; i < items.length; i += batchSize) {
      batches.push(items.slice(i, i + batchSize))
    }
    return batches
  }

  /**
   * 生成请求键
   */
  generateRequestKey(endpoint, params, method) {
    return `${method}:${endpoint}:${JSON.stringify(params)}`
  }

  /**
   * 生成请求ID
   */
  generateRequestId() {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  }

  /**
   * 延迟函数
   */
  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms))
  }

  /**
   * 立即执行所有待处理请求
   */
  async flushNow() {
    if (this.timer) {
      clearTimeout(this.timer)
      this.timer = null
    }
    await this.flush()
  }

  /**
   * 清空队列
   */
  clear() {
    if (this.timer) {
      clearTimeout(this.timer)
      this.timer = null
    }

    // 拒绝所有待处理请求
    for (const requests of this.queue.values()) {
      for (const request of requests) {
        request.reject(new Error('Queue cleared'))
      }
    }

    this.queue.clear()
    this.pendingRequests.clear()
  }

  /**
   * 获取统计信息
   */
  getStats() {
    return {
      ...this.stats,
      queueSize: this.queue.size,
      pendingRequests: this.pendingRequests.size,
      processing: this.processing
    }
  }

  /**
   * 重置统计信息
   */
  resetStats() {
    this.stats = {
      totalRequests: 0,
      batchedRequests: 0,
      failedRequests: 0,
      averageBatchSize: 0,
      totalBatches: 0
    }
  }
}

// 创建默认实例
const batchRequestManager = new BatchRequestManager({
  batchDelay: 100,
  maxBatchSize: 20,
  timeout: 30000,
  retryAttempts: 2
})

// 导出
export default batchRequestManager
export { BatchRequestManager }
