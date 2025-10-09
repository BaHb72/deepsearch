/**
 * 智能数据缓存管理器
 * 
 * 功能特性：
 * - 多层缓存（内存 + IndexedDB + SessionStorage）
 * - 智能过期策略
 * - 数据版本控制
 * - 增量更新支持
 * - 压缩存储
 * - 离线支持
 */

import logger from '@/utils/logger'

const dataCacheLogger = logger.child('utils:data-cache')

import { ref, computed } from 'vue'

// IndexedDB 配置
const DB_NAME = 'DeepSearchCache'
const DB_VERSION = 1
const STORE_NAME = 'dataCache'

class IndexedDBCache {
  constructor() {
    this.db = null
    this.initPromise = this.init()
  }
  
  async init() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION)
      
      request.onerror = () => reject(request.error)
      request.onsuccess = () => {
        this.db = request.result
        resolve()
      }
      
      request.onupgradeneeded = (event) => {
        const db = event.target.result
        
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const store = db.createObjectStore(STORE_NAME, { keyPath: 'key' })
          store.createIndex('expiry', 'expiry', { unique: false })
          store.createIndex('category', 'category', { unique: false })
        }
      }
    })
  }
  
  async set(key, value, expiry, category = 'default') {
    await this.initPromise
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([STORE_NAME], 'readwrite')
      const store = transaction.objectStore(STORE_NAME)
      
      const request = store.put({
        key,
        value,
        expiry,
        category,
        timestamp: Date.now()
      })
      
      request.onsuccess = () => resolve()
      request.onerror = () => reject(request.error)
    })
  }
  
  async get(key) {
    await this.initPromise
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([STORE_NAME], 'readonly')
      const store = transaction.objectStore(STORE_NAME)
      const request = store.get(key)
      
      request.onsuccess = () => {
        const result = request.result
        if (result && result.expiry > Date.now()) {
          resolve(result.value)
        } else {
          resolve(null)
        }
      }
      request.onerror = () => reject(request.error)
    })
  }
  
  async delete(key) {
    await this.initPromise
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([STORE_NAME], 'readwrite')
      const store = transaction.objectStore(STORE_NAME)
      const request = store.delete(key)
      
      request.onsuccess = () => resolve()
      request.onerror = () => reject(request.error)
    })
  }
  
  async clear(category = null) {
    await this.initPromise
    
    if (!category) {
      // 清空所有
      return new Promise((resolve, reject) => {
        const transaction = this.db.transaction([STORE_NAME], 'readwrite')
        const store = transaction.objectStore(STORE_NAME)
        const request = store.clear()
        
        request.onsuccess = () => resolve()
        request.onerror = () => reject(request.error)
      })
    } else {
      // 按类别清空
      return new Promise((resolve, reject) => {
        const transaction = this.db.transaction([STORE_NAME], 'readwrite')
        const store = transaction.objectStore(STORE_NAME)
        const index = store.index('category')
        const request = index.openCursor(IDBKeyRange.only(category))
        
        request.onsuccess = (event) => {
          const cursor = event.target.result
          if (cursor) {
            store.delete(cursor.primaryKey)
            cursor.continue()
          } else {
            resolve()
          }
        }
        request.onerror = () => reject(request.error)
      })
    }
  }
  
  async cleanExpired() {
    await this.initPromise
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([STORE_NAME], 'readwrite')
      const store = transaction.objectStore(STORE_NAME)
      const index = store.index('expiry')
      const request = index.openCursor(IDBKeyRange.upperBound(Date.now()))
      
      let deletedCount = 0
      
      request.onsuccess = (event) => {
        const cursor = event.target.result
        if (cursor) {
          store.delete(cursor.primaryKey)
          deletedCount++
          cursor.continue()
        } else {
          resolve(deletedCount)
        }
      }
      request.onerror = () => reject(request.error)
    })
  }
}

class MemoryCache {
  constructor(maxSize = 100, maxMemoryMB = 50) {
    this.cache = new Map()
    this.maxSize = maxSize
    this.maxMemory = maxMemoryMB * 1024 * 1024
    this.currentMemory = 0
    this.accessOrder = []
  }
  
  set(key, value, ttl = 3600000) {
    const size = this.estimateSize(value)
    
    // 检查内存限制
    while (this.currentMemory + size > this.maxMemory && this.cache.size > 0) {
      this.evictLRU()
    }
    
    // 检查数量限制
    while (this.cache.size >= this.maxSize) {
      this.evictLRU()
    }
    
    const expiry = Date.now() + ttl
    this.cache.set(key, { value, expiry, size })
    this.currentMemory += size
    this.updateAccessOrder(key)
  }
  
  get(key) {
    const item = this.cache.get(key)
    
    if (!item) return null
    
    if (item.expiry < Date.now()) {
      this.delete(key)
      return null
    }
    
    this.updateAccessOrder(key)
    return item.value
  }
  
  delete(key) {
    const item = this.cache.get(key)
    if (item) {
      this.currentMemory -= item.size
      this.cache.delete(key)
      const index = this.accessOrder.indexOf(key)
      if (index > -1) {
        this.accessOrder.splice(index, 1)
      }
    }
  }
  
  clear() {
    this.cache.clear()
    this.accessOrder = []
    this.currentMemory = 0
  }
  
  evictLRU() {
    if (this.accessOrder.length > 0) {
      const key = this.accessOrder.shift()
      this.delete(key)
    }
  }
  
  updateAccessOrder(key) {
    const index = this.accessOrder.indexOf(key)
    if (index > -1) {
      this.accessOrder.splice(index, 1)
    }
    this.accessOrder.push(key)
  }
  
  estimateSize(value) {
    // 简单估算对象大小
    const str = JSON.stringify(value)
    return str.length * 2 // UTF-16
  }
  
  getStats() {
    return {
      size: this.cache.size,
      memoryUsage: this.currentMemory,
      memoryUsageMB: (this.currentMemory / 1024 / 1024).toFixed(2)
    }
  }
}

class DataCache {
  constructor() {
    // 多层缓存
    this.memoryCache = new MemoryCache()
    this.indexedDBCache = new IndexedDBCache()
    
    // 缓存策略配置
    this.strategies = new Map()
    
    // 统计信息
    this.stats = ref({
      hits: 0,
      misses: 0,
      memoryHits: 0,
      diskHits: 0,
      networkFetches: 0
    })
    
    // 版本管理
    this.versions = new Map()
    
    // 离线模式
    this.isOffline = ref(!navigator.onLine)
    
    this.setupEventListeners()
    this.startCleanupTask()
  }
  
  setupEventListeners() {
    window.addEventListener('online', () => {
      this.isOffline.value = false
      dataCacheLogger.info('Cache: Online mode')
    })
    
    window.addEventListener('offline', () => {
      this.isOffline.value = true
      dataCacheLogger.info('Cache: Offline mode')
    })
  }
  
  startCleanupTask() {
    // 定期清理过期数据
    setInterval(async () => {
      try {
        const deletedCount = await this.indexedDBCache.cleanExpired()
        if (deletedCount > 0) {
          dataCacheLogger.info(`Cleaned ${deletedCount} expired cache entries`)
        }
      } catch (error) {
        dataCacheLogger.error('Cache cleanup error:', error)
      }
    }, 60000) // 每分钟清理一次
  }
  
  /**
   * 注册缓存策略
   */
  registerStrategy(key, strategy) {
    this.strategies.set(key, {
      ttl: strategy.ttl || 3600000, // 默认1小时
      category: strategy.category || 'default',
      version: strategy.version || 1,
      compress: strategy.compress || false,
      persistent: strategy.persistent !== false, // 默认持久化
      incremental: strategy.incremental || false, // 增量更新
      transform: strategy.transform || null, // 数据转换函数
      validator: strategy.validator || null // 数据验证函数
    })
  }
  
  /**
   * 获取数据（支持自动加载）
   */
  async get(key, loader = null) {
    const strategy = this.strategies.get(key) || {}
    
    // 1. 检查内存缓存
    let data = this.memoryCache.get(key)
    if (data !== null) {
      this.stats.value.hits++
      this.stats.value.memoryHits++
      return this.processData(data, strategy)
    }
    
    // 2. 检查持久化缓存
    if (strategy.persistent !== false) {
      try {
        data = await this.indexedDBCache.get(key)
        if (data !== null) {
          this.stats.value.hits++
          this.stats.value.diskHits++
          
          // 提升到内存缓存
          this.memoryCache.set(key, data, strategy.ttl)
          
          return this.processData(data, strategy)
        }
      } catch (error) {
        dataCacheLogger.error('IndexedDB read error:', error)
      }
    }
    
    // 3. 缓存未命中
    this.stats.value.misses++
    
    // 4. 离线模式检查
    if (this.isOffline.value && !loader) {
      return null
    }
    
    // 5. 使用加载器获取数据
    if (loader) {
      try {
        this.stats.value.networkFetches++
        data = await loader()
        
        // 验证数据
        if (strategy.validator && !strategy.validator(data)) {
          dataCacheLogger.warn(`Data validation failed for key: ${key}`)
          return null
        }
        
        // 缓存数据
        await this.set(key, data, strategy)
        
        return this.processData(data, strategy)
      } catch (error) {
        dataCacheLogger.error(`Loader error for key ${key}:`, error)
        
        // 降级到过期缓存
        return this.getStale(key)
      }
    }
    
    return null
  }
  
  /**
   * 设置缓存数据
   */
  async set(key, value, strategyOverride = {}) {
    const strategy = { ...(this.strategies.get(key) || {}), ...strategyOverride }
    
    // 数据转换
    let processedValue = value
    if (strategy.transform) {
      processedValue = strategy.transform(value)
    }
    
    // 压缩处理
    if (strategy.compress) {
      processedValue = this.compress(processedValue)
    }
    
    // 版本控制
    if (strategy.version) {
      this.versions.set(key, strategy.version)
    }
    
    // 设置内存缓存
    this.memoryCache.set(key, processedValue, strategy.ttl)
    
    // 设置持久化缓存
    if (strategy.persistent !== false) {
      try {
        const expiry = Date.now() + strategy.ttl
        await this.indexedDBCache.set(key, processedValue, expiry, strategy.category)
      } catch (error) {
        dataCacheLogger.error('IndexedDB write error:', error)
      }
    }
  }
  
  /**
   * 增量更新缓存
   */
  async update(key, updater) {
    const currentData = await this.get(key)
    if (currentData !== null) {
      const updatedData = await updater(currentData)
      await this.set(key, updatedData)
      return updatedData
    }
    return null
  }
  
  /**
   * 批量获取
   */
  async getMany(keys, loader = null) {
    const results = {}
    const missingKeys = []
    
    // 先从缓存获取
    for (const key of keys) {
      const data = await this.get(key)
      if (data !== null) {
        results[key] = data
      } else {
        missingKeys.push(key)
      }
    }
    
    // 批量加载缺失的数据
    if (missingKeys.length > 0 && loader) {
      try {
        const loadedData = await loader(missingKeys)
        for (const key of missingKeys) {
          if (loadedData[key]) {
            await this.set(key, loadedData[key])
            results[key] = loadedData[key]
          }
        }
      } catch (error) {
        dataCacheLogger.error('Batch loader error:', error)
      }
    }
    
    return results
  }
  
  /**
   * 删除缓存
   */
  async delete(key) {
    this.memoryCache.delete(key)
    await this.indexedDBCache.delete(key)
    this.versions.delete(key)
  }
  
  /**
   * 清空缓存
   */
  async clear(category = null) {
    if (!category) {
      this.memoryCache.clear()
      this.versions.clear()
    }
    await this.indexedDBCache.clear(category)
  }
  
  /**
   * 获取过期数据（降级方案）
   */
  async getStale(key) {
    // 尝试获取过期但仍存在的数据
    const data = this.memoryCache.cache.get(key)
    if (data) {
      return this.processData(data.value, this.strategies.get(key) || {})
    }
    
    // 从IndexedDB获取过期数据
    try {
      const result = await new Promise((resolve, reject) => {
        const transaction = this.indexedDBCache.db.transaction([STORE_NAME], 'readonly')
        const store = transaction.objectStore(STORE_NAME)
        const request = store.get(key)
        
        request.onsuccess = () => resolve(request.result)
        request.onerror = () => reject(request.error)
      })
      
      if (result) {
        return this.processData(result.value, this.strategies.get(key) || {})
      }
    } catch (error) {
      dataCacheLogger.error('Get stale data error:', error)
    }
    
    return null
  }
  
  /**
   * 处理数据（解压缩、转换等）
   */
  processData(data, strategy) {
    let processedData = data
    
    // 解压缩
    if (strategy.compress) {
      processedData = this.decompress(processedData)
    }
    
    return processedData
  }
  
  /**
   * 压缩数据
   */
  compress(data) {
    // 简单的压缩实现（实际应用中可以使用更高效的算法）
    const str = JSON.stringify(data)
    return btoa(str) // Base64编码作为简单压缩
  }
  
  /**
   * 解压缩数据
   */
  decompress(data) {
    try {
      const str = atob(data)
      return JSON.parse(str)
    } catch {
      return data // 如果解压失败，返回原数据
    }
  }
  
  /**
   * 获取缓存统计
   */
  getStats() {
    const memoryStats = this.memoryCache.getStats()
    const hitRate = this.stats.value.hits / (this.stats.value.hits + this.stats.value.misses) || 0
    
    return {
      ...this.stats.value,
      ...memoryStats,
      hitRate: (hitRate * 100).toFixed(2) + '%',
      isOffline: this.isOffline.value
    }
  }
  
  /**
   * 预热缓存
   */
  async warmup(items) {
    const promises = items.map(async ({ key, loader, strategy }) => {
      if (strategy) {
        this.registerStrategy(key, strategy)
      }
      return this.get(key, loader)
    })
    
    await Promise.allSettled(promises)
    dataCacheLogger.info('Cache warmup completed')
  }
}

// 创建全局实例
const dataCache = new DataCache()

// Vue组合式API集成
export function useDataCache() {
  const stats = computed(() => dataCache.getStats())
  const isOffline = computed(() => dataCache.isOffline.value)
  
  return {
    get: (key, loader) => dataCache.get(key, loader),
    set: (key, value, strategy) => dataCache.set(key, value, strategy),
    update: (key, updater) => dataCache.update(key, updater),
    getMany: (keys, loader) => dataCache.getMany(keys, loader),
    delete: (key) => dataCache.delete(key),
    clear: (category) => dataCache.clear(category),
    registerStrategy: (key, strategy) => dataCache.registerStrategy(key, strategy),
    warmup: (items) => dataCache.warmup(items),
    stats,
    isOffline
  }
}

export default dataCache