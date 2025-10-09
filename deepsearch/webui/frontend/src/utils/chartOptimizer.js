/**
 * ECharts 图表优化工具
 * 提供性能优化、内存管理、渲染优化等功能
 */

import logger from '@/utils/logger'
import { ref, onMounted, onUnmounted } from 'vue'

const chartOptimizerLogger = logger.child('utils:chart-optimizer')

import * as echarts from 'echarts'
import { debounce } from 'lodash-es'

/**
 * 图表优化配置
 */
export const CHART_OPTIMIZATION_CONFIG = {
  // 渲染优化
  rendering: {
    progressive: 400,           // 渐进式渲染阈值
    progressiveThreshold: 3000, // 渐进式渲染数据量阈值
    animation: false,           // 关闭动画以提升性能
    animationDuration: 300,     // 动画持续时间（如果启用）
    animationEasing: 'linear'   // 使用线性动画
  },
  
  // 数据采样
  sampling: {
    enabled: true,
    strategy: 'lttb',          // Largest Triangle Three Bucket 算法
    threshold: 1000,           // 采样阈值
    rate: 0.1                  // 采样率
  },
  
  // 内存管理
  memory: {
    maxSeriesData: 10000,      // 单系列最大数据点
    maxTotalData: 50000,       // 总数据点最大值
    enableGC: true,            // 启用垃圾回收
    gcInterval: 60000          // GC间隔（毫秒）
  },
  
  // 渲染策略
  strategy: {
    useWebGL: true,            // 使用 WebGL 渲染（大数据量）
    useWorker: true,           // 使用 Web Worker
    lazyUpdate: true,          // 懒更新
    silent: false              // 静默模式
  }
}

/**
 * 图表管理器
 */
class ChartManager {
  constructor() {
    this.charts = new Map()
    this.disposalQueue = []
    this.gcTimer = null
    this.performanceMonitor = new ChartPerformanceMonitor()
    
    this.init()
  }

  init() {
    // 启动垃圾回收
    if (CHART_OPTIMIZATION_CONFIG.memory.enableGC) {
      this.startGarbageCollection()
    }

    // 监听页面隐藏事件
    document.addEventListener('visibilitychange', this.handleVisibilityChange)
    
    // 监听内存压力
    if ('memory' in performance) {
      setInterval(() => {
        this.checkMemoryPressure()
      }, 10000)
    }
  }

  /**
   * 创建优化的图表实例
   */
  createChart(container, options = {}) {
    const chartId = this.generateChartId()
    
    // 检查容器
    if (!container || !container.offsetWidth || !container.offsetHeight) {
      chartOptimizerLogger.warn('Chart container is not ready:', container)
      return null
    }

    // 确定渲染器
    const renderer = this.determineRenderer(options)
    
    // 创建图表实例
    const chart = echarts.init(container, null, {
      renderer,
      devicePixelRatio: window.devicePixelRatio || 1,
      width: 'auto',
      height: 'auto',
      ...options
    })

    // 存储图表信息
    this.charts.set(chartId, {
      instance: chart,
      container,
      options,
      dataCount: 0,
      lastUpdate: Date.now(),
      memoryUsage: 0
    })

    // 设置自动调整大小
    this.setupAutoResize(chartId)

    return { chart, chartId }
  }

  /**
   * 确定渲染器类型
   */
  determineRenderer(options) {
    const dataCount = options.dataCount || 0
    
    // 大数据量使用 Canvas
    if (dataCount > 5000) {
      return 'canvas'
    }
    
    // 需要交互的使用 SVG
    if (options.interactive) {
      return 'svg'
    }
    
    // 默认 Canvas
    return 'canvas'
  }

  /**
   * 设置图表选项（带优化）
   */
  setOption(chartId, option, notMerge = false) {
    const chartInfo = this.charts.get(chartId)
    if (!chartInfo) return

    const { instance } = chartInfo
    
    // 优化选项
    const optimizedOption = this.optimizeOption(option)
    
    // 记录性能
    const startTime = performance.now()
    
    // 设置选项
    instance.setOption(optimizedOption, notMerge, true)
    
    // 更新信息
    chartInfo.lastUpdate = Date.now()
    chartInfo.dataCount = this.calculateDataCount(optimizedOption)
    
    // 记录性能指标
    const renderTime = performance.now() - startTime
    this.performanceMonitor.record(chartId, 'render', renderTime)
    
    // 检查是否需要优化
    if (renderTime > 100) {
      chartOptimizerLogger.warn(`Chart ${chartId} rendering took ${renderTime}ms`)
      this.suggestOptimizations(chartInfo)
    }
  }

  /**
   * 优化图表选项
   */
  optimizeOption(option) {
    const optimized = { ...option }
    
    // 应用渲染优化
    if (!optimized.animation) {
      optimized.animation = CHART_OPTIMIZATION_CONFIG.rendering.animation
    }
    
    if (optimized.series) {
      optimized.series = optimized.series.map(series => {
        const optimizedSeries = { ...series }
        
        // 数据采样
        if (series.data && series.data.length > CHART_OPTIMIZATION_CONFIG.sampling.threshold) {
          optimizedSeries.data = this.sampleData(series.data)
          optimizedSeries.sampling = 'lttb'
        }
        
        // 大数据量优化
        if (series.data && series.data.length > 5000) {
          optimizedSeries.large = true
          optimizedSeries.largeThreshold = 3000
          optimizedSeries.progressive = CHART_OPTIMIZATION_CONFIG.rendering.progressive
        }
        
        // 关闭不必要的视觉效果
        if (series.type === 'line' && series.data && series.data.length > 1000) {
          optimizedSeries.showSymbol = false
          optimizedSeries.smooth = false
        }
        
        return optimizedSeries
      })
    }
    
    // 优化坐标轴
    if (optimized.xAxis) {
      optimized.xAxis = this.optimizeAxis(optimized.xAxis)
    }
    if (optimized.yAxis) {
      optimized.yAxis = this.optimizeAxis(optimized.yAxis)
    }
    
    // 优化 DataZoom
    if (optimized.dataZoom) {
      optimized.dataZoom = optimized.dataZoom.map(zoom => ({
        ...zoom,
        throttle: 100,
        filterMode: 'weakFilter'
      }))
    }
    
    return optimized
  }

  /**
   * 优化坐标轴
   */
  optimizeAxis(axis) {
    if (Array.isArray(axis)) {
      return axis.map(a => this.optimizeAxis(a))
    }
    
    return {
      ...axis,
      axisLabel: {
        ...axis.axisLabel,
        hideOverlap: true  // 隐藏重叠标签
      },
      splitLine: {
        ...axis.splitLine,
        show: false  // 默认隐藏网格线
      }
    }
  }

  /**
   * 数据采样（LTTB算法）
   */
  sampleData(data, targetCount = 500) {
    if (data.length <= targetCount) return data
    
    const sampled = []
    const bucketSize = (data.length - 2) / (targetCount - 2)
    
    // 保留第一个点
    sampled.push(data[0])
    
    let prevIndex = 0
    
    for (let i = 1; i < targetCount - 1; i++) {
      const bucketStart = Math.floor((i - 1) * bucketSize) + 1
      const bucketEnd = Math.floor(i * bucketSize) + 1
      
      let maxArea = 0
      let maxAreaIndex = bucketStart
      
      for (let j = bucketStart; j < bucketEnd && j < data.length; j++) {
        // 计算三角形面积
        const area = Math.abs(
          (data[prevIndex][0] - data[data.length - 1][0]) * (data[j][1] - data[prevIndex][1]) -
          (data[prevIndex][0] - data[j][0]) * (data[data.length - 1][1] - data[prevIndex][1])
        )
        
        if (area > maxArea) {
          maxArea = area
          maxAreaIndex = j
        }
      }
      
      sampled.push(data[maxAreaIndex])
      prevIndex = maxAreaIndex
    }
    
    // 保留最后一个点
    sampled.push(data[data.length - 1])
    
    return sampled
  }

  /**
   * 批量更新图表
   */
  batchUpdate(updates) {
    // 使用 requestAnimationFrame 批量更新
    requestAnimationFrame(() => {
      updates.forEach(({ chartId, option }) => {
        this.setOption(chartId, option)
      })
    })
  }

  /**
   * 设置自动调整大小
   */
  setupAutoResize(chartId) {
    const chartInfo = this.charts.get(chartId)
    if (!chartInfo) return
    
    const { instance, container } = chartInfo
    
    // 使用防抖优化
    const resizeHandler = debounce(() => {
      if (container.offsetWidth && container.offsetHeight) {
        instance.resize()
      }
    }, 200)
    
    // ResizeObserver
    if (window.ResizeObserver) {
      const observer = new ResizeObserver(resizeHandler)
      observer.observe(container)
      chartInfo.resizeObserver = observer
    } else {
      // 降级方案
      window.addEventListener('resize', resizeHandler)
      chartInfo.resizeHandler = resizeHandler
    }
  }

  /**
   * 销毁图表
   */
  dispose(chartId) {
    const chartInfo = this.charts.get(chartId)
    if (!chartInfo) return
    
    const { instance, resizeObserver, resizeHandler } = chartInfo
    
    // 清理 ResizeObserver
    if (resizeObserver) {
      resizeObserver.disconnect()
    }
    
    // 清理 resize 事件
    if (resizeHandler) {
      window.removeEventListener('resize', resizeHandler)
    }
    
    // 销毁图表实例
    instance.dispose()
    
    // 从管理器中移除
    this.charts.delete(chartId)
    
    // 记录性能
    this.performanceMonitor.record(chartId, 'dispose', 0)
  }

  /**
   * 清理所有图表
   */
  disposeAll() {
    this.charts.forEach((_, chartId) => {
      this.dispose(chartId)
    })
  }

  /**
   * 垃圾回收
   */
  startGarbageCollection() {
    this.gcTimer = setInterval(() => {
      this.performGarbageCollection()
    }, CHART_OPTIMIZATION_CONFIG.memory.gcInterval)
  }

  performGarbageCollection() {
    const now = Date.now()
    const staleThreshold = 5 * 60 * 1000 // 5分钟
    
    this.charts.forEach((chartInfo, chartId) => {
      // 清理长时间未更新的图表
      if (now - chartInfo.lastUpdate > staleThreshold) {
        chartOptimizerLogger.info(`GC: Disposing stale chart ${chartId}`)
        this.dispose(chartId)
      }
    })
    
    // 检查内存使用
    if ('memory' in performance) {
      const memoryInfo = performance.memory
      const usageRatio = memoryInfo.usedJSHeapSize / memoryInfo.jsHeapSizeLimit
      
      if (usageRatio > 0.8) {
        chartOptimizerLogger.warn('Memory pressure detected, clearing chart cache')
        this.clearCache()
      }
    }
  }

  /**
   * 检查内存压力
   */
  checkMemoryPressure() {
    if (!('memory' in performance)) return
    
    const memoryInfo = performance.memory
    const usageRatio = memoryInfo.usedJSHeapSize / memoryInfo.jsHeapSizeLimit
    
    if (usageRatio > 0.9) {
      // 紧急清理
      this.emergencyCleanup()
    }
  }

  /**
   * 紧急清理
   */
  emergencyCleanup() {
    chartOptimizerLogger.warn('Emergency cleanup triggered')
    
    // 清理所有非活动图表
    const activeCharts = new Set()
    document.querySelectorAll('[_echarts_instance_]').forEach(el => {
      const instanceId = el.getAttribute('_echarts_instance_')
      activeCharts.add(instanceId)
    })
    
    this.charts.forEach((_, chartId) => {
      if (!activeCharts.has(chartId)) {
        this.dispose(chartId)
      }
    })
  }

  /**
   * 清理缓存
   */
  clearCache() {
    // 清理 ECharts 内部缓存
    if (echarts.dispose) {
      document.querySelectorAll('[_echarts_instance_]').forEach(el => {
        if (!this.charts.has(el.getAttribute('_echarts_instance_'))) {
          echarts.dispose(el)
        }
      })
    }
  }

  /**
   * 页面可见性变化处理
   */
  handleVisibilityChange = () => {
    if (document.hidden) {
      // 页面隐藏时暂停渲染
      this.charts.forEach(chartInfo => {
        chartInfo.instance.clear()
      })
    } else {
      // 页面显示时恢复渲染
      this.charts.forEach(chartInfo => {
        chartInfo.instance.restore()
      })
    }
  }

  /**
   * 建议优化
   */
  suggestOptimizations(chartInfo) {
    const suggestions = []
    
    if (chartInfo.dataCount > 10000) {
      suggestions.push('Consider using data sampling')
    }
    
    if (chartInfo.dataCount > 50000) {
      suggestions.push('Consider using WebGL renderer')
    }
    
    if (suggestions.length > 0) {
      chartOptimizerLogger.info('Optimization suggestions:', suggestions)
    }
  }

  /**
   * 计算数据点数量
   */
  calculateDataCount(option) {
    let count = 0
    
    if (option.series) {
      option.series.forEach(series => {
        if (series.data) {
          count += series.data.length
        }
      })
    }
    
    return count
  }

  /**
   * 生成图表ID
   */
  generateChartId() {
    return `chart_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  /**
   * 获取性能报告
   */
  getPerformanceReport() {
    return this.performanceMonitor.getReport()
  }
}

/**
 * 图表性能监控器
 */
class ChartPerformanceMonitor {
  constructor() {
    this.metrics = new Map()
  }

  record(chartId, action, value) {
    if (!this.metrics.has(chartId)) {
      this.metrics.set(chartId, {
        renders: [],
        updates: [],
        disposes: []
      })
    }
    
    const metrics = this.metrics.get(chartId)
    
    switch (action) {
      case 'render':
        metrics.renders.push({ time: Date.now(), duration: value })
        break
      case 'update':
        metrics.updates.push({ time: Date.now(), duration: value })
        break
      case 'dispose':
        metrics.disposes.push({ time: Date.now() })
        break
    }
    
    // 保留最近100条记录
    if (metrics.renders.length > 100) {
      metrics.renders.shift()
    }
    if (metrics.updates.length > 100) {
      metrics.updates.shift()
    }
  }

  getReport() {
    const report = {}
    
    this.metrics.forEach((metrics, chartId) => {
      const avgRenderTime = metrics.renders.reduce((sum, r) => sum + r.duration, 0) / metrics.renders.length || 0
      const avgUpdateTime = metrics.updates.reduce((sum, u) => sum + u.duration, 0) / metrics.updates.length || 0
      
      report[chartId] = {
        avgRenderTime: avgRenderTime.toFixed(2),
        avgUpdateTime: avgUpdateTime.toFixed(2),
        totalRenders: metrics.renders.length,
        totalUpdates: metrics.updates.length,
        totalDisposes: metrics.disposes.length
      }
    })
    
    return report
  }
}

// 创建全局实例
export const chartManager = new ChartManager()

/**
 * Vue 3 组合式 API Hook
 */
export function useOptimizedChart(containerRef, options = {}) {
  const chartInstance = ref(null)
  const chartId = ref(null)
  
  const initChart = () => {
    if (!containerRef.value) return
    
    const result = chartManager.createChart(containerRef.value, options)
    if (result) {
      chartInstance.value = result.chart
      chartId.value = result.chartId
    }
  }
  
  const setOption = (option, notMerge = false) => {
    if (chartId.value) {
      chartManager.setOption(chartId.value, option, notMerge)
    }
  }
  
  const dispose = () => {
    if (chartId.value) {
      chartManager.dispose(chartId.value)
      chartInstance.value = null
      chartId.value = null
    }
  }
  
  const resize = () => {
    if (chartInstance.value) {
      chartInstance.value.resize()
    }
  }
  
  onMounted(() => {
    initChart()
  })
  
  onUnmounted(() => {
    dispose()
  })
  
  return {
    chartInstance,
    chartId,
    setOption,
    dispose,
    resize
  }
}

export default chartManager
