/**
 * 智能轮询管理器
 * 
 * 特性：
 * - 页面可见性检测
 * - 自适应频率调整
 * - 数据变化检测
 * - 批量管理轮询任务
 */

import logger from '@/utils/logger'

const pollingLogger = logger.child('utils:polling')

class PollingManager {
  constructor() {
    this.pollers = new Map()
    this.visibility = !document.hidden
    this.focused = document.hasFocus()
    this.globalPaused = false
    
    // 监听页面可见性变化
    document.addEventListener('visibilitychange', () => {
      this.visibility = !document.hidden
      pollingLogger.info('[PollingManager] Visibility changed:', this.visibility)
      this.updateAllPollingRates()
    })
    
    // 监听窗口焦点变化
    window.addEventListener('focus', () => {
      this.focused = true
      pollingLogger.info('[PollingManager] Window focused')
      this.updateAllPollingRates()
    })
    
    window.addEventListener('blur', () => {
      this.focused = false
      pollingLogger.info('[PollingManager] Window blurred')
      this.updateAllPollingRates()
    })
    
    // 监听网络状态
    window.addEventListener('online', () => {
      pollingLogger.info('[PollingManager] Network online')
      this.resumeAll()
    })
    
    window.addEventListener('offline', () => {
      pollingLogger.info('[PollingManager] Network offline')
      this.pauseAll()
    })
  }
  
  /**
   * 注册轮询任务
   * @param {string} key - 唯一标识符
   * @param {Function} callback - 轮询回调函数
   * @param {Object} options - 配置选项
   */
  register(key, callback, options = {}) {
    const {
      interval = 5000,           // 默认轮询间隔
      minInterval = 1000,         // 最小间隔
      maxInterval = 60000,        // 最大间隔
      adaptive = true,            // 是否自适应调整
      immediate = true,           // 是否立即执行
      retryOnError = true,        // 错误时是否重试
      maxRetries = 3,             // 最大重试次数
      backoffMultiplier = 2,      // 退避倍数
      compareData = JSON.stringify // 数据比较函数
    } = options
    
    // 如果已存在，先停止
    if (this.pollers.has(key)) {
      this.stop(key)
    }
    
    const poller = {
      key,
      callback,
      interval,
      currentInterval: interval,
      minInterval,
      maxInterval,
      adaptive,
      immediate,
      retryOnError,
      maxRetries,
      backoffMultiplier,
      compareData,
      timer: null,
      lastData: null,
      lastHash: null,
      unchangedCount: 0,
      errorCount: 0,
      successCount: 0,
      lastExecutionTime: 0,
      averageExecutionTime: 0,
      status: 'idle' // idle | running | paused | error
    }
    
    this.pollers.set(key, poller)
    
    // 立即执行一次
    if (immediate && !this.globalPaused) {
      this.execute(key)
    }
    
    // 启动轮询
    this.start(key)
    
    return key
  }
  
  /**
   * 执行轮询任务
   */
  async execute(key) {
    const poller = this.pollers.get(key)
    if (!poller || poller.status === 'paused') return
    
    // 标记为运行中
    poller.status = 'running'
    const startTime = performance.now()
    
    try {
      // 执行回调
      const data = await poller.callback()
      
      // 记录执行时间
      const executionTime = performance.now() - startTime
      poller.lastExecutionTime = executionTime
      poller.averageExecutionTime = poller.successCount === 0
        ? executionTime
        : (poller.averageExecutionTime * poller.successCount + executionTime) / (poller.successCount + 1)
      
      // 成功计数
      poller.successCount++
      poller.errorCount = 0 // 重置错误计数
      
      // 自适应调整频率
      if (poller.adaptive) {
        this.adaptInterval(key, data)
      }
      
      poller.status = 'idle'
      
      // 返回数据供外部使用
      return data
      
    } catch (error) {
      pollingLogger.error(`[PollingManager] Error in ${key}:`, error)
      poller.errorCount++
      poller.status = 'error'
      
      // 错误重试逻辑
      if (poller.retryOnError && poller.errorCount <= poller.maxRetries) {
        // 使用指数退避
        const retryInterval = Math.min(
          poller.currentInterval * Math.pow(poller.backoffMultiplier, poller.errorCount),
          poller.maxInterval
        )
        pollingLogger.info(`[PollingManager] Retrying ${key} in ${retryInterval}ms`)
        this.setInterval(key, retryInterval)
      } else if (poller.errorCount > poller.maxRetries) {
        // 超过最大重试次数，暂停轮询
        pollingLogger.error(`[PollingManager] Max retries exceeded for ${key}, pausing`)
        this.pause(key)
      }
      
      throw error
    }
  }
  
  /**
   * 自适应调整轮询间隔
   */
  adaptInterval(key, data) {
    const poller = this.pollers.get(key)
    if (!poller) return
    
    // 计算数据哈希
    const dataHash = poller.compareData(data)
    
    if (dataHash === poller.lastHash) {
      // 数据未变化
      poller.unchangedCount++
      
      // 根据未变化次数调整间隔
      if (poller.unchangedCount >= 3) {
        // 连续3次未变化，增加间隔
        const newInterval = Math.min(
          poller.currentInterval * 1.5,
          poller.maxInterval
        )
        if (newInterval !== poller.currentInterval) {
          pollingLogger.info(`[PollingManager] ${key}: Data unchanged ${poller.unchangedCount} times, increasing interval to ${newInterval}ms`)
          this.setInterval(key, newInterval)
        }
      }
    } else {
      // 数据有变化
      if (poller.unchangedCount > 0) {
        pollingLogger.info(`[PollingManager] ${key}: Data changed after ${poller.unchangedCount} unchanged polls`)
      }
      
      poller.unchangedCount = 0
      poller.lastHash = dataHash
      poller.lastData = data
      
      // 恢复到正常间隔
      if (poller.currentInterval > poller.interval) {
        pollingLogger.info(`[PollingManager] ${key}: Data changed, restoring interval to ${poller.interval}ms`)
        this.setInterval(key, poller.interval)
      }
    }
  }
  
  /**
   * 设置轮询间隔
   */
  setInterval(key, interval) {
    const poller = this.pollers.get(key)
    if (!poller) return
    
    poller.currentInterval = interval
    
    // 重启定时器
    if (poller.timer) {
      clearTimeout(poller.timer)
    }
    
    if (!this.globalPaused && poller.status !== 'paused') {
      this.scheduleNext(key)
    }
  }
  
  /**
   * 安排下次执行
   */
  scheduleNext(key) {
    const poller = this.pollers.get(key)
    if (!poller || poller.status === 'paused') return
    
    poller.timer = setTimeout(async () => {
      await this.execute(key)
      // 执行完成后安排下次
      if (poller.status !== 'paused') {
        this.scheduleNext(key)
      }
    }, poller.currentInterval)
  }
  
  /**
   * 启动轮询
   */
  start(key) {
    const poller = this.pollers.get(key)
    if (!poller) return
    
    pollingLogger.info(`[PollingManager] Starting ${key}`)
    poller.status = 'idle'
    this.scheduleNext(key)
  }
  
  /**
   * 停止轮询
   */
  stop(key) {
    const poller = this.pollers.get(key)
    if (!poller) return
    
    pollingLogger.info(`[PollingManager] Stopping ${key}`)
    
    if (poller.timer) {
      clearTimeout(poller.timer)
      poller.timer = null
    }
    
    poller.status = 'idle'
  }
  
  /**
   * 暂停轮询
   */
  pause(key) {
    const poller = this.pollers.get(key)
    if (!poller) return
    
    pollingLogger.info(`[PollingManager] Pausing ${key}`)
    
    if (poller.timer) {
      clearTimeout(poller.timer)
      poller.timer = null
    }
    
    poller.status = 'paused'
  }
  
  /**
   * 恢复轮询
   */
  resume(key) {
    const poller = this.pollers.get(key)
    if (!poller || poller.status !== 'paused') return
    
    pollingLogger.info(`[PollingManager] Resuming ${key}`)
    poller.status = 'idle'
    
    // 立即执行一次
    this.execute(key)
    // 然后恢复轮询
    this.scheduleNext(key)
  }
  
  /**
   * 移除轮询
   */
  unregister(key) {
    pollingLogger.info(`[PollingManager] Unregistering ${key}`)
    this.stop(key)
    this.pollers.delete(key)
  }
  
  /**
   * 更新所有轮询的频率
   */
  updateAllPollingRates() {
    for (const [key, poller] of this.pollers) {
      if (poller.status === 'paused') continue
      
      if (!this.visibility) {
        // 页面不可见，暂停或降低频率
        if (poller.adaptive) {
          pollingLogger.info(`[PollingManager] Page hidden, pausing ${key}`)
          this.pause(key)
        }
      } else if (!this.focused) {
        // 失去焦点，降低频率
        const slowInterval = Math.min(poller.currentInterval * 2, poller.maxInterval)
        pollingLogger.info(`[PollingManager] Window blurred, slowing ${key} to ${slowInterval}ms`)
        this.setInterval(key, slowInterval)
      } else {
        // 恢复正常
        if (poller.status === 'paused' && poller.adaptive) {
          pollingLogger.info(`[PollingManager] Page visible, resuming ${key}`)
          this.resume(key)
        } else {
          pollingLogger.info(`[PollingManager] Window focused, restoring ${key} to ${poller.interval}ms`)
          this.setInterval(key, poller.interval)
        }
      }
    }
  }
  
  /**
   * 暂停所有轮询
   */
  pauseAll() {
    pollingLogger.info('[PollingManager] Pausing all pollers')
    this.globalPaused = true
    for (const key of this.pollers.keys()) {
      this.pause(key)
    }
  }
  
  /**
   * 恢复所有轮询
   */
  resumeAll() {
    pollingLogger.info('[PollingManager] Resuming all pollers')
    this.globalPaused = false
    for (const key of this.pollers.keys()) {
      this.resume(key)
    }
  }
  
  /**
   * 获取统计信息
   */
  getStats() {
    const stats = {
      total: this.pollers.size,
      running: 0,
      paused: 0,
      error: 0,
      details: {}
    }
    
    for (const [key, poller] of this.pollers) {
      if (poller.status === 'running') stats.running++
      else if (poller.status === 'paused') stats.paused++
      else if (poller.status === 'error') stats.error++
      
      stats.details[key] = {
        status: poller.status,
        currentInterval: poller.currentInterval,
        unchangedCount: poller.unchangedCount,
        errorCount: poller.errorCount,
        successCount: poller.successCount,
        averageExecutionTime: Math.round(poller.averageExecutionTime)
      }
    }
    
    return stats
  }
  
  /**
   * 清理所有轮询
   */
  destroy() {
    pollingLogger.info('[PollingManager] Destroying all pollers')
    for (const key of this.pollers.keys()) {
      this.unregister(key)
    }
  }
}

// 创建单例实例
const pollingManager = new PollingManager()

// 导出
export default pollingManager
export { PollingManager }