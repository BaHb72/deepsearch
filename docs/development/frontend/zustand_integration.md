# Zustand 状态管理集成架构

## 一、概述

采用 Zustand 作为 React 应用的全局状态管理方案，建立集中式数据中心，解决当前组件状态管理混乱、重复请求、数据不同步等问题。

## 二、架构设计

```
┌─────────────────────────────────────────────────────────┐
│                     React Components                      │
│  (DatabaseConfig, DataSourceManager, SystemMonitor...)    │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼ 使用
┌─────────────────────────────────────────────────────────┐
│                    Zustand Stores                         │
│  ┌──────────────┬──────────────┬────────────────┐       │
│  │DatabaseStore │DataSourceStore│ SystemStore    │       │
│  └──────────────┴──────────────┴────────────────┘       │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼ 调用
┌─────────────────────────────────────────────────────────┐
│                    Data Center Module                     │
│  (数据请求、缓存、错误处理、重试机制)                    │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼ 请求
┌─────────────────────────────────────────────────────────┐
│                      Backend API                          │
│                   (FastAPI Server)                        │
└─────────────────────────────────────────────────────────┘
```

## 三、核心优势

1. **状态持久化** - 数据存储在全局 store，组件卸载不丢失
2. **自动缓存** - 内置缓存机制，避免重复请求
3. **请求去重** - 多个组件同时请求自动合并
4. **实时同步** - 所有组件自动响应数据变化
5. **开发体验** - DevTools 支持，易于调试

## 四、目录结构

```
src/
├── stores/                     # Zustand stores
│   ├── index.ts               # 统一导出入口
│   ├── database.store.ts      # 数据库相关状态
│   ├── dataSource.store.ts    # 数据源相关状态
│   ├── system.store.ts        # 系统相关状态
│   └── types.ts               # 类型定义
├── dataCenter/                 # 数据中心模块
│   ├── index.ts               # 数据中心入口
│   ├── database.service.ts    # 数据库服务
│   ├── dataSource.service.ts  # 数据源服务
│   ├── cache.service.ts       # 缓存服务
│   └── utils.ts               # 工具函数
```

## 五、Store 设计示例

### DatabaseStore

```typescript
interface DatabaseState {
  // 状态
  connections: DatabaseConnection[]
  loading: boolean
  error: Error | null
  selectedId: number | null

  // 缓存控制
  lastFetch: number
  cacheTime: number // 缓存时间（毫秒）

  // 方法
  fetchConnections: (force?: boolean) => Promise<void>
  createConnection: (data: CreateConnectionDTO) => Promise<void>
  updateConnection: (id: number, data: UpdateConnectionDTO) => Promise<void>
  deleteConnection: (id: number) => Promise<void>
  testConnection: (id: number) => Promise<TestResult>
  selectConnection: (id: number | null) => void
  clearError: () => void
  reset: () => void
}
```

### DataSourceStore

```typescript
interface DataSourceState {
  // 状态
  sources: DataSource[]
  status: DataSourceStatus
  statistics: DataSourceStatistics
  loading: boolean
  error: Error | null

  // 缓存控制
  lastUpdate: number
  autoRefresh: boolean
  refreshInterval: number

  // 方法
  fetchSources: (force?: boolean) => Promise<void>
  fetchStatus: () => Promise<void>
  fetchStatistics: () => Promise<void>
  toggleSource: (id: string) => Promise<void>
  updateConfig: (id: string, config: any) => Promise<void>
  testSource: (id: string) => Promise<TestResult>
  startAutoRefresh: () => void
  stopAutoRefresh: () => void
  reset: () => void
}
```

## 六、数据中心服务

### 缓存策略

```typescript
class CacheService {
  private cache = new Map<string, CacheEntry>()

  set(key: string, data: any, ttl: number = 30000) {
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      ttl
    })
  }

  get(key: string): any | null {
    const entry = this.cache.get(key)
    if (!entry) return null

    if (Date.now() - entry.timestamp > entry.ttl) {
      this.cache.delete(key)
      return null
    }

    return entry.data
  }

  invalidate(pattern?: string) {
    if (!pattern) {
      this.cache.clear()
    } else {
      for (const key of this.cache.keys()) {
        if (key.includes(pattern)) {
          this.cache.delete(key)
        }
      }
    }
  }
}
```

### 请求去重

```typescript
class RequestManager {
  private pending = new Map<string, Promise<any>>()

  async execute<T>(
    key: string,
    fn: () => Promise<T>
  ): Promise<T> {
    // 如果有相同请求正在进行，返回同一个 Promise
    if (this.pending.has(key)) {
      return this.pending.get(key) as Promise<T>
    }

    // 创建新请求
    const promise = fn().finally(() => {
      this.pending.delete(key)
    })

    this.pending.set(key, promise)
    return promise
  }
}
```

## 七、组件使用示例

### 使用 Store

```typescript
import { useDatabaseStore } from '@/stores'

function DatabaseConfig() {
  const {
    connections,
    loading,
    error,
    fetchConnections,
    createConnection,
    deleteConnection
  } = useDatabaseStore()

  useEffect(() => {
    // 组件挂载时获取数据（如果没有缓存或缓存过期）
    fetchConnections()
  }, [])

  // 组件使用 store 中的数据
  return (
    <Table
      dataSource={connections}
      loading={loading}
    />
  )
}
```

### 跨组件数据共享

```typescript
// ComponentA.tsx
function ComponentA() {
  const { connections } = useDatabaseStore()
  return <div>连接数: {connections.length}</div>
}

// ComponentB.tsx
function ComponentB() {
  const { connections, updateConnection } = useDatabaseStore()
  // 两个组件共享同一份数据，ComponentB 的更新会自动反映到 ComponentA
  return <ConnectionList connections={connections} />
}
```

## 八、实施步骤

### 第一阶段：基础搭建
1. 安装 Zustand 及相关依赖
2. 创建基础 store 结构
3. 实现数据中心基础服务

### 第二阶段：功能迁移
1. 迁移 DatabaseConfig 使用 store
2. 迁移 DataSourceManager 使用 store
3. 迁移其他系统配置组件

### 第三阶段：优化增强
1. 添加持久化支持（localStorage）
2. 添加 DevTools 集成
3. 实现高级缓存策略
4. 添加乐观更新支持

## 九、注意事项

1. **避免过度订阅** - 使用 selector 只订阅需要的数据
2. **合理设置缓存** - 根据数据特性设置合适的缓存时间
3. **错误边界** - 在关键组件添加错误边界
4. **性能监控** - 使用 React DevTools 监控渲染性能

## 十、迁移清单

- [ ] 安装 zustand 依赖
- [ ] 创建 stores 目录结构
- [ ] 实现 DatabaseStore
- [ ] 实现 DataSourceStore
- [ ] 实现 SystemStore
- [ ] 创建数据中心服务
- [ ] 迁移 DatabaseConfig 组件
- [ ] 迁移 DataSourceManager 组件
- [ ] 添加 DevTools 支持
- [ ] 编写测试用例
- [ ] 更新相关文档

## 十一、性能指标

### 预期改进
- 请求次数减少 80%
- 组件渲染次数减少 60%
- 首屏加载时间减少 40%
- 内存占用减少 30%

### 监控指标
- API 请求频率
- 缓存命中率
- 组件渲染次数
- Store 更新频率