/**
 * 性能优化工具集
 */

// 防抖函数
export function debounce(func, wait = 300, immediate = false) {
  let timeout
  return function executedFunction(...args) {
    const later = () => {
      timeout = null
      if (!immediate) func.apply(this, args)
    }
    const callNow = immediate && !timeout
    clearTimeout(timeout)
    timeout = setTimeout(later, wait)
    if (callNow) func.apply(this, args)
  }
}

// 节流函数
export function throttle(func, limit = 100) {
  let inThrottle
  let lastFunc
  let lastRan
  
  return function(...args) {
    if (!inThrottle) {
      func.apply(this, args)
      lastRan = Date.now()
      inThrottle = true
    } else {
      clearTimeout(lastFunc)
      lastFunc = setTimeout(() => {
        if ((Date.now() - lastRan) >= limit) {
          func.apply(this, args)
          lastRan = Date.now()
        }
      }, Math.max(limit - (Date.now() - lastRan), 0))
    }
  }
}

// 虚拟滚动类
export class VirtualScroller {
  constructor(options) {
    this.itemHeight = options.itemHeight || 50
    this.buffer = options.buffer || 5
    this.container = options.container
    this.items = options.items || []
    this.renderItem = options.renderItem
    
    this.visibleStart = 0
    this.visibleEnd = 0
    
    this.init()
  }
  
  init() {
    if (!this.container) return
    
    const containerHeight = this.container.clientHeight
    const visibleCount = Math.ceil(containerHeight / this.itemHeight)
    
    this.visibleEnd = visibleCount + this.buffer * 2
    
    this.container.addEventListener('scroll', throttle(() => {
      this.handleScroll()
    }, 16))
  }
  
  handleScroll() {
    const scrollTop = this.container.scrollTop
    const startIndex = Math.floor(scrollTop / this.itemHeight)
    const containerHeight = this.container.clientHeight
    const visibleCount = Math.ceil(containerHeight / this.itemHeight)
    
    this.visibleStart = Math.max(0, startIndex - this.buffer)
    this.visibleEnd = Math.min(
      this.items.length,
      startIndex + visibleCount + this.buffer
    )
    
    this.render()
  }
  
  render() {
    const visibleItems = this.items.slice(this.visibleStart, this.visibleEnd)
    
    if (this.renderItem) {
      this.renderItem(visibleItems, this.visibleStart)
    }
  }
  
  updateItems(items) {
    this.items = items
    this.handleScroll()
  }
}

// 懒加载图片
export function lazyLoadImages(selector = 'img[data-lazy]') {
  const images = document.querySelectorAll(selector)
  
  if ('IntersectionObserver' in window) {
    const imageObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const img = entry.target
          img.src = img.dataset.lazy
          img.removeAttribute('data-lazy')
          imageObserver.unobserve(img)
        }
      })
    })
    
    images.forEach(img => imageObserver.observe(img))
  } else {
    // Fallback for browsers that don't support IntersectionObserver
    images.forEach(img => {
      img.src = img.dataset.lazy
      img.removeAttribute('data-lazy')
    })
  }
}

// 缓存管理器
export class CacheManager {
  constructor(options = {}) {
    this.cache = new Map()
    this.maxSize = options.maxSize || 100
    this.ttl = options.ttl || 5 * 60 * 1000 // 默认5分钟
  }
  
  set(key, value, customTTL) {
    // 如果缓存已满，删除最旧的项
    if (this.cache.size >= this.maxSize) {
      const firstKey = this.cache.keys().next().value
      this.cache.delete(firstKey)
    }
    
    const ttl = customTTL || this.ttl
    const expiresAt = Date.now() + ttl
    
    this.cache.set(key, {
      value,
      expiresAt
    })
  }
  
  get(key) {
    const item = this.cache.get(key)
    
    if (!item) return null
    
    if (Date.now() > item.expiresAt) {
      this.cache.delete(key)
      return null
    }
    
    return item.value
  }
  
  has(key) {
    return this.get(key) !== null
  }
  
  clear() {
    this.cache.clear()
  }
  
  // 清理过期项
  cleanup() {
    const now = Date.now()
    for (const [key, item] of this.cache.entries()) {
      if (now > item.expiresAt) {
        this.cache.delete(key)
      }
    }
  }
}

// 批量请求处理器
export class BatchRequestProcessor {
  constructor(options = {}) {
    this.batchSize = options.batchSize || 10
    this.delay = options.delay || 100
    this.processor = options.processor
    this.queue = []
    this.processing = false
  }
  
  add(request) {
    return new Promise((resolve, reject) => {
      this.queue.push({
        request,
        resolve,
        reject
      })
      
      if (!this.processing) {
        this.process()
      }
    })
  }
  
  async process() {
    if (this.queue.length === 0) {
      this.processing = false
      return
    }
    
    this.processing = true
    
    // 取出一批请求
    const batch = this.queue.splice(0, this.batchSize)
    const requests = batch.map(item => item.request)
    
    try {
      // 批量处理
      const results = await this.processor(requests)
      
      // 分发结果
      batch.forEach((item, index) => {
        item.resolve(results[index])
      })
    } catch (error) {
      // 错误处理
      batch.forEach(item => {
        item.reject(error)
      })
    }
    
    // 延迟后处理下一批
    setTimeout(() => {
      this.process()
    }, this.delay)
  }
}

// 性能监控
export class PerformanceMonitor {
  constructor() {
    this.metrics = {}
    this.observers = []
  }
  
  // 测量函数执行时间
  measure(name, fn) {
    const start = performance.now()
    const result = fn()
    const duration = performance.now() - start
    
    if (!this.metrics[name]) {
      this.metrics[name] = []
    }
    
    this.metrics[name].push(duration)
    
    // 只保留最近100条记录
    if (this.metrics[name].length > 100) {
      this.metrics[name].shift()
    }
    
    return result
  }
  
  // 异步函数测量
  async measureAsync(name, fn) {
    const start = performance.now()
    const result = await fn()
    const duration = performance.now() - start
    
    if (!this.metrics[name]) {
      this.metrics[name] = []
    }
    
    this.metrics[name].push(duration)
    
    if (this.metrics[name].length > 100) {
      this.metrics[name].shift()
    }
    
    return result
  }
  
  // 获取统计信息
  getStats(name) {
    const data = this.metrics[name]
    if (!data || data.length === 0) return null
    
    const sorted = [...data].sort((a, b) => a - b)
    const sum = sorted.reduce((a, b) => a + b, 0)
    
    return {
      count: sorted.length,
      mean: sum / sorted.length,
      min: sorted[0],
      max: sorted[sorted.length - 1],
      p50: sorted[Math.floor(sorted.length * 0.5)],
      p95: sorted[Math.floor(sorted.length * 0.95)],
      p99: sorted[Math.floor(sorted.length * 0.99)]
    }
  }
  
  // 清空指标
  clear(name) {
    if (name) {
      delete this.metrics[name]
    } else {
      this.metrics = {}
    }
  }
  
  // 开始观察页面性能
  startObserving() {
    // 观察长任务
    if ('PerformanceObserver' in window) {
      try {
        const longTaskObserver = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            console.warn('Long task detected:', {
              duration: entry.duration,
              startTime: entry.startTime,
              name: entry.name
            })
          }
        })
        
        longTaskObserver.observe({ entryTypes: ['longtask'] })
        this.observers.push(longTaskObserver)
      } catch (e) {
        console.log('Long task observer not supported')
      }
      
      // 观察布局偏移
      try {
        const layoutShiftObserver = new PerformanceObserver((list) => {
          let cls = 0
          for (const entry of list.getEntries()) {
            if (!entry.hadRecentInput) {
              cls += entry.value
            }
          }
          if (cls > 0.1) {
            console.warn('High layout shift detected:', cls)
          }
        })
        
        layoutShiftObserver.observe({ entryTypes: ['layout-shift'] })
        this.observers.push(layoutShiftObserver)
      } catch (e) {
        console.log('Layout shift observer not supported')
      }
    }
  }
  
  // 停止观察
  stopObserving() {
    this.observers.forEach(observer => observer.disconnect())
    this.observers = []
  }
}

// 创建全局实例
export const performanceMonitor = new PerformanceMonitor()
export const globalCache = new CacheManager()

// 自动开始监控
if (process.env.NODE_ENV === 'development') {
  performanceMonitor.startObserving()
}