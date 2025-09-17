/**
 * API 监控系统
 * 实时监控 API 性能和健康状态
 */

import { 
  ApiCategory, 
  HealthRule, 
  HealthIssue,
  RequestLog 
} from './types'
import { ApiLogger } from './logger'

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
interface CategoryMetrics extends PerformanceMetrics {
  category: ApiCategory
}

// 端点指标
interface EndpointMetrics extends PerformanceMetrics {
  endpoint: string
  method: string
}

/**
 * API 监控器
 */
export class ApiMonitor {
  private static instance: ApiMonitor
  private logger: ApiLogger
  private metrics: Map<string, PerformanceMetrics> = new Map()
  private healthRules: HealthRule[] = []
  private healthIssues: HealthIssue[] = []
  private monitorInterval: NodeJS.Timeout | null = null
  private readonly checkInterval: number = 10000 // 10秒检查一次
  private subscribers: Set<(metrics: any) => void> = new Set()
  
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
    
    console.log('📊 API Monitor started')
  }
  
  /**
   * 停止监控
   */
  public stop(): void {
    if (this.monitorInterval) {
      clearInterval(this.monitorInterval)
      this.monitorInterval = null
      console.log('📊 API Monitor stopped')
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
   * 更新指标
   */
  private updateMetrics(): void {
    const logs = this.logger.getAllLogs()
    const now = Date.now()
    const recentLogs = logs.filter(log => now - log.timestamp < 60000) // 最近1分钟
    
    // 全局指标
    const globalMetrics = this.calculateMetrics(recentLogs)
    this.metrics.set('global', globalMetrics)
    
    // 分类指标
    const categories = Object.values(ApiCategory)
    for (const category of categories) {
      const categoryLogs = recentLogs.filter(log => log.category === category)
      if (categoryLogs.length > 0) {
        const metrics = this.calculateMetrics(categoryLogs)
        this.metrics.set(`category:${category}`, metrics)
      }
    }
    
    // 端点指标
    const endpoints = new Set(recentLogs.map(log => `${log.method}:${log.url}`))
    for (const endpoint of endpoints) {
      const [method, url] = endpoint.split(':')
      const endpointLogs = recentLogs.filter(
        log => log.method === method && log.url === url
      )
      if (endpointLogs.length > 0) {
        const metrics = this.calculateMetrics(endpointLogs)
        this.metrics.set(`endpoint:${endpoint}`, metrics)
      }
    }
    
    // 通知订阅者
    this.notifySubscribers()
  }
  
  /**
   * 计算指标
   */
  private calculateMetrics(logs: RequestLog[]): PerformanceMetrics {
    const requestCount = logs.length
    const successCount = logs.filter(log => !log.error).length
    const errorCount = logs.filter(log => log.error).length
    
    const durations = logs
      .filter(log => log.duration)
      .map(log => log.duration!)
      .sort((a, b) => a - b)
    
    const avgDuration = this.calculateAvgDuration(logs)
    const p50Duration = this.calculatePercentile(durations, 0.5)
    const p95Duration = this.calculatePercentile(durations, 0.95)
    const p99Duration = this.calculatePercentile(durations, 0.99)
    
    const errorRate = requestCount > 0 ? errorCount / requestCount : 0
    
    // 计算吞吐量（请求/秒）
    const timeSpan = logs.length > 1 
      ? (logs[logs.length - 1].timestamp - logs[0].timestamp) / 1000
      : 60
    const throughput = timeSpan > 0 ? requestCount / timeSpan : 0
    
    return {
      requestCount,
      successCount,
      errorCount,
      avgDuration,
      p50Duration,
      p95Duration,
      p99Duration,
      errorRate,
      throughput
    }
  }
  
  /**
   * 计算平均响应时间
   */
  private calculateAvgDuration(logs: RequestLog[]): number {
    const durations = logs.filter(log => log.duration).map(log => log.duration!)
    if (durations.length === 0) return 0
    return durations.reduce((a, b) => a + b, 0) / durations.length
  }
  
  /**
   * 计算错误率
   */
  private calculateErrorRate(logs: RequestLog[]): number {
    if (logs.length === 0) return 0
    const errors = logs.filter(log => log.error).length
    return errors / logs.length
  }
  
  /**
   * 计算百分位数
   */
  private calculatePercentile(sortedValues: number[], percentile: number): number {
    if (sortedValues.length === 0) return 0
    const index = Math.ceil(sortedValues.length * percentile) - 1
    return sortedValues[Math.max(0, index)]
  }
  
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
   * 处理健康问题
   */
  private handleHealthIssue(issue: HealthIssue): void {
    console.warn(`⚠️ Health Issue Detected: ${issue.message}`)
    console.warn(`   Severity: ${issue.severity}`)
    console.warn(`   Suggested Action: ${issue.suggestedAction}`)
    
    if (issue.affectedEndpoints && issue.affectedEndpoints.length > 0) {
      console.warn(`   Affected Endpoints:`, issue.affectedEndpoints)
    }
    
    // 根据严重程度采取行动
    switch (issue.severity) {
      case 'critical':
        // TODO: 发送紧急通知
        break
      case 'high':
        // TODO: 记录到错误追踪系统
        break
      case 'medium':
        // TODO: 记录到日志
        break
      default:
        // 仅控制台警告
        break
    }
  }
  
  /**
   * 记录请求
   */
  public recordRequest(params: {
    requestId: string
    duration: number
    category: ApiCategory
    success: boolean
  }): void {
    // 这个方法由 ApiClient 调用，用于实时更新指标
    // 当前实现依赖于日志系统，但可以扩展为独立的指标收集
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
  
  // ========== 公共方法 ==========
  
  /**
   * 获取所有指标
   */
  public getMetrics() {
    const metrics: any = {
      global: this.metrics.get('global'),
      categories: {},
      endpoints: {},
      health: {
        issues: this.healthIssues,
        status: this.getHealthStatus()
      }
    }
    
    // 整理分类指标
    for (const [key, value] of this.metrics.entries()) {
      if (key.startsWith('category:')) {
        const category = key.replace('category:', '')
        metrics.categories[category] = value
      } else if (key.startsWith('endpoint:')) {
        const endpoint = key.replace('endpoint:', '')
        metrics.endpoints[endpoint] = value
      }
    }
    
    return metrics
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
   * 订阅指标更新
   */
  public subscribe(callback: (metrics: any) => void): () => void {
    this.subscribers.add(callback)
    return () => this.subscribers.delete(callback)
  }
  
  /**
   * 重置指标
   */
  public reset(): void {
    this.metrics.clear()
    this.healthIssues = []
  }
}