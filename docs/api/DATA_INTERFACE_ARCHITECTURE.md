# 数据接口层架构文档

## 概述

本文档描述了 DeepSearch 项目的统一数据接口层架构，该架构旨在解决之前存在的 API 调用混乱、缺乏统一管理、难以排查故障等问题。

生成时间: 2025-09-13

## 架构目标

1. **统一性**: 所有 API 调用通过单一入口
2. **可追踪**: 每个请求都有完整日志
3. **可维护**: 接口变更有文档记录
4. **高可用**: 自动故障检测和恢复
5. **高性能**: 请求去重、缓存、批处理

## 核心模块

### 1. API 客户端 (`/src/api/core/client.ts`)

统一的 HTTP 客户端，提供：
- 单例模式，全局唯一实例
- 请求去重机制（100ms 时间窗口）
- 自动重试（可配置）
- 请求/响应拦截器
- 统一错误处理

```typescript
import { apiClient } from '@/api/core'

// 使用示例
const response = await apiClient.get('/system/status')
```

### 2. 日志系统 (`/src/api/core/logger.ts`)

完整的请求日志记录：
- 循环缓冲区（最多 1000 条）
- 多级日志级别
- 日志查询和过滤
- 导出功能（JSON/CSV）

```typescript
// 获取日志
const logs = apiClient.getLogs()

// 查询特定日志
const errorLogs = logger.queryLogs({
  hasError: true,
  startTime: Date.now() - 3600000
})
```

### 3. 监控系统 (`/src/api/core/monitor.ts`)

实时性能监控：
- 请求成功率
- 响应时间分布（p50/p95/p99）
- 错误率监控
- 吞吐量统计
- 健康规则检查

健康规则示例：
- 错误率超过 10%
- 平均响应时间超过 3 秒
- 连续 5 个请求失败
- 请求量突增 50%

### 4. 接口注册表 (`/src/api/core/registry.ts`)

所有 API 端点的中央注册表：
- 端点元数据管理
- 缓存配置
- 限流配置
- 权限验证
- 文档生成

```typescript
// 注册新端点
apiRegistry.register({
  id: 'custom.endpoint',
  path: '/custom/endpoint',
  method: HttpMethod.POST,
  category: ApiCategory.CUSTOM,
  cache: { enabled: true, duration: 5000 },
  rateLimit: { maxRequests: 10, windowMs: 60000 }
})
```

### 5. 错误处理 (`/src/api/core/error-handler.ts`)

标准化的错误处理：
- 错误码映射
- 用户友好的错误消息
- 自动重试判断
- 错误上报

### 6. 拦截器管理 (`/src/api/core/interceptors.ts`)

可扩展的拦截器系统：
- 认证拦截器（自动添加 token）
- 时间戳拦截器（防缓存）
- 追踪拦截器（请求追踪）

## 使用指南

### 基础使用

```typescript
import { api } from '@/api/core'

// 系统状态
const status = await api.system.getStatus()

// 市场数据
const marketData = await api.market.getOverview()

// 数据库查询
const result = await api.database.query('SELECT * FROM stocks')
```

### 高级功能

```typescript
import { apiClient, ApiCategory } from '@/api/core'

// 带配置的请求
const response = await apiClient.request({
  url: '/custom/endpoint',
  method: HttpMethod.POST,
  data: { key: 'value' },
  category: ApiCategory.CUSTOM,
  retries: 3,
  cache: true,
  cacheDuration: 10000,
  dedupe: true
})
```

### 故障排查

1. **查看实时日志**
   ```typescript
   // 在控制台
   window.__API__.getLogs()
   ```

2. **查看性能指标**
   ```typescript
   window.__API__.getMetrics()
   ```

3. **导出文档**
   ```typescript
   window.__API__.exportDocs()
   ```

4. **使用故障排查页面**
   访问: `/api-troubleshooting`

## 文档工具

### API 文档生成

```bash
python tools/generate_api_documentation.py
```

生成的文档包括：
- `docs/api/README.md` - 主文档
- `docs/api/{category}.md` - 分类文档
- `docs/api/openapi.json` - OpenAPI 规范
- `docs/api/frontend_mapping.md` - 前后端映射
- `docs/api/statistics.md` - 统计报告

## 配置说明

### 开发环境

```typescript
// 开发环境自动使用 Vite 代理
baseURL = '/api' // 代理到 http://localhost:8000
```

### 生产环境

```typescript
// 生产环境直接连接
baseURL = `${protocol}//${hostname}:8000/api`
```

## 最佳实践

### 1. 使用分类 API

优先使用预定义的分类 API 方法：

```typescript
// ✅ 推荐
import { api } from '@/api/core'
const data = await api.market.getKline({ symbol: '000001' })

// ❌ 不推荐
import axios from 'axios'
const data = await axios.get('/api/market/kline?symbol=000001')
```

### 2. 错误处理

使用 try-catch 处理错误：

```typescript
try {
  const data = await api.system.getStatus()
} catch (error) {
  if (isApiError(error)) {
    console.error('API 错误:', error.code, error.message)
    // 显示用户友好的错误消息
    message.error(errorHandler.getUserMessage(error))
  }
}
```

### 3. 请求去重

对于可能重复的请求，启用去重：

```typescript
// 多个组件同时请求相同数据时，只会发送一个请求
const data = await apiClient.get('/market/overview', null, {
  dedupe: true // 默认开启
})
```

### 4. 缓存策略

合理使用缓存减少服务器负载：

```typescript
// 市场概览数据缓存 30 秒
const data = await apiClient.get('/market/overview', null, {
  cache: true,
  cacheDuration: 30000
})
```

## 性能优化

### 请求批处理

对于多个独立请求，使用 Promise.all 并行执行：

```typescript
const [status, market, database] = await Promise.all([
  api.system.getStatus(),
  api.market.getOverview(),
  api.database.getStatus()
])
```

### 请求取消

长时间运行的请求应支持取消：

```typescript
const controller = new AbortController()

// 发起请求
const promise = apiClient.get('/long-running', null, {
  signal: controller.signal
})

// 取消请求
controller.abort()
```

## 监控告警

### 健康规则配置

```typescript
// 添加自定义健康规则
monitor.addHealthRule({
  name: '数据源延迟',
  description: '数据源响应时间超过5秒',
  threshold: 5000,
  action: 'alert',
  check: (logs) => {
    const dataSourceLogs = logs.filter(l => l.category === ApiCategory.DATA_SOURCE)
    return dataSourceLogs.some(l => l.duration > 5000)
  }
})
```

### 指标订阅

```typescript
// 订阅指标更新
const unsubscribe = monitor.subscribe((metrics) => {
  console.log('当前错误率:', metrics.global.errorRate)
  if (metrics.global.errorRate > 0.1) {
    // 触发告警
  }
})
```

## 故障排查流程

### 1. 问题识别

- 查看健康状态面板
- 检查错误率和响应时间
- 查看健康问题列表

### 2. 日志分析

- 使用时间范围过滤
- 按错误状态过滤
- 查看详细错误信息

### 3. 性能分析

- 查看响应时间分布
- 识别慢请求
- 分析请求模式

### 4. 根因定位

- 查看请求追踪
- 分析错误堆栈
- 检查相关端点

### 5. 问题修复

- 根据建议采取行动
- 验证修复效果
- 更新监控规则

## 迁移指南

### 从旧代码迁移

1. **替换 fetch 调用**
   ```typescript
   // 旧代码
   const response = await fetch('/api/system/status')
   
   // 新代码
   const response = await api.system.getStatus()
   ```

2. **替换 axios 直接调用**
   ```typescript
   // 旧代码
   import axios from 'axios'
   const { data } = await axios.get('/api/market/kline')
   
   // 新代码
   import { api } from '@/api/core'
   const data = await api.market.getKline()
   ```

3. **更新错误处理**
   ```typescript
   // 旧代码
   try {
     // ...
   } catch (error) {
     console.error(error)
   }
   
   // 新代码
   try {
     // ...
   } catch (error) {
     if (isApiError(error)) {
       message.error(errorHandler.getUserMessage(error))
     }
   }
   ```

## 常见问题

### Q: 如何添加新的 API 端点？

A: 在 `registry.ts` 中注册新端点，或使用 `registerEndpoint` 函数动态注册。

### Q: 如何禁用请求去重？

A: 在请求配置中设置 `dedupe: false`。

### Q: 如何清除缓存？

A: 调用 `apiClient.clearCache()` 清除所有缓存。

### Q: 如何查看所有注册的端点？

A: 使用 `apiRegistry.getAllEndpoints()` 或查看生成的文档。

### Q: 如何处理 401 未授权错误？

A: 错误处理器会自动处理，可以注册自定义处理器：
```typescript
errorHandler.registerHandler(ApiErrorCode.UNAUTHORIZED, (error) => {
  // 跳转到登录页
  router.push('/login')
})
```

## 总结

新的数据接口层提供了：

✅ **统一的 API 管理** - 所有请求通过单一客户端  
✅ **完整的日志记录** - 每个请求都可追踪  
✅ **实时性能监控** - 及时发现性能问题  
✅ **自动故障检测** - 主动发现和报告问题  
✅ **丰富的调试工具** - 快速定位和解决问题  
✅ **标准化错误处理** - 一致的错误处理体验  
✅ **灵活的扩展机制** - 易于添加新功能  

这个架构显著提升了系统的可维护性、可靠性和开发效率。