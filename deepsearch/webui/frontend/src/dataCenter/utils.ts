/**
 * 数据中心工具函数
 */

/**
 * 请求管理器 - 防止重复请求
 */
export class RequestManager {
  private pending = new Map<string, Promise<any>>()

  /**
   * 执行请求，自动去重
   */
  async execute<T>(
    key: string,
    fn: () => Promise<T>,
    options?: {
      dedupe?: boolean // 是否去重，默认true
      timeout?: number // 超时时间
    }
  ): Promise<T> {
    const { dedupe = true, timeout } = options || {}

    // 如果不需要去重，直接执行
    if (!dedupe) {
      return this.executeWithTimeout(fn, timeout)
    }

    // 如果有相同请求正在进行，返回同一个 Promise
    if (this.pending.has(key)) {
      console.log(`[RequestManager] 请求去重: ${key}`)
      return this.pending.get(key) as Promise<T>
    }

    // 创建新请求
    const promise = this.executeWithTimeout(fn, timeout)
      .finally(() => {
        this.pending.delete(key)
      })

    this.pending.set(key, promise)
    return promise
  }

  /**
   * 带超时的执行
   */
  private async executeWithTimeout<T>(
    fn: () => Promise<T>,
    timeout?: number
  ): Promise<T> {
    if (!timeout) {
      return fn()
    }

    return Promise.race([
      fn(),
      new Promise<T>((_, reject) =>
        setTimeout(() => reject(new Error('请求超时')), timeout)
      )
    ])
  }

  /**
   * 取消所有进行中的请求
   */
  cancelAll(): void {
    this.pending.clear()
  }

  /**
   * 获取进行中的请求数
   */
  getPendingCount(): number {
    return this.pending.size
  }

  /**
   * 检查是否有进行中的请求
   */
  hasPending(key?: string): boolean {
    if (key) {
      return this.pending.has(key)
    }
    return this.pending.size > 0
  }
}

/**
 * 重试机制
 */
export async function retry<T>(
  fn: () => Promise<T>,
  options: {
    maxAttempts?: number
    delay?: number
    backoff?: boolean
    onRetry?: (attempt: number, error: Error) => void
  } = {}
): Promise<T> {
  const {
    maxAttempts = 3,
    delay = 1000,
    backoff = true,
    onRetry
  } = options

  let lastError: Error

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn()
    } catch (error) {
      lastError = error as Error

      if (attempt === maxAttempts) {
        throw lastError
      }

      onRetry?.(attempt, lastError)

      // 计算延迟时间
      const waitTime = backoff ? delay * Math.pow(2, attempt - 1) : delay
      await sleep(waitTime)
    }
  }

  throw lastError!
}

/**
 * 延迟函数
 */
export function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

/**
 * 防抖函数
 */
export function debounce<T extends (...args: any[]) => any>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timeoutId: NodeJS.Timeout

  return function (...args: Parameters<T>) {
    clearTimeout(timeoutId)
    timeoutId = setTimeout(() => fn(...args), delay)
  }
}

/**
 * 节流函数
 */
export function throttle<T extends (...args: any[]) => any>(
  fn: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle = false

  return function (...args: Parameters<T>) {
    if (!inThrottle) {
      fn(...args)
      inThrottle = true
      setTimeout(() => {
        inThrottle = false
      }, limit)
    }
  }
}

/**
 * 批量执行，带并发控制
 */
export async function batchExecute<T, R>(
  items: T[],
  fn: (item: T) => Promise<R>,
  options: {
    concurrency?: number
    onProgress?: (completed: number, total: number) => void
  } = {}
): Promise<R[]> {
  const { concurrency = 5, onProgress } = options
  const results: R[] = []
  const executing: Promise<void>[] = []
  let completed = 0

  for (let i = 0; i < items.length; i++) {
    const promise = fn(items[i]).then(result => {
      results[i] = result
      completed++
      onProgress?.(completed, items.length)
    })

    executing.push(promise)

    if (executing.length >= concurrency) {
      await Promise.race(executing)
      executing.splice(
        executing.findIndex(p => p === promise),
        1
      )
    }
  }

  await Promise.all(executing)
  return results
}

/**
 * 创建单例请求管理器
 */
export const requestManager = new RequestManager()

/**
 * 生成缓存键
 */
export function generateCacheKey(
  prefix: string,
  params?: Record<string, any>
): string {
  if (!params || Object.keys(params).length === 0) {
    return prefix
  }

  const sortedParams = Object.keys(params)
    .sort()
    .map(key => `${key}=${JSON.stringify(params[key])}`)
    .join('&')

  return `${prefix}:${sortedParams}`
}