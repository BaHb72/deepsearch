/**
 * 多层缓存管理器
 * 
 * 特性：
 * - 内存缓存（最快）
 * - SessionStorage缓存（中等）
 * - IndexedDB缓存（大数据）
 * - LRU淘汰策略
 * - TTL过期控制
 * - 数据压缩
 */

import logger from '@/utils/logger'

const cacheLogger = logger.child('utils:cache')

class CacheManager {
  constructor(options = {}) {
    // 配置选项
    this.maxMemoryItems = options.maxMemoryItems || 100
    this.maxMemorySize = options.maxMemorySize || 10 * 1024 * 1024 // 10MB
    this.defaultTTL = options.defaultTTL || 5 * 60 * 1000 // 5分钟
    this.dbName = options.dbName || 'DeepSearchCache'
    this.dbVersion = options.dbVersion || 1
    this.enableCompression = options.enableCompression || true
    
    // 内存缓存
    this.memoryCache = new Map()
    this.memoryCacheSize = 0
    this.accessOrder = [] // LRU访问顺序
    
    // SessionStorage前缀
    this.sessionPrefix = 'ds_cache_'
    
    // IndexedDB
    this.db = null
    this.dbReady = this.initIndexedDB()
    
    // 统计信息
    this.stats = {
      hits: 0,
      misses: 0,
      memoryHits: 0,
      sessionHits: 0,
      indexedHits: 0,
      writes: 0,
      evictions: 0
    }
    
    // 定期清理过期数据
    this.startCleanupTimer()
  }
  
  /**
   * 初始化IndexedDB
   */
  async initIndexedDB() {
    return new Promise((resolve, reject) => {
      if (!window.indexedDB) {
        cacheLogger.warn('[CacheManager] IndexedDB not supported')
        resolve(null)
        return
      }
      
      const request = indexedDB.open(this.dbName, this.dbVersion)
      
      request.onerror = () => {
        cacheLogger.error('[CacheManager] IndexedDB error:', request.error)
        reject(request.error)
      }
      
      request.onsuccess = () => {
        this.db = request.result
        cacheLogger.info('[CacheManager] IndexedDB initialized')
        resolve(this.db)
      }
      
      request.onupgradeneeded = (event) => {
        const db = event.target.result
        
        // 创建对象存储
        if (!db.objectStoreNames.contains('cache')) {
          const store = db.createObjectStore('cache', { keyPath: 'key' })
          store.createIndex('expiry', 'expiry', { unique: false })
          store.createIndex('size', 'size', { unique: false })
        }
      }
    })
  }
  
  /**
   * 获取缓存数据
   */
  async get(key, options = {}) {
    const {
      ttl = this.defaultTTL,
      strategy = 'all', // all | memory | session | indexed
      validator = null,
      fallback = null
    } = options
    
    // 1. 检查内存缓存
    if (strategy === 'all' || strategy === 'memory') {
      const memoryData = this.getFromMemory(key)
      if (memoryData !== null) {
        if (this.isValid(memoryData, ttl, validator)) {
          this.stats.hits++
          this.stats.memoryHits++
          return memoryData.value
        } else {
          // 过期或无效，删除
          this.removeFromMemory(key)
        }
      }
    }
    
    // 2. 检查SessionStorage
    if (strategy === 'all' || strategy === 'session') {
      const sessionData = this.getFromSession(key)
      if (sessionData !== null) {
        if (this.isValid(sessionData, ttl, validator)) {
          this.stats.hits++
          this.stats.sessionHits++
          // 提升到内存缓存
          if (strategy === 'all') {
            this.setToMemory(key, sessionData.value, sessionData)
          }
          return sessionData.value
        } else {
          // 过期或无效，删除
          this.removeFromSession(key)
        }
      }
    }
    
    // 3. 检查IndexedDB
    if ((strategy === 'all' || strategy === 'indexed') && this.db) {
      const indexedData = await this.getFromIndexed(key)
      if (indexedData !== null) {
        if (this.isValid(indexedData, ttl, validator)) {
          this.stats.hits++
          this.stats.indexedHits++
          // 提升到更高层缓存
          if (strategy === 'all') {
            this.setToMemory(key, indexedData.value, indexedData)
            this.setToSession(key, indexedData.value, indexedData)
          }
          return indexedData.value
        } else {
          // 过期或无效，删除
          await this.removeFromIndexed(key)
        }
      }
    }
    
    // 缓存未命中
    this.stats.misses++
    
    // 如果提供了fallback函数，执行并缓存结果
    if (fallback) {
      try {
        const value = await fallback()
        await this.set(key, value, options)
        return value
      } catch (error) {
        cacheLogger.error('[CacheManager] Fallback error:', error)
        return null
      }
    }
    
    return null
  }
  
  /**
   * 设置缓存数据
   */
  async set(key, value, options = {}) {
    const {
      ttl = this.defaultTTL,
      strategy = 'all', // all | memory | session | indexed
      compress = this.enableCompression,
      metadata = {}
    } = options
    
    const now = Date.now()
    const expiry = now + ttl
    
    // 准备缓存数据
    const cacheData = {
      key,
      value,
      timestamp: now,
      expiry,
      metadata,
      compressed: false
    }
    
    // 压缩大数据
    if (compress && this.shouldCompress(value)) {
      cacheData.value = this.compress(value)
      cacheData.compressed = true
    }
    
    // 计算大小
    cacheData.size = this.calculateSize(cacheData)
    
    this.stats.writes++
    
    // 1. 存储到内存
    if (strategy === 'all' || strategy === 'memory') {
      this.setToMemory(key, value, cacheData)
    }
    
    // 2. 存储到SessionStorage
    if (strategy === 'all' || strategy === 'session') {
      this.setToSession(key, value, cacheData)
    }
    
    // 3. 存储到IndexedDB
    if ((strategy === 'all' || strategy === 'indexed') && this.db) {
      await this.setToIndexed(key, value, cacheData)
    }
    
    return true
  }
  
  /**
   * 删除缓存
   */
  async remove(key) {
    this.removeFromMemory(key)
    this.removeFromSession(key)
    if (this.db) {
      await this.removeFromIndexed(key)
    }
  }
  
  /**
   * 清空所有缓存
   */
  async clear() {
    // 清空内存缓存
    this.memoryCache.clear()
    this.memoryCacheSize = 0
    this.accessOrder = []
    
    // 清空SessionStorage
    const keys = Object.keys(sessionStorage)
    keys.forEach(key => {
      if (key.startsWith(this.sessionPrefix)) {
        sessionStorage.removeItem(key)
      }
    })
    
    // 清空IndexedDB
    if (this.db) {
      await this.clearIndexed()
    }
    
    cacheLogger.info('[CacheManager] All caches cleared')
  }
  
  // === 内存缓存操作 ===
  
  getFromMemory(key) {
    const data = this.memoryCache.get(key)
    if (data) {
      // 更新LRU访问顺序
      this.updateAccessOrder(key)
      return data
    }
    return null
  }
  
  setToMemory(key, value, cacheData) {
    // 检查内存限制
    if (this.memoryCache.size >= this.maxMemoryItems) {
      this.evictLRU()
    }
    
    // 检查大小限制
    if (this.memoryCacheSize + cacheData.size > this.maxMemorySize) {
      this.evictBySize(cacheData.size)
    }
    
    // 存储数据
    this.memoryCache.set(key, cacheData)
    this.memoryCacheSize += cacheData.size
    this.updateAccessOrder(key)
  }
  
  removeFromMemory(key) {
    const data = this.memoryCache.get(key)
    if (data) {
      this.memoryCacheSize -= data.size
      this.memoryCache.delete(key)
      const index = this.accessOrder.indexOf(key)
      if (index > -1) {
        this.accessOrder.splice(index, 1)
      }
    }
  }
  
  updateAccessOrder(key) {
    const index = this.accessOrder.indexOf(key)
    if (index > -1) {
      this.accessOrder.splice(index, 1)
    }
    this.accessOrder.push(key)
  }
  
  evictLRU() {
    if (this.accessOrder.length > 0) {
      const key = this.accessOrder[0]
      this.removeFromMemory(key)
      this.stats.evictions++
      cacheLogger.info(`[CacheManager] Evicted LRU item: ${key}`)
    }
  }
  
  evictBySize(requiredSize) {
    let freedSize = 0
    const toEvict = []
    
    // 从最旧的开始驱逐
    for (const key of this.accessOrder) {
      const data = this.memoryCache.get(key)
      if (data) {
        toEvict.push(key)
        freedSize += data.size
        if (freedSize >= requiredSize) break
      }
    }
    
    // 执行驱逐
    toEvict.forEach(key => {
      this.removeFromMemory(key)
      this.stats.evictions++
    })
    
    cacheLogger.info(`[CacheManager] Evicted ${toEvict.length} items to free ${freedSize} bytes`)
  }
  
  // === SessionStorage操作 ===
  
  getFromSession(key) {
    try {
      const data = sessionStorage.getItem(this.sessionPrefix + key)
      if (data) {
        return JSON.parse(data)
      }
    } catch (error) {
      cacheLogger.error('[CacheManager] SessionStorage read error:', error)
    }
    return null
  }
  
  setToSession(key, value, cacheData) {
    try {
      sessionStorage.setItem(
        this.sessionPrefix + key,
        JSON.stringify(cacheData)
      )
    } catch (error) {
      if (error.name === 'QuotaExceededError') {
        // 存储空间满，清理旧数据
        this.cleanSessionStorage()
        // 重试
        try {
          sessionStorage.setItem(
            this.sessionPrefix + key,
            JSON.stringify(cacheData)
          )
        } catch (retryError) {
          cacheLogger.error('[CacheManager] SessionStorage write failed:', retryError)
        }
      }
    }
  }
  
  removeFromSession(key) {
    sessionStorage.removeItem(this.sessionPrefix + key)
  }
  
  cleanSessionStorage() {
    const now = Date.now()
    const keys = Object.keys(sessionStorage)
    let removed = 0
    
    keys.forEach(key => {
      if (key.startsWith(this.sessionPrefix)) {
        try {
          const data = JSON.parse(sessionStorage.getItem(key))
          if (data.expiry < now) {
            sessionStorage.removeItem(key)
            removed++
          }
        } catch (error) {
          // 无效数据，删除
          sessionStorage.removeItem(key)
          removed++
        }
      }
    })
    
    cacheLogger.info(`[CacheManager] Cleaned ${removed} expired items from SessionStorage`)
  }
  
  // === IndexedDB操作 ===
  
  async getFromIndexed(key) {
    if (!this.db) return null
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['cache'], 'readonly')
      const store = transaction.objectStore('cache')
      const request = store.get(key)
      
      request.onsuccess = () => {
        resolve(request.result || null)
      }
      
      request.onerror = () => {
        cacheLogger.error('[CacheManager] IndexedDB read error:', request.error)
        reject(request.error)
      }
    })
  }
  
  async setToIndexed(key, value, cacheData) {
    if (!this.db) return
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['cache'], 'readwrite')
      const store = transaction.objectStore('cache')
      const request = store.put(cacheData)
      
      request.onsuccess = () => {
        resolve()
      }
      
      request.onerror = () => {
        cacheLogger.error('[CacheManager] IndexedDB write error:', request.error)
        reject(request.error)
      }
    })
  }
  
  async removeFromIndexed(key) {
    if (!this.db) return
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['cache'], 'readwrite')
      const store = transaction.objectStore('cache')
      const request = store.delete(key)
      
      request.onsuccess = () => {
        resolve()
      }
      
      request.onerror = () => {
        cacheLogger.error('[CacheManager] IndexedDB delete error:', request.error)
        reject(request.error)
      }
    })
  }
  
  async clearIndexed() {
    if (!this.db) return
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['cache'], 'readwrite')
      const store = transaction.objectStore('cache')
      const request = store.clear()
      
      request.onsuccess = () => {
        resolve()
      }
      
      request.onerror = () => {
        cacheLogger.error('[CacheManager] IndexedDB clear error:', request.error)
        reject(request.error)
      }
    })
  }
  
  // === 工具方法 ===
  
  /**
   * 验证缓存数据
   */
  isValid(data, ttl, validator) {
    // 检查过期
    if (data.expiry < Date.now()) {
      return false
    }
    
    // 自定义验证
    if (validator) {
      return validator(data.value, data.metadata)
    }
    
    return true
  }
  
  /**
   * 判断是否需要压缩
   */
  shouldCompress(value) {
    const size = this.calculateSize({ value })
    return size > 1024 // 大于1KB才压缩
  }
  
  /**
   * 压缩数据（简单实现，实际可用pako等库）
   */
  compress(value) {
    // 简单的JSON字符串压缩
    const json = JSON.stringify(value)
    // 实际项目中可以使用pako或lz-string
    return btoa(encodeURIComponent(json))
  }
  
  /**
   * 解压数据
   */
  decompress(compressed) {
    return JSON.parse(decodeURIComponent(atob(compressed)))
  }
  
  /**
   * 计算数据大小
   */
  calculateSize(data) {
    const str = JSON.stringify(data)
    return new Blob([str]).size
  }
  
  /**
   * 启动清理定时器
   */
  startCleanupTimer() {
    // 每5分钟清理一次过期数据
    setInterval(() => {
      this.cleanup()
    }, 5 * 60 * 1000)
  }
  
  /**
   * 清理过期数据
   */
  async cleanup() {
    const now = Date.now()
    let removed = 0
    
    // 清理内存缓存
    for (const [key, data] of this.memoryCache) {
      if (data.expiry < now) {
        this.removeFromMemory(key)
        removed++
      }
    }
    
    // 清理SessionStorage
    this.cleanSessionStorage()
    
    // 清理IndexedDB
    if (this.db) {
      await this.cleanIndexed()
    }
    
    if (removed > 0) {
      cacheLogger.info(`[CacheManager] Cleaned ${removed} expired items`)
    }
  }
  
  async cleanIndexed() {
    if (!this.db) return
    
    const now = Date.now()
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['cache'], 'readwrite')
      const store = transaction.objectStore('cache')
      const index = store.index('expiry')
      const range = IDBKeyRange.upperBound(now)
      const request = index.openCursor(range)
      
      let removed = 0
      
      request.onsuccess = (event) => {
        const cursor = event.target.result
        if (cursor) {
          store.delete(cursor.primaryKey)
          removed++
          cursor.continue()
        } else {
          cacheLogger.info(`[CacheManager] Cleaned ${removed} expired items from IndexedDB`)
          resolve(removed)
        }
      }
      
      request.onerror = () => {
        cacheLogger.error('[CacheManager] IndexedDB cleanup error:', request.error)
        reject(request.error)
      }
    })
  }
  
  /**
   * 获取缓存统计
   */
  getStats() {
    const hitRate = this.stats.hits + this.stats.misses > 0
      ? (this.stats.hits / (this.stats.hits + this.stats.misses) * 100).toFixed(2)
      : 0
    
    return {
      ...this.stats,
      hitRate: `${hitRate}%`,
      memoryItems: this.memoryCache.size,
      memorySize: this.memoryCacheSize,
      sessionItems: this.countSessionItems(),
      indexedItems: this.countIndexedItems()
    }
  }
  
  countSessionItems() {
    let count = 0
    const keys = Object.keys(sessionStorage)
    keys.forEach(key => {
      if (key.startsWith(this.sessionPrefix)) {
        count++
      }
    })
    return count
  }
  
  async countIndexedItems() {
    if (!this.db) return 0
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['cache'], 'readonly')
      const store = transaction.objectStore('cache')
      const request = store.count()
      
      request.onsuccess = () => {
        resolve(request.result)
      }
      
      request.onerror = () => {
        reject(request.error)
      }
    })
  }
  
  /**
   * 预加载数据
   */
  async preload(keys, fetcher) {
    const promises = keys.map(async key => {
      const cached = await this.get(key)
      if (cached === null && fetcher) {
        const value = await fetcher(key)
        await this.set(key, value)
      }
    })
    
    await Promise.allSettled(promises)
  }
}

// 创建默认实例
const cacheManager = new CacheManager({
  maxMemoryItems: 100,
  maxMemorySize: 10 * 1024 * 1024,
  defaultTTL: 5 * 60 * 1000
})

// 导出
export default cacheManager
export { CacheManager }