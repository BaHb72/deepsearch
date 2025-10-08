/**
 * 统一的轮询管理器
 * 
 * 功能特性：
 * - 页面可见性自动调节
 * - 智能调频（根据数据变化频率）
 * - 统一的错误处理
 * - 防止重复请求
 * - 支持批量管理
 */

import { getCurrentInstance, onUnmounted } from 'vue'
import logger from '@/utils/logger'

const pollingLogger = logger.child('utils:polling')

class PollingTask {
  constructor({
    key,
    fn,
    interval,
    immediate = false,
    enableVisibility = true,
    enableSmartInterval = true,
    minInterval = 1000,
    maxInterval = 60000,
    onError = null
  }) {
    this.key = key
    this.fn = fn
    this.baseInterval = interval
    this.currentInterval = interval
    this.immediate = immediate
    this.enableVisibility = enableVisibility
    this.enableSmartInterval = enableSmartInterval
    this.minInterval = minInterval
    this.maxInterval = maxInterval
    this.onError = onError
    
    this.timer = null
    this.running = false
    this.paused = false
    this.lastData = null
    this.lastError = null
    this.retryCount = 0
    this.maxRetries = 3
    
    // 性能统计
    this.stats = {
      totalPolls: 0,
      errors: 0,
      avgResponseTime: 0,
      lastPollTime: null,
      dataChangeRate: 0
    }
  }
  
  async execute() {
    if (this.running || this.paused) return
    
    this.running = true
    const startTime = Date.now()
    
    try {
      const data = await this.fn()
      
      // 更新统计
      this.stats.totalPolls++
      this.stats.lastPollTime = new Date()
      const responseTime = Date.now() - startTime
      this.stats.avgResponseTime = 
        (this.stats.avgResponseTime * (this.stats.totalPolls - 1) + responseTime) / this.stats.totalPolls
      
      // 智能调频
      if (this.enableSmartInterval) {
        this.adjustInterval(data)
      }
      
      this.lastData = data
      this.retryCount = 0
      this.lastError = null
      
      return data
    } catch (error) {
      this.stats.errors++
      this.lastError = error
      this.retryCount++
      
      // 错误处理
      if (this.onError) {
        this.onError(error, this.retryCount)
      }
      
      // 退避策略
      if (this.retryCount < this.maxRetries) {
        this.currentInterval = Math.min(
          this.currentInterval * Math.pow(2, this.retryCount),
          this.maxInterval
        )
      }
      
      throw error
    } finally {
      this.running = false
    }
  }
  
  adjustInterval(newData) {
    // 比较数据变化
    const hasChanged = JSON.stringify(newData) !== JSON.stringify(this.lastData)
    
    if (hasChanged) {
      // 数据变化，减小间隔
      this.currentInterval = Math.max(
        this.currentInterval * 0.8,
        this.minInterval
      )
      this.stats.dataChangeRate = Math.min(this.stats.dataChangeRate + 0.1, 1)
    } else {
      // 数据未变化，增大间隔
      this.currentInterval = Math.min(
        this.currentInterval * 1.2,
        this.maxInterval
      )
      this.stats.dataChangeRate = Math.max(this.stats.dataChangeRate - 0.05, 0)
    }
  }
  
  start() {
    if (this.timer) return
    
    const poll = async () => {
      try {
        await this.execute()
      } catch (error) {
        pollingLogger.error(`[TASK_ERROR] ${this.key}`, error)
      }
      
      if (!this.paused) {
        this.timer = setTimeout(poll, this.currentInterval)
      }
    }
    
    if (this.immediate) {
      poll()
    } else {
      this.timer = setTimeout(poll, this.currentInterval)
    }
  }
  
  stop() {
    if (this.timer) {
      clearTimeout(this.timer)
      this.timer = null
    }
    this.paused = false
    this.running = false
  }
  
  pause() {
    this.paused = true
    if (this.timer) {
      clearTimeout(this.timer)
      this.timer = null
    }
  }
  
  resume() {
    if (!this.paused) return
    this.paused = false
    this.start()
  }
  
  updateInterval(interval) {
    this.baseInterval = interval
    this.currentInterval = interval
  }
  
  getStats() {
    return {
      ...this.stats,
      currentInterval: this.currentInterval,
      isPaused: this.paused,
      isRunning: this.running,
      retryCount: this.retryCount
    }
  }
}

class PollingManager {
  constructor() {
    this.tasks = new Map()
    this.visibilityState = !document.hidden
    this.backgroundMultiplier = 3 // 后台运行时间隔倍数
    
    this.setupVisibilityListener()
  }
  
  setupVisibilityListener() {
    document.addEventListener('visibilitychange', () => {
      this.visibilityState = !document.hidden
      
      if (this.visibilityState) {
        // 页面可见，恢复正常轮询
        this.resumeAll()
      } else {
        // 页面隐藏，降低轮询频率
        this.reduceFrequency()
      }
    })
  }
  
  register(options) {
    const task = new PollingTask(options)
    this.tasks.set(options.key, task)
    return task
  }
  
  unregister(key) {
    const task = this.tasks.get(key)
    if (task) {
      task.stop()
      this.tasks.delete(key)
    }
  }
  
  start(key) {
    const task = this.tasks.get(key)
    if (task) {
      task.start()
    }
  }
  
  stop(key) {
    const task = this.tasks.get(key)
    if (task) {
      task.stop()
    }
  }
  
  pause(key) {
    const task = this.tasks.get(key)
    if (task) {
      task.pause()
    }
  }
  
  resume(key) {
    const task = this.tasks.get(key)
    if (task) {
      task.resume()
    }
  }
  
  startAll() {
    this.tasks.forEach(task => task.start())
  }
  
  stopAll() {
    this.tasks.forEach(task => task.stop())
  }
  
  pauseAll() {
    this.tasks.forEach(task => task.pause())
  }
  
  resumeAll() {
    this.tasks.forEach(task => {
      if (task.enableVisibility) {
        task.resume()
      }
    })
  }
  
  reduceFrequency() {
    this.tasks.forEach(task => {
      if (task.enableVisibility) {
        const originalInterval = task.currentInterval
        task.currentInterval = originalInterval * this.backgroundMultiplier
      }
    })
  }
  
  updateInterval(key, interval) {
    const task = this.tasks.get(key)
    if (task) {
      task.updateInterval(interval)
    }
  }
  
  getTask(key) {
    return this.tasks.get(key)
  }
  
  getAllStats() {
    const stats = {}
    this.tasks.forEach((task, key) => {
      stats[key] = task.getStats()
    })
    return stats
  }
  
  clear() {
    this.stopAll()
    this.tasks.clear()
  }
}

// 创建单例实例
const pollingManager = new PollingManager()

// Vue 3 Composition API 集成
export function usePolling(options) {
  const { key } = options
  
  const task = pollingManager.register(options)
  
  // 组件卸载时自动清理
  if (typeof getCurrentInstance !== 'undefined') {
    const instance = getCurrentInstance()
    if (instance) {
      onUnmounted(() => {
        pollingManager.unregister(key)
      })
    }
  }
  
  return {
    start: () => pollingManager.start(key),
    stop: () => pollingManager.stop(key),
    pause: () => pollingManager.pause(key),
    resume: () => pollingManager.resume(key),
    updateInterval: (interval) => pollingManager.updateInterval(key, interval),
    getStats: () => task.getStats()
  }
}

export default pollingManager
