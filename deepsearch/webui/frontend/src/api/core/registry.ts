/**
 * API 接口注册表
 * 管理和验证所有 API 端点
 */

import { 
  ApiEndpoint, 
  ApiCategory, 
  HttpMethod,
  CacheConfig,
  RateLimitConfig 
} from './types'

/**
 * API 注册表类
 */
export class ApiRegistry {
  private static instance: ApiRegistry
  private endpoints: Map<string, ApiEndpoint> = new Map()
  private categoryEndpoints: Map<ApiCategory, Set<string>> = new Map()
  
  private constructor() {
    this.registerDefaultEndpoints()
  }
  
  /**
   * 获取单例实例
   */
  public static getInstance(): ApiRegistry {
    if (!ApiRegistry.instance) {
      ApiRegistry.instance = new ApiRegistry()
    }
    return ApiRegistry.instance
  }
  
  /**
   * 注册默认端点
   */
  private registerDefaultEndpoints(): void {
    // ========== 系统管理端点 ==========
    this.register({
      id: 'system.status',
      path: '/system/status',
      method: HttpMethod.GET,
      category: ApiCategory.SYSTEM,
      name: '系统状态',
      description: '获取系统运行状态',
      cache: {
        enabled: true,
        duration: 5000
      }
    })
    
    this.register({
      id: 'system.health',
      path: '/health',
      method: HttpMethod.GET,
      category: ApiCategory.SYSTEM,
      name: '健康检查',
      description: '系统健康检查',
      cache: {
        enabled: true,
        duration: 10000
      }
    })
    
    this.register({
      id: 'system.config',
      path: '/system/config',
      method: HttpMethod.GET,
      category: ApiCategory.SYSTEM,
      name: '系统配置',
      description: '获取系统配置信息',
      requireAuth: true
    })
    
    // ========== 数据库端点 ==========
    this.register({
      id: 'database.status',
      path: '/database/status',
      method: HttpMethod.GET,
      category: ApiCategory.DATABASE,
      name: '数据库状态',
      description: '获取数据库连接状态',
      cache: {
        enabled: true,
        duration: 10000
      }
    })
    
    this.register({
      id: 'database.connections',
      path: '/database/connections',
      method: HttpMethod.GET,
      category: ApiCategory.DATABASE,
      name: '数据库连接列表',
      description: '获取所有数据库连接',
      requireAuth: true
    })
    
    this.register({
      id: 'database.query',
      path: '/database/query',
      method: HttpMethod.POST,
      category: ApiCategory.DATABASE,
      name: '执行查询',
      description: '执行数据库查询',
      requireAuth: true,
      permissions: ['database.query'],
      rateLimit: {
        maxRequests: 10,
        windowMs: 60000,
        message: '查询过于频繁'
      }
    })
    
    // ========== 市场数据端点 ==========
    this.register({
      id: 'market.overview',
      path: '/market/overview',
      method: HttpMethod.GET,
      category: ApiCategory.MARKET,
      name: '市场概览',
      description: '获取市场概览数据',
      cache: {
        enabled: true,
        duration: 30000
      }
    })
    
    this.register({
      id: 'market.kline',
      path: '/market/kline',
      method: HttpMethod.GET,
      category: ApiCategory.MARKET,
      name: 'K线数据',
      description: '获取股票K线数据',
      cache: {
        enabled: true,
        duration: 60000
      }
    })
    
    this.register({
      id: 'market.realtime',
      path: '/market/realtime',
      method: HttpMethod.GET,
      category: ApiCategory.MARKET,
      name: '实时行情',
      description: '获取实时行情数据',
      cache: {
        enabled: true,
        duration: 1000
      }
    })
    
    // ========== 数据源管理端点 ==========
    this.register({
      id: 'datasource.list',
      path: '/data-source/list',
      method: HttpMethod.GET,
      category: ApiCategory.DATA_SOURCE,
      name: '数据源列表',
      description: '获取所有数据源',
      cache: {
        enabled: true,
        duration: 30000
      }
    })
    
    this.register({
      id: 'datasource.status',
      path: '/data-source/status',
      method: HttpMethod.GET,
      category: ApiCategory.DATA_SOURCE,
      name: '数据源状态',
      description: '获取数据源状态',
      cache: {
        enabled: true,
        duration: 5000
      }
    })
    
    this.register({
      id: 'datasource.test',
      path: '/data-source/test',
      method: HttpMethod.POST,
      category: ApiCategory.DATA_SOURCE,
      name: '测试数据源',
      description: '测试数据源连接',
      requireAuth: true
    })
    
    // ========== 监控端点 ==========
    this.register({
      id: 'monitor.metrics',
      path: '/monitor/metrics',
      method: HttpMethod.GET,
      category: ApiCategory.MONITOR,
      name: '监控指标',
      description: '获取系统监控指标',
      cache: {
        enabled: true,
        duration: 5000
      }
    })
    
    this.register({
      id: 'monitor.logs',
      path: '/monitor/logs',
      method: HttpMethod.GET,
      category: ApiCategory.MONITOR,
      name: '系统日志',
      description: '获取系统日志',
      requireAuth: true,
      rateLimit: {
        maxRequests: 20,
        windowMs: 60000
      }
    })
  }
  
  /**
   * 注册端点
   */
  public register(endpoint: ApiEndpoint): void {
    // 验证端点
    this.validateEndpoint(endpoint)
    
    // 添加到注册表
    this.endpoints.set(endpoint.id, endpoint)
    
    // 添加到分类索引
    if (!this.categoryEndpoints.has(endpoint.category)) {
      this.categoryEndpoints.set(endpoint.category, new Set())
    }
    this.categoryEndpoints.get(endpoint.category)!.add(endpoint.id)
    
    console.log(`📝 Registered API endpoint: ${endpoint.id}`)
  }
  
  /**
   * 验证端点
   */
  private validateEndpoint(endpoint: ApiEndpoint): void {
    // 检查 ID 唯一性
    if (this.endpoints.has(endpoint.id)) {
      throw new Error(`Endpoint with ID '${endpoint.id}' already registered`)
    }
    
    // 检查路径格式
    if (!endpoint.path.startsWith('/')) {
      throw new Error(`Endpoint path must start with '/', got: ${endpoint.path}`)
    }
    
    // 检查缓存配置
    if (endpoint.cache && endpoint.method !== HttpMethod.GET) {
      console.warn(`Cache is only effective for GET requests, endpoint: ${endpoint.id}`)
    }
    
    // 检查限流配置
    if (endpoint.rateLimit && endpoint.rateLimit.maxRequests <= 0) {
      throw new Error(`Invalid rate limit configuration for endpoint: ${endpoint.id}`)
    }
  }
  
  /**
   * 获取端点
   */
  public getEndpoint(id: string): ApiEndpoint | undefined {
    return this.endpoints.get(id)
  }
  
  /**
   * 根据路径和方法获取端点
   */
  public getEndpointByPath(path: string, method: HttpMethod): ApiEndpoint | undefined {
    for (const endpoint of this.endpoints.values()) {
      if (endpoint.path === path && endpoint.method === method) {
        return endpoint
      }
    }
    return undefined
  }
  
  /**
   * 获取所有端点
   */
  public getAllEndpoints(): ApiEndpoint[] {
    return Array.from(this.endpoints.values())
  }
  
  /**
   * 获取分类下的所有端点
   */
  public getEndpointsByCategory(category: ApiCategory): ApiEndpoint[] {
    const ids = this.categoryEndpoints.get(category)
    if (!ids) return []
    
    return Array.from(ids)
      .map(id => this.endpoints.get(id))
      .filter(Boolean) as ApiEndpoint[]
  }
  
  /**
   * 检查端点是否需要认证
   */
  public requiresAuth(id: string): boolean {
    const endpoint = this.endpoints.get(id)
    return endpoint?.requireAuth || false
  }
  
  /**
   * 检查端点权限
   */
  public checkPermissions(id: string, userPermissions: string[]): boolean {
    const endpoint = this.endpoints.get(id)
    if (!endpoint || !endpoint.permissions) return true
    
    return endpoint.permissions.every(permission => 
      userPermissions.includes(permission)
    )
  }
  
  /**
   * 获取端点缓存配置
   */
  public getCacheConfig(id: string): CacheConfig | undefined {
    const endpoint = this.endpoints.get(id)
    return endpoint?.cache
  }
  
  /**
   * 获取端点限流配置
   */
  public getRateLimitConfig(id: string): RateLimitConfig | undefined {
    const endpoint = this.endpoints.get(id)
    return endpoint?.rateLimit
  }
  
  /**
   * 批量注册端点
   */
  public registerBatch(endpoints: ApiEndpoint[]): void {
    for (const endpoint of endpoints) {
      this.register(endpoint)
    }
  }
  
  /**
   * 注销端点
   */
  public unregister(id: string): void {
    const endpoint = this.endpoints.get(id)
    if (endpoint) {
      this.endpoints.delete(id)
      this.categoryEndpoints.get(endpoint.category)?.delete(id)
      console.log(`📝 Unregistered API endpoint: ${id}`)
    }
  }
  
  /**
   * 导出端点文档
   */
  public exportDocumentation(): string {
    const docs: string[] = ['# API Endpoints Documentation\n']
    
    // 按分类组织文档
    for (const category of Object.values(ApiCategory)) {
      const endpoints = this.getEndpointsByCategory(category)
      if (endpoints.length === 0) continue
      
      docs.push(`\n## ${this.getCategoryName(category)}\n`)
      
      for (const endpoint of endpoints) {
        docs.push(`### ${endpoint.name}`)
        docs.push(`- **ID**: ${endpoint.id}`)
        docs.push(`- **Path**: ${endpoint.method} ${endpoint.path}`)
        docs.push(`- **Description**: ${endpoint.description}`)
        
        if (endpoint.requireAuth) {
          docs.push(`- **Authentication**: Required`)
        }
        
        if (endpoint.permissions) {
          docs.push(`- **Permissions**: ${endpoint.permissions.join(', ')}`)
        }
        
        if (endpoint.cache) {
          docs.push(`- **Cache**: ${endpoint.cache.duration}ms`)
        }
        
        if (endpoint.rateLimit) {
          docs.push(`- **Rate Limit**: ${endpoint.rateLimit.maxRequests} requests per ${endpoint.rateLimit.windowMs}ms`)
        }
        
        if (endpoint.deprecated) {
          docs.push(`- **⚠️ DEPRECATED**`)
        }
        
        docs.push('')
      }
    }
    
    return docs.join('\n')
  }
  
  /**
   * 获取分类名称
   */
  private getCategoryName(category: ApiCategory): string {
    const names: Record<ApiCategory, string> = {
      [ApiCategory.SYSTEM]: '系统管理',
      [ApiCategory.DATABASE]: '数据库操作',
      [ApiCategory.MARKET]: '市场数据',
      [ApiCategory.TRADING]: '交易相关',
      [ApiCategory.MONITOR]: '监控相关',
      [ApiCategory.DATA_SOURCE]: '数据源管理'
    }
    return names[category] || category
  }
  
  /**
   * 获取统计信息
   */
  public getStatistics() {
    const stats: any = {
      total: this.endpoints.size,
      byCategory: {},
      byMethod: {},
      requireAuth: 0,
      cached: 0,
      rateLimited: 0,
      deprecated: 0
    }
    
    for (const endpoint of this.endpoints.values()) {
      // 按分类统计
      stats.byCategory[endpoint.category] = (stats.byCategory[endpoint.category] || 0) + 1
      
      // 按方法统计
      stats.byMethod[endpoint.method] = (stats.byMethod[endpoint.method] || 0) + 1
      
      // 其他统计
      if (endpoint.requireAuth) stats.requireAuth++
      if (endpoint.cache) stats.cached++
      if (endpoint.rateLimit) stats.rateLimited++
      if (endpoint.deprecated) stats.deprecated++
    }
    
    return stats
  }
}

// 导出单例实例
export const apiRegistry = ApiRegistry.getInstance()