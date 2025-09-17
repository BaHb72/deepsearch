/**
 * 缓存服务 - 提供统一的缓存管理
 */

interface CacheEntry<T = any> {
  data: T
  timestamp: number
  ttl: number
}

interface CacheStats {
  size: number
  hits: number
  misses: number
  hitRate: number
}

class CacheService {
  private cache = new Map<string, CacheEntry>()
  private stats = {
    hits: 0,
    misses: 0
  }

  /**
   * 设置缓存
   */
  set<T>(key: string, data: T, ttl: number = 30000): void {
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      ttl
    })
  }

  /**
   * 获取缓存
   */
  get<T>(key: string): T | null {
    const entry = this.cache.get(key)
    if (!entry) {
      this.stats.misses++
      return null
    }

    // 检查是否过期
    if (Date.now() - entry.timestamp > entry.ttl) {
      this.cache.delete(key)
      this.stats.misses++
      return null
    }

    this.stats.hits++
    return entry.data as T
  }

  /**
   * 获取缓存（带统计）
   */
  getWithStats<T>(key: string): T | null {
    return this.get<T>(key)
  }

  /**
   * 检查缓存是否存在且有效
   */
  has(key: string): boolean {
    const entry = this.cache.get(key)
    if (!entry) return false

    // 检查是否过期
    if (Date.now() - entry.timestamp > entry.ttl) {
      this.cache.delete(key)
      return false
    }

    return true
  }

  /**
   * 删除缓存
   */
  delete(key: string): boolean {
    return this.cache.delete(key)
  }

  /**
   * 清空缓存
   */
  clear(): void {
    this.cache.clear()
  }

  /**
   * 失效匹配的缓存
   */
  invalidate(pattern?: string): void {
    if (!pattern) {
      this.clear()
      return
    }

    const keysToDelete: string[] = []
    for (const key of this.cache.keys()) {
      if (key.includes(pattern)) {
        keysToDelete.push(key)
      }
    }

    keysToDelete.forEach(key => this.cache.delete(key))
  }

  /**
   * 获取缓存大小
   */
  size(): number {
    return this.cache.size
  }

  /**
   * 获取统计信息
   */
  getStats(): CacheStats {
    const total = this.stats.hits + this.stats.misses
    return {
      size: this.cache.size,
      hits: this.stats.hits,
      misses: this.stats.misses,
      hitRate: total > 0 ? this.stats.hits / total : 0
    }
  }

  /**
   * 重置统计
   */
  resetStats(): void {
    this.stats.hits = 0
    this.stats.misses = 0
  }

  /**
   * 清理过期缓存
   */
  cleanup(): void {
    const now = Date.now()
    const keysToDelete: string[] = []

    this.cache.forEach((entry, key) => {
      if (now - entry.timestamp > entry.ttl) {
        keysToDelete.push(key)
      }
    })

    keysToDelete.forEach(key => this.cache.delete(key))
  }

  /**
   * 获取所有缓存键
   */
  keys(): string[] {
    return Array.from(this.cache.keys())
  }

  /**
   * 获取缓存条目信息
   */
  getEntryInfo(key: string): { data: any; age: number; ttl: number } | null {
    const entry = this.cache.get(key)
    if (!entry) return null

    const age = Date.now() - entry.timestamp
    if (age > entry.ttl) {
      this.cache.delete(key)
      return null
    }

    return {
      data: entry.data,
      age,
      ttl: entry.ttl
    }
  }
}

// 导出单例
export const cacheService = new CacheService()

// 定期清理过期缓存（每分钟）
if (typeof window !== 'undefined') {
  setInterval(() => {
    cacheService.cleanup()
  }, 60000)
}

// 开发环境下暴露到 window
if (process.env.NODE_ENV === 'development' && typeof window !== 'undefined') {
  (window as any).__CACHE__ = cacheService
}