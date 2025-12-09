import logger from '@/utils/logger'
import {getCLS, getFCP, getFID, getLCP, getTTFB, Metric} from 'web-vitals'

const performanceLogger = logger.child('utils:performance')

interface PerformanceMemoryInfo {
  usedJSHeapSize: number
  totalJSHeapSize: number
  jsHeapSizeLimit: number
}

interface PerformanceWithMemory extends Performance {
  memory?: PerformanceMemoryInfo
}

interface PerformanceData {
  // Core Web Vitals
  cls?: number // Cumulative Layout Shift
  fcp?: number // First Contentful Paint
  fid?: number // First Input Delay
  lcp?: number // Largest Contentful Paint
  ttfb?: number // Time to First Byte
  
  // Custom metrics
  customMetrics: Record<string, number>
  
  // Resource timing
  resources: ResourceTiming[]
  
  // Navigation timing
  navigation?: NavigationTiming
  
  // User timing
  marks: PerformanceMark[]
  measures: PerformanceMeasure[]
}

interface ResourceTiming {
  name: string
  type: string
  duration: number
  size?: number
  startTime: number
}

interface NavigationTiming {
  domContentLoaded: number
  loadComplete: number
  domInteractive: number
  redirectTime: number
  dnsTime: number
  tcpTime: number
  requestTime: number
  responseTime: number
}

class PerformanceMonitor {
  private data: PerformanceData = {
    customMetrics: {},
    resources: [],
    marks: [],
    measures: [],
  }
  
  private observers: Map<string, PerformanceObserver> = new Map()
  private reportCallback?: (data: PerformanceData) => void
  private reportThreshold = 10 // 收集10个指标后上报
  private metricsCount = 0
  private debug = false

  constructor(options?: {
    reportCallback?: (data: PerformanceData) => void
    reportThreshold?: number
    debug?: boolean
  }) {
    this.reportCallback = options?.reportCallback
    this.reportThreshold = options?.reportThreshold || 10
    this.debug = options?.debug || false
    
    this.init()
  }

  private init() {
    // 收集 Core Web Vitals
    this.collectWebVitals()
    
    // 收集资源加载性能
    this.observeResources()
    
    // 收集导航性能
    this.collectNavigationTiming()
    
    // 监听用户自定义性能标记
    this.observeUserTiming()
    
    // 监听长任务
    this.observeLongTasks()
    
    // 监听内存使用
    this.monitorMemory()
  }

  // 收集 Web Vitals
  private collectWebVitals() {
    getCLS((metric) => this.handleWebVital('cls', metric))
    getFCP((metric) => this.handleWebVital('fcp', metric))
    getFID((metric) => this.handleWebVital('fid', metric))
    getLCP((metric) => this.handleWebVital('lcp', metric))
    getTTFB((metric) => this.handleWebVital('ttfb', metric))
  }

  private handleWebVital(name: string, metric: Metric) {
    this.data[name as keyof PerformanceData] = metric.value
    this.log(`Web Vital - ${name}:`, metric.value)
    this.checkAndReport()
  }

  // 观察资源加载
  private observeResources() {
    if ('PerformanceObserver' in window) {
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          const resourceEntry = entry as PerformanceResourceTiming
          
          this.data.resources.push({
            name: resourceEntry.name,
            type: resourceEntry.initiatorType,
            duration: resourceEntry.duration,
            size: resourceEntry.transferSize,
            startTime: resourceEntry.startTime,
          })
          
          // 只保留最近100条资源记录
          if (this.data.resources.length > 100) {
            this.data.resources.shift()
          }
        }
      })
      
      observer.observe({ entryTypes: ['resource'] })
      this.observers.set('resource', observer)
    }
  }

  // 收集导航时间
  private collectNavigationTiming() {
    if (window.performance && window.performance.timing) {
      const timing = window.performance.timing
      const navigationStart = timing.navigationStart
      
      this.data.navigation = {
        domContentLoaded: timing.domContentLoadedEventEnd - navigationStart,
        loadComplete: timing.loadEventEnd - navigationStart,
        domInteractive: timing.domInteractive - navigationStart,
        redirectTime: timing.redirectEnd - timing.redirectStart,
        dnsTime: timing.domainLookupEnd - timing.domainLookupStart,
        tcpTime: timing.connectEnd - timing.connectStart,
        requestTime: timing.responseStart - timing.requestStart,
        responseTime: timing.responseEnd - timing.responseStart,
      }
      
      this.log('Navigation Timing:', this.data.navigation)
    }
  }

  // 观察用户自定义时间标记
  private observeUserTiming() {
    if ('PerformanceObserver' in window) {
      const markObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          this.data.marks.push(entry as PerformanceMark)
        }
      })
      
      const measureObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          this.data.measures.push(entry as PerformanceMeasure)
        }
      })
      
      markObserver.observe({ entryTypes: ['mark'] })
      measureObserver.observe({ entryTypes: ['measure'] })
      
      this.observers.set('mark', markObserver)
      this.observers.set('measure', measureObserver)
    }
  }

  // 监听长任务
  private observeLongTasks() {
    if ('PerformanceObserver' in window && 'PerformanceLongTaskTiming' in window) {
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          this.log('Long Task detected:', {
            duration: entry.duration,
            startTime: entry.startTime,
            name: entry.name,
          })
          
          // 记录长任务
          this.setCustomMetric('longTaskCount', 
            (this.data.customMetrics.longTaskCount || 0) + 1
          )
          this.setCustomMetric('totalLongTaskTime', 
            (this.data.customMetrics.totalLongTaskTime || 0) + entry.duration
          )
        }
      })
      
      try {
        observer.observe({ entryTypes: ['longtask'] })
        this.observers.set('longtask', observer)
      } catch (error) {
        this.log('Long task monitoring not supported', error)
      }
    }
  }

  // 监控内存使用
  private monitorMemory() {
    if ('memory' in performance) {
      setInterval(() => {
        const memory = (performance as PerformanceWithMemory).memory
        if (!memory) {
          this.log('Performance memory info unavailable')
          return
        }
        this.setCustomMetric('jsHeapUsed', memory.usedJSHeapSize)
        this.setCustomMetric('jsHeapTotal', memory.totalJSHeapSize)
        this.setCustomMetric('jsHeapLimit', memory.jsHeapSizeLimit)
      }, 10000) // 每 10 秒采样一次
    }
  }

  // 标记时间点
  mark(name: string) {
    performance.mark(name)
    this.log(`Mark: ${name}`)
  }

  // 测量两个标记之间的时间
  measure(name: string, startMark: string, endMark?: string) {
    try {
      if (endMark) {
        performance.measure(name, startMark, endMark)
      } else {
        performance.measure(name, startMark)
      }
      
      const measures = performance.getEntriesByName(name, 'measure')
      const measure = measures[measures.length - 1]
      
      this.log(`Measure ${name}:`, measure.duration)
      this.setCustomMetric(name, measure.duration)
      
      return measure.duration
    } catch (error) {
      this.log(`Failed to measure ${name}:`, error)
      return null
    }
  }

  // 设置自定义指标
  setCustomMetric(name: string, value: number) {
    this.data.customMetrics[name] = value
    this.checkAndReport()
  }

  // 获取性能数据
  getData(): PerformanceData {
    return { ...this.data }
  }

  // 手动上报
  report() {
    if (this.reportCallback) {
      this.reportCallback(this.getData())
      this.log('Performance data reported:', this.data)
    }
  }

  // 检查并自动上报
  private checkAndReport() {
    this.metricsCount++
    if (this.metricsCount >= this.reportThreshold) {
      this.report()
      this.metricsCount = 0
    }
  }

  // 清理
  destroy() {
    this.observers.forEach(observer => observer.disconnect())
    this.observers.clear()
  }

  // 日志
  private log(...args: unknown[]) {
    if (this.debug) {
      performanceLogger.info('[Performance]', ...args)
    }
  }
}

// 创建默认实例
let defaultMonitor: PerformanceMonitor | null = null

export const initPerformanceMonitor = (options?: Parameters<typeof PerformanceMonitor>[0]) => {
  if (!defaultMonitor) {
    defaultMonitor = new PerformanceMonitor(options)
  }
  return defaultMonitor
}

export const getPerformanceMonitor = () => {
  if (!defaultMonitor) {
    defaultMonitor = new PerformanceMonitor()
  }
  return defaultMonitor
}

// React Hook
export const usePerformance = () => {
  const monitor = React.useMemo(() => getPerformanceMonitor(), [])

  return React.useMemo(() => ({
    mark: (name: string) => monitor.mark(name),
    measure: (name: string, startMark: string, endMark?: string) =>
      monitor.measure(name, startMark, endMark),
    setMetric: (name: string, value: number) =>
      monitor.setCustomMetric(name, value),
    getData: () => monitor.getData(),
    report: () => monitor.report(),
  }), [monitor])
}

// 组件性能追踪 HOC
export const withPerformanceTracking = <P extends object>(
  Component: React.ComponentType<P>,
  componentName: string
) => {
  const WrappedComponent: React.FC<P> = (props: P) => {
    const { mark, measure } = usePerformance()

    React.useEffect(() => {
      mark(`${componentName}-mount-start`)

      return () => {
        measure(
          `${componentName}-mounted`,
          `${componentName}-mount-start`
        )
      }
    }, [mark, measure])

    return React.createElement(Component, props)
  }

  WrappedComponent.displayName = `withPerformanceTracking(${componentName})`

  return WrappedComponent
}

export default PerformanceMonitor
