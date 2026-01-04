/**
 * 前端性能监控系统
 *
 * 功能特性：
 * - FPS监控
 * - 内存使用监控
 * - 网络请求监控
 * - 组件渲染性能
 * - 用户交互延迟
 * - 错误监控
 * - 性能报告生成
 */

import logger from '@/utils/logger'

const performanceMonitorLogger = logger.child('utils:performance-monitor')

import { ref, reactive, onMounted, onUnmounted } from 'vue'

class PerformanceMonitor {
  constructor() {
    // 性能指标
    this.metrics = reactive({
      fps: {
        current: 60,
        average: 60,
        min: 60,
        max: 60,
        samples: []
      },
      memory: {
        used: 0,
        limit: 0,
        usagePercent: 0
      },
      network: {
        requestCount: 0,
        totalSize: 0,
        averageLatency: 0,
        failedRequests: 0,
        pendingRequests: 0
      },
      rendering: {
        componentCount: 0,
        renderTime: 0,
        updateTime: 0,
        slowComponents: []
      },
      interaction: {
        clickLatency: 0,
        inputLatency: 0,
        scrollFPS: 60,
        animationFPS: 60
      },
      errors: {
        jsErrors: 0,
        resourceErrors: 0,
        networkErrors: 0,
        totalErrors: 0
      }
    })

    // 监控配置
    this.config = {
      enableFPS: true,
      enableMemory: true,
      enableNetwork: true,
      enableRendering: true,
      enableInteraction: true,
      enableErrors: true,
      sampleInterval: 1000,
      reportInterval: 60000
    }

    // 监控状态
    this.isMonitoring = ref(false)
    this.observers = []
    this.timers = []

    // 性能条目缓存
    this.performanceEntries = []

    // 初始化
    this.init()
  }

  init() {
    // 监听性能事件
    if (typeof window !== 'undefined') {
      // 监听资源加载
      this.setupResourceObserver()

      // 监听错误
      this.setupErrorHandlers()

      // 监听网络
      this.interceptNetworkRequests()
    }
  }

  /**
   * 开始监控
   */
  start() {
    if (this.isMonitoring.value) return

    this.isMonitoring.value = true

    // FPS监控
    if (this.config.enableFPS) {
      this.startFPSMonitoring()
    }

    // 内存监控
    if (this.config.enableMemory) {
      this.startMemoryMonitoring()
    }

    // 渲染监控
    if (this.config.enableRendering) {
      this.startRenderingMonitoring()
    }

    // 交互监控
    if (this.config.enableInteraction) {
      this.startInteractionMonitoring()
    }

    // 定期生成报告
    this.timers.push(
      setInterval(() => {
        this.generateReport()
      }, this.config.reportInterval)
    )

    performanceMonitorLogger.info('Performance monitoring started')
  }

  /**
   * 停止监控
   */
  stop() {
    this.isMonitoring.value = false

    // 清理定时器
    this.timers.forEach(timer => clearInterval(timer))
    this.timers = []

    // 断开观察器
    this.observers.forEach(observer => observer.disconnect())
    this.observers = []

    performanceMonitorLogger.info('Performance monitoring stopped')
  }

  /**
   * FPS监控
   */
  startFPSMonitoring() {
    let lastTime = performance.now()
    let frames = 0
    let fps = 60

    const measureFPS = () => {
      if (!this.isMonitoring.value) return

      frames++
      const currentTime = performance.now()

      if (currentTime >= lastTime + 1000) {
        fps = Math.round((frames * 1000) / (currentTime - lastTime))

        // 更新指标
        this.metrics.fps.current = fps
        this.metrics.fps.samples.push(fps)

        // 保持最近60个样本
        if (this.metrics.fps.samples.length > 60) {
          this.metrics.fps.samples.shift()
        }

        // 计算统计值
        this.updateFPSStats()

        frames = 0
        lastTime = currentTime
      }

      requestAnimationFrame(measureFPS)
    }

    requestAnimationFrame(measureFPS)
  }

  updateFPSStats() {
    const samples = this.metrics.fps.samples
    if (samples.length === 0) return

    this.metrics.fps.average = Math.round(
      samples.reduce((a, b) => a + b, 0) / samples.length
    )
    this.metrics.fps.min = Math.min(...samples)
    this.metrics.fps.max = Math.max(...samples)
  }

  /**
   * 内存监控
   */
  startMemoryMonitoring() {
    if (!performance.memory) {
      performanceMonitorLogger.warn('Memory monitoring not supported in this browser')
      return
    }

    const updateMemory = () => {
      if (!this.isMonitoring.value) return

      const memory = performance.memory
      this.metrics.memory.used = Math.round(memory.usedJSHeapSize / 1048576) // MB
      this.metrics.memory.limit = Math.round(memory.jsHeapSizeLimit / 1048576) // MB
      this.metrics.memory.usagePercent = Math.round(
        (memory.usedJSHeapSize / memory.jsHeapSizeLimit) * 100
      )
    }

    this.timers.push(
      setInterval(updateMemory, this.config.sampleInterval)
    )

    updateMemory()
  }

  /**
   * 渲染性能监控
   */
  startRenderingMonitoring() {
    // 使用PerformanceObserver监控渲染性能
    if ('PerformanceObserver' in window) {
      try {
        const observer = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            if (entry.entryType === 'measure') {
              // Vue组件渲染性能
              if (entry.name.startsWith('vue-')) {
                this.handleComponentPerformance(entry)
              }
            } else if (entry.entryType === 'paint') {
              // 绘制性能
              this.handlePaintPerformance(entry)
            }
          }
        })

        observer.observe({ entryTypes: ['measure', 'paint'] })
        this.observers.push(observer)
      } catch (error) {
        performanceMonitorLogger.error('Failed to setup rendering observer:', error)
      }
    }
  }

  handleComponentPerformance(entry) {
    const duration = entry.duration

    // 记录慢组件
    if (duration > 16) { // 超过一帧时间
      this.metrics.rendering.slowComponents.push({
        name: entry.name,
        duration: Math.round(duration * 100) / 100,
        timestamp: Date.now()
      })

      // 保持最近20个慢组件记录
      if (this.metrics.rendering.slowComponents.length > 20) {
        this.metrics.rendering.slowComponents.shift()
      }
    }

    // 更新平均渲染时间
    this.metrics.rendering.renderTime = Math.round(
      (this.metrics.rendering.renderTime + duration) / 2
    )
  }

  handlePaintPerformance(entry) {
    // 记录绘制性能
    performanceMonitorLogger.info(`Paint: ${entry.name} - ${entry.startTime}ms`)
  }

  /**
   * 交互性能监控
   */
  startInteractionMonitoring() {
    // 监控点击延迟
    let clickStartTime = 0

    document.addEventListener('mousedown', () => {
      clickStartTime = performance.now()
    })

    document.addEventListener('click', () => {
      if (clickStartTime) {
        const latency = performance.now() - clickStartTime
        this.metrics.interaction.clickLatency = Math.round(latency)
        clickStartTime = 0
      }
    })

    // 监控输入延迟
    let inputStartTime = 0

    document.addEventListener('input', (_event) => {
      if (!inputStartTime) {
        inputStartTime = performance.now()

        requestAnimationFrame(() => {
          const latency = performance.now() - inputStartTime
          this.metrics.interaction.inputLatency = Math.round(latency)
          inputStartTime = 0
        })
      }
    })

    // 监控滚动性能
    let scrollFrames = 0
    let scrollStartTime = 0
    let isScrolling = false

    document.addEventListener('scroll', () => {
      if (!isScrolling) {
        isScrolling = true
        scrollStartTime = performance.now()
        scrollFrames = 0

        const measureScrollFPS = () => {
          if (!isScrolling) return

          scrollFrames++
          const elapsed = performance.now() - scrollStartTime

          if (elapsed >= 1000) {
            this.metrics.interaction.scrollFPS = Math.round(
              (scrollFrames * 1000) / elapsed
            )
            isScrolling = false
          } else {
            requestAnimationFrame(measureScrollFPS)
          }
        }

        requestAnimationFrame(measureScrollFPS)
      }
    })

    // 滚动结束检测
    let scrollTimeout
    document.addEventListener('scroll', () => {
      clearTimeout(scrollTimeout)
      scrollTimeout = setTimeout(() => {
        isScrolling = false
      }, 150)
    })
  }

  /**
   * 资源加载监控
   */
  setupResourceObserver() {
    if ('PerformanceObserver' in window) {
      try {
        const observer = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            if (entry.entryType === 'resource') {
              this.handleResourceTiming(entry)
            }
          }
        })

        observer.observe({ entryTypes: ['resource'] })
        this.observers.push(observer)
      } catch (error) {
        performanceMonitorLogger.error('Failed to setup resource observer:', error)
      }
    }
  }

  handleResourceTiming(entry) {
    // 记录资源加载性能
    const duration = entry.duration
    const size = entry.transferSize || 0

    this.performanceEntries.push({
      name: entry.name,
      type: entry.initiatorType,
      duration: Math.round(duration),
      size,
      timestamp: Date.now()
    })

    // 保持最近100条记录
    if (this.performanceEntries.length > 100) {
      this.performanceEntries.shift()
    }
  }

  /**
   * 错误监控
   */
  setupErrorHandlers() {
    // JavaScript错误
    window.addEventListener('error', (event) => {
      this.metrics.errors.jsErrors++
      this.metrics.errors.totalErrors++

      performanceMonitorLogger.error('JS Error:', {
        message: event.message,
        source: event.filename,
        line: event.lineno,
        column: event.colno,
        error: event.error
      })
    })

    // Promise错误
    window.addEventListener('unhandledrejection', (event) => {
      this.metrics.errors.jsErrors++
      this.metrics.errors.totalErrors++

      performanceMonitorLogger.error('Unhandled Promise Rejection:', event.reason)
    })

    // 资源加载错误
    window.addEventListener('error', (event) => {
      if (event.target !== window) {
        this.metrics.errors.resourceErrors++
        this.metrics.errors.totalErrors++

        performanceMonitorLogger.error('Resource Error:', {
          type: event.target.tagName,
          source: event.target.src || event.target.href,
          message: 'Failed to load resource'
        })
      }
    }, true)
  }

  /**
   * 网络请求监控
   */
  interceptNetworkRequests() {
    // 拦截fetch
    const originalFetch = window.fetch
    window.fetch = async (...args) => {
      const startTime = performance.now()
      this.metrics.network.requestCount++
      this.metrics.network.pendingRequests++

      try {
        const response = await originalFetch(...args)
        const duration = performance.now() - startTime

        // 更新指标
        this.metrics.network.pendingRequests--
        this.metrics.network.averageLatency = Math.round(
          (this.metrics.network.averageLatency + duration) / 2
        )

        // 获取响应大小
        const size = response.headers.get('content-length') || 0
        this.metrics.network.totalSize += parseInt(size)

        if (!response.ok) {
          this.metrics.network.failedRequests++
          this.metrics.errors.networkErrors++
          this.metrics.errors.totalErrors++
        }

        return response
      } catch (error) {
        this.metrics.network.pendingRequests--
        this.metrics.network.failedRequests++
        this.metrics.errors.networkErrors++
        this.metrics.errors.totalErrors++
        throw error
      }
    }

    // 拦截XMLHttpRequest
    const originalXHROpen = XMLHttpRequest.prototype.open
    const originalXHRSend = XMLHttpRequest.prototype.send

    XMLHttpRequest.prototype.open = function(...args) {
      this._performanceStartTime = performance.now()
      return originalXHROpen.apply(this, args)
    }

    XMLHttpRequest.prototype.send = function(...args) {
      const monitor = this

      this.addEventListener('loadend', () => {
        const duration = performance.now() - monitor._performanceStartTime

        // 更新网络指标
        performanceMonitor.metrics.network.requestCount++
        performanceMonitor.metrics.network.averageLatency = Math.round(
          (performanceMonitor.metrics.network.averageLatency + duration) / 2
        )

        if (this.status >= 400) {
          performanceMonitor.metrics.network.failedRequests++
          performanceMonitor.metrics.errors.networkErrors++
          performanceMonitor.metrics.errors.totalErrors++
        }
      })

      return originalXHRSend.apply(this, args)
    }
  }

  /**
   * 生成性能报告
   */
  generateReport() {
    const report = {
      timestamp: Date.now(),
      metrics: { ...this.metrics },
      summary: this.generateSummary()
    }

    // 发送报告（可以发送到后端分析）
    performanceMonitorLogger.info('Performance Report:', report)

    // 触发自定义事件
    window.dispatchEvent(new CustomEvent('performance-report', { detail: report }))

    return report
  }

  generateSummary() {
    const fps = this.metrics.fps.average
    const memory = this.metrics.memory.usagePercent
    const errors = this.metrics.errors.totalErrors

    let health = 'good'
    const issues = []

    if (fps < 30) {
      health = 'poor'
      issues.push(`Low FPS: ${fps}`)
    } else if (fps < 50) {
      health = 'fair'
      issues.push(`Moderate FPS: ${fps}`)
    }

    if (memory > 80) {
      health = 'poor'
      issues.push(`High memory usage: ${memory}%`)
    } else if (memory > 60) {
      if (health === 'good') health = 'fair'
      issues.push(`Moderate memory usage: ${memory}%`)
    }

    if (errors > 10) {
      health = 'poor'
      issues.push(`High error rate: ${errors} errors`)
    } else if (errors > 5) {
      if (health === 'good') health = 'fair'
      issues.push(`Some errors detected: ${errors}`)
    }

    return {
      health,
      issues,
      score: this.calculatePerformanceScore()
    }
  }

  calculatePerformanceScore() {
    let score = 100

    // FPS评分 (40分)
    const fpsScore = Math.min(40, (this.metrics.fps.average / 60) * 40)
    score = fpsScore

    // 内存评分 (20分)
    const memoryScore = Math.max(0, 20 - (this.metrics.memory.usagePercent / 5))
    score += memoryScore

    // 网络评分 (20分)
    const networkScore = Math.max(0, 20 - (this.metrics.network.failedRequests * 2))
    score += networkScore

    // 错误评分 (20分)
    const errorScore = Math.max(0, 20 - (this.metrics.errors.totalErrors * 2))
    score += errorScore

    return Math.round(score)
  }

  /**
   * 获取性能指标
   */
  getMetrics() {
    return this.metrics
  }

  /**
   * 重置指标
   */
  reset() {
    this.metrics.fps.samples = []
    this.metrics.rendering.slowComponents = []
    this.metrics.errors.jsErrors = 0
    this.metrics.errors.resourceErrors = 0
    this.metrics.errors.networkErrors = 0
    this.metrics.errors.totalErrors = 0
    this.metrics.network.failedRequests = 0
    this.performanceEntries = []
  }
}

// 创建全局实例
const performanceMonitor = new PerformanceMonitor()

// Vue组合式API集成
export function usePerformanceMonitor() {
  const metrics = reactive(performanceMonitor.metrics)
  const isMonitoring = performanceMonitor.isMonitoring

  onMounted(() => {
    performanceMonitor.start()
  })

  onUnmounted(() => {
    performanceMonitor.stop()
  })

  return {
    metrics,
    isMonitoring,
    start: () => performanceMonitor.start(),
    stop: () => performanceMonitor.stop(),
    reset: () => performanceMonitor.reset(),
    generateReport: () => performanceMonitor.generateReport()
  }
}

export default performanceMonitor
