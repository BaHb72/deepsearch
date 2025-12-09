/**
 * API 监控系统
 * 实时监控 API 性能和健康状态
 */

import {ApiCategory, HealthIssue, HealthRule, HttpMethod, RequestLog,} from './types'
import {ApiLogger} from './logger'

type RequestSample = {
    timestamp: number
    duration: number
    success: boolean
}

interface MonitorSnapshot {
    global: PerformanceMetrics
    categories: Record<string, PerformanceMetrics>
    endpoints: Record<string, PerformanceMetrics>
    health: {
        issues: HealthIssue[]
        status: 'healthy' | 'degraded' | 'unhealthy'
    }
}

// 性能指标
interface PerformanceMetrics {
  requestCount: number
  successCount: number
  errorCount: number
  avgDuration: number
  p50Duration: number
  p95Duration: number
  p99Duration: number
  errorRate: number
  throughput: number // 请求/秒
}

// 分类指标
// 端点指标
/**
 * API 监控器
 */
export class ApiMonitor {
  private static instance: ApiMonitor
    private static readonly HISTORY_LIMIT = 200
    private static readonly HISTORY_RETENTION_MS = 5 * 60 * 1000
  private logger: ApiLogger
  private metrics: Map<string, PerformanceMetrics> = new Map()
    private requestHistory: Map<string, RequestSample[]> = new Map()
  private healthRules: HealthRule[] = []
  private healthIssues: HealthIssue[] = []
    private monitorInterval: ReturnType<typeof setInterval> | null = null
  private readonly checkInterval: number = 10000 // 10秒检查一次
    private subscribers: Set<(metrics: MonitorSnapshot) => void> = new Set()
  
  private constructor() {
    this.logger = ApiLogger.getInstance()
    this.setupDefaultRules()
  }
  
  /**
   * 获取单例实例
   */
  public static getInstance(): ApiMonitor {
    if (!ApiMonitor.instance) {
      ApiMonitor.instance = new ApiMonitor()
    }
    return ApiMonitor.instance
  }
  
  /**
   * 设置默认健康规则
   */
  private setupDefaultRules(): void {
    this.healthRules = [
      {
        name: '高错误率',
        description: '错误率超过10%',
        threshold: 0.1,
        action: 'alert',
        check: (logs: RequestLog[]) => {
          const errorRate = this.calculateErrorRate(logs)
          return errorRate > 0.1
        }
      },
      {
        name: '响应缓慢',
        description: '平均响应时间超过3秒',
        threshold: 3000,
        action: 'alert',
        check: (logs: RequestLog[]) => {
          const avgDuration = this.calculateAvgDuration(logs)
          return avgDuration > 3000
        }
      },
      {
        name: '连续失败',
        description: '连续5个请求失败',
        threshold: 5,
        action: 'recover',
        check: (logs: RequestLog[]) => {
          let consecutiveErrors = 0
          for (const log of logs.slice(-10)) {
            if (log.error) {
              consecutiveErrors++
              if (consecutiveErrors >= 5) return true
            } else {
              consecutiveErrors = 0
            }
          }
          return false
        }
      },
      {
        name: '请求激增',
        description: '请求量突然增加50%',
        threshold: 1.5,
        action: 'throttle',
        check: (logs: RequestLog[]) => {
          const now = Date.now()
          const recent = logs.filter(l => now - l.timestamp < 60000).length
          const previous = logs.filter(l => 
            l.timestamp >= now - 120000 && 
            l.timestamp < now - 60000
          ).length
          
          return previous > 0 && recent / previous > 1.5
        }
      }
    ]
  }
  
  /**
   * 启动监控
   */
  public start(): void {
    if (this.monitorInterval) return
    
    this.monitorInterval = setInterval(() => {
      this.performHealthCheck()
      this.updateMetrics()
    }, this.checkInterval)

      console.log('[API Monitor] started')
  }
  
  /**
   * 停止监控
   */
  public stop(): void {
    if (this.monitorInterval) {
      clearInterval(this.monitorInterval)
      this.monitorInterval = null
        console.log('[API Monitor] stopped')
    }
  }
  
  /**
   * 执行健康检查
   */
  private performHealthCheck(): void {
    const logs = this.logger.getAllLogs()
    const now = Date.now()
    const recentLogs = logs.filter(log => now - log.timestamp < 300000) // 最近5分钟
    
    // 清除旧的问题
    this.healthIssues = this.healthIssues.filter(
      issue => now - issue.timestamp < 3600000 // 保留1小时内的问题
    )
    
    // 检查每个规则
    for (const rule of this.healthRules) {
      if (rule.check(recentLogs)) {
        const issue: HealthIssue = {
          rule,
          timestamp: now,
          severity: this.determineSeverity(rule),
          message: `${rule.name}: ${rule.description}`,
          affectedEndpoints: this.findAffectedEndpoints(recentLogs, rule),
          suggestedAction: this.getSuggestedAction(rule)
        }
        
        // 检查是否是新问题
        const existingIssue = this.healthIssues.find(
          i => i.rule.name === rule.name && now - i.timestamp < 60000
        )
        
        if (!existingIssue) {
          this.healthIssues.push(issue)
          this.handleHealthIssue(issue)
        }
      }
    }
  }
  
  /**
   * 记录请求
   */
  public recordRequest({
                           duration,
                           category,
                           success,
                           method,
                           url,
                       }: {
      requestId: string
      duration: number
      category: ApiCategory
      success: boolean
      method: HttpMethod
      url?: string
  }): void {
      const sample: RequestSample = {timestamp: Date.now(), duration, success}

      this.appendSample('global', sample)
      this.appendSample(`category:${category}`, sample)

      if (url) {
          const endpointKey = `endpoint:${method}:${url}`
          this.appendSample(endpointKey, sample)
      }

      this.notifySubscribers()
  }

    public getMetrics(): MonitorSnapshot {
        const snapshot: MonitorSnapshot = {
            global: this.metrics.get('global') ?? this.createEmptyMetrics(),
            categories: {},
            endpoints: {},
            health: {
                issues: [...this.healthIssues],
                status: this.getHealthStatus(),
            },
        }

        for (const [key, value] of this.metrics.entries()) {
            if (key.startsWith('category:')) {
                const category = key.replace('category:', '')
                snapshot.categories[category] = value
            } else if (key.startsWith('endpoint:')) {
                const endpoint = key.replace('endpoint:', '')
                snapshot.endpoints[endpoint] = value
            }
        }

        return snapshot
  }

  private calculateErrorRate(logs: RequestLog[]): number {
    if (logs.length === 0) return 0
    const errors = logs.filter(log => log.error).length
    return errors / logs.length
  }
  
  /**
   * 计算百分位数
   */
  /**
   * 确定严重程度
   */
  private determineSeverity(rule: HealthRule): 'low' | 'medium' | 'high' | 'critical' {
    switch (rule.action) {
      case 'recover':
        return 'critical'
      case 'throttle':
        return 'high'
      case 'alert':
        return rule.threshold && rule.threshold > 0.2 ? 'high' : 'medium'
      default:
        return 'low'
    }
  }
  
  /**
   * 查找受影响的端点
   */
  private findAffectedEndpoints(logs: RequestLog[], rule: HealthRule): string[] {
    const affectedLogs = logs.filter(log => {
      if (rule.name === '高错误率' || rule.name === '连续失败') {
        return log.error !== undefined
      }
      if (rule.name === '响应缓慢') {
        return log.duration && log.duration > (rule.threshold || 3000)
      }
      return true
    })
    
    const endpoints = new Set(affectedLogs.map(log => `${log.method} ${log.url}`))
    return Array.from(endpoints)
  }
  
  /**
   * 获取建议操作
   */
  private getSuggestedAction(rule: HealthRule): string {
    const suggestions: Record<string, string> = {
      '高错误率': '检查后端服务状态，查看错误日志',
      '响应缓慢': '检查数据库性能，优化慢查询',
      '连续失败': '检查网络连接，重启服务',
      '请求激增': '考虑启用限流，增加服务器资源'
    }
    return suggestions[rule.name] || '请检查系统状态'
  }

    /**
     * 订阅指标更新
     */
    public subscribe(callback: (metrics: MonitorSnapshot) => void): () => void {
        this.subscribers.add(callback)
        return () => this.subscribers.delete(callback)
    }

    /**
     * 更新指标
     */
    private updateMetrics(): void {
        const now = Date.now()
        let changed = false
        const keysToDelete: string[] = []

        for (const [key, history] of this.requestHistory.entries()) {
            const normalized = this.normalizeHistory(history, now)
            if (normalized.length === 0) {
                keysToDelete.push(key)
                if (this.metrics.delete(key)) {
                    changed = true
                }
                continue
            }

            if (normalized.length !== history.length) {
                this.requestHistory.set(key, normalized)
            }

            const previousMetrics = this.metrics.get(key)
            const metrics = this.computeMetricsFromHistory(normalized)
            this.metrics.set(key, metrics)
            if (!previousMetrics || JSON.stringify(previousMetrics) !== JSON.stringify(metrics)) {
                changed = true
            }
        }

        if (keysToDelete.length > 0) {
            for (const key of keysToDelete) {
                this.requestHistory.delete(key)
            }
        }

        if (changed) {
            this.notifySubscribers()
        }
    }

    /**
     * 计算错误率
     */
    private calculateAvgDuration(logs: RequestLog[]): number {
        const durations = logs
            .map((log) => log.duration)
            .filter((value): value is number => typeof value === 'number')

        if (durations.length === 0) {
            return 0
        }

        return durations.reduce((sum, value) => sum + value, 0) / durations.length
    }

  /**
   * 处理健康问题
   */
  private handleHealthIssue(issue: HealthIssue): void {
      console.warn(`[API Monitor] Health issue detected: ${issue.message}`)
      console.warn(`  Severity: ${issue.severity}`)
      if (issue.suggestedAction) {
          console.warn(`  Suggested Action: ${issue.suggestedAction}`)
      }

    if (issue.affectedEndpoints && issue.affectedEndpoints.length > 0) {
        console.warn('  Affected Endpoints:', issue.affectedEndpoints)
    }

    switch (issue.severity) {
      case 'critical':
          console.error('[API Monitor] Critical issue requires immediate attention.')
        break
      case 'high':
          console.warn('[API Monitor] High severity issue recorded.')
        break
      case 'medium':
          console.info('[API Monitor] Medium severity issue logged.')
        break
      default:
          console.debug('[API Monitor] Issue captured for monitoring.')
        break
    }
  }

    private appendSample(key: string, sample: RequestSample) {
        const history = this.requestHistory.get(key) ?? []
        history.push(sample)
        const normalized = this.normalizeHistory(history, sample.timestamp)
        this.requestHistory.set(key, normalized)
        this.metrics.set(key, this.computeMetricsFromHistory(normalized))
    }

    private normalizeHistory(history: RequestSample[], currentTimestamp: number): RequestSample[] {
        const cutoff = currentTimestamp - ApiMonitor.HISTORY_RETENTION_MS
        const recent = history.filter((item) => item.timestamp >= cutoff)
        if (recent.length > ApiMonitor.HISTORY_LIMIT) {
            return recent.slice(-ApiMonitor.HISTORY_LIMIT)
        }
        return recent
    }

    // ========== 公共方法 ==========

    private computeMetricsFromHistory(history: RequestSample[]): PerformanceMetrics {
        const requestCount = history.length
        const successCount = history.filter((item) => item.success).length
        const errorCount = requestCount - successCount

        const durations = history.map((item) => item.duration).sort((a, b) => a - b)
        const avgDuration =
            requestCount > 0 ? durations.reduce((acc, value) => acc + value, 0) / requestCount : 0

        const percentile = (p: number) => {
            if (durations.length === 0) {
                return 0
            }
            const index = Math.min(
                durations.length - 1,
                Math.max(0, Math.floor((durations.length - 1) * p))
            )
            return durations[index]
        }

        const firstTimestamp = history[0]?.timestamp ?? Date.now()
        const lastTimestamp = history[history.length - 1]?.timestamp ?? firstTimestamp
        const timeSpanSeconds =
            requestCount > 1 ? Math.max(1, (lastTimestamp - firstTimestamp) / 1000) : 60
        const throughput = requestCount / timeSpanSeconds

        return {
            requestCount,
            successCount,
            errorCount,
            avgDuration,
            p50Duration: percentile(0.5),
            p95Duration: percentile(0.95),
            p99Duration: percentile(0.99),
            errorRate: requestCount > 0 ? errorCount / requestCount : 0,
            throughput,
        }
  }

    /**
   * 通知订阅者
   */
  private notifySubscribers(): void {
    const metrics = this.getMetrics()
    this.subscribers.forEach(callback => {
      try {
        callback(metrics)
      } catch (error) {
        console.error('Monitor subscriber error:', error)
      }
    })
  }
  /**
   * 获取健康状态
   */
  public getHealthStatus(): 'healthy' | 'degraded' | 'unhealthy' {
    if (this.healthIssues.length === 0) return 'healthy'
    
    const hasCritical = this.healthIssues.some(i => i.severity === 'critical')
    if (hasCritical) return 'unhealthy'
    
    const hasHigh = this.healthIssues.some(i => i.severity === 'high')
    if (hasHigh) return 'degraded'
    
    return 'degraded'
  }
  
  /**
   * 获取健康问题
   */
  public getHealthIssues(): HealthIssue[] {
    return [...this.healthIssues]
  }
  
  /**
   * 添加健康规则
   */
  public addHealthRule(rule: HealthRule): void {
    this.healthRules.push(rule)
  }
  
  /**
   * 移除健康规则
   */
  public removeHealthRule(name: string): void {
    this.healthRules = this.healthRules.filter(r => r.name !== name)
  }
  
  /**
   * 获取所有指标
   */
  private createEmptyMetrics(): PerformanceMetrics {
      return {
          requestCount: 0,
          successCount: 0,
          errorCount: 0,
          avgDuration: 0,
          p50Duration: 0,
          p95Duration: 0,
          p99Duration: 0,
          errorRate: 0,
          throughput: 0,
      }
  }
  
  /**
   * 重置指标
   */
  public reset(): void {
    this.metrics.clear()
    this.healthIssues = []
  }
}
