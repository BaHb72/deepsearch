# 数据源API前后端映射关系

生成时间: 2025-09-17

## 🔴 关键问题：数据源监控API不匹配

### 问题描述
前端数据源监控页面（`DataSourceMonitor.tsx`）无法正常获取数据，因为前后端API路径不匹配。

### 具体不匹配项

| 功能 | 前端请求路径 | 后端实际路径 | 状态 |
|------|-------------|-------------|------|
| **获取监控数据** | `/data-sources/monitor` | 无此端点 | ❌ 不匹配 |
| 获取数据源状态 | `/data-sources/status` | `/api/data-sources/status` | ✅ 匹配 |
| 获取数据源列表 | `/data-sources/list` | `/api/data-sources/list` | ✅ 匹配 |
| 测试数据源 | `/data-sources/test` | `/api/data-sources/test` | ✅ 匹配 |
| 切换数据源 | `/data-sources/switch` | 无此端点 | ❌ 不匹配 |
| 获取监控健康状态 | 未使用 | `/api/monitor/datasource/health` | ⚠️ 后端已实现但前端未使用 |
| 获取监控统计 | 未使用 | `/api/monitor/datasource/statistics` | ⚠️ 后端已实现但前端未使用 |

## 数据源相关API完整映射表

### 1. 数据源管理 (`/api/data-sources`)

| 方法 | 路径 | 前端函数 | 后端处理器 | 状态 |
|------|------|----------|-----------|------|
| GET | `/status` | `fetchDataSourceList()` | `data_source_status.get_data_source_status` | ✅ |
| GET | `/list` | `getDataSources()` | `datasource_manager.list_data_sources` | ✅ |
| POST | `/create` | `createDataSource()` | `datasource_manager.create_data_source` | ✅ |
| PUT | `/{id}/update` | `updateDataSource()` | `datasource_manager.update_data_source` | ✅ |
| DELETE | `/{id}/delete` | `deleteDataSource()` | `datasource_manager.delete_data_source` | ✅ |
| POST | `/test` | `testDataSource()` | `datasource_manager.test_data_source` | ✅ |
| GET | `/monitor` | `getDataSourceMonitor()` | `datasource_manager.get_data_source_monitor` | ✅ |
| POST | `/switch` | `switchDataSource()` | `datasource_manager.switch_primary_source` | ✅ |
| POST | `/cache/refresh` | `refreshDataSourceCache()` | `datasource_manager.refresh_data_source_cache` | ✅ |

### 2. 数据源监控 (`/api/monitor/datasource`)

| 方法 | 路径 | 前端函数 | 后端处理器 | 状态 |
|------|------|----------|-----------|------|
| GET | `/health` | 未使用 | `data_source_monitor_api.get_health_status` | ⚠️ |
| GET | `/health/{source}` | 未使用 | `data_source_monitor_api.get_source_health` | ⚠️ |
| GET | `/statistics` | 未使用 | `data_source_monitor_api.get_statistics` | ⚠️ |
| GET | `/recommendation` | 未使用 | `data_source_monitor_api.get_recommendation` | ⚠️ |
| GET | `/metrics` | 未使用 | `data_source_monitor_api.get_metrics` | ⚠️ |
| POST | `/reset` | 未使用 | `data_source_monitor_api.reset_metrics` | ⚠️ |
| GET | `/circuit-breaker` | 未使用 | `data_source_monitor_api.get_circuit_breaker_status` | ⚠️ |
| POST | `/circuit-breaker/reset` | 未使用 | `data_source_monitor_api.reset_circuit_breaker` | ⚠️ |
| GET | `/realtime` | 未使用 | `data_source_monitor_api.get_realtime_monitoring` | ⚠️ |
| GET | `/test` | 未使用 | `data_source_monitor_api.test_data_access` | ⚠️ |
| WS | `/ws` | 未使用 | `data_source_monitor_api.websocket_endpoint` | ⚠️ |

### 3. 数据源监控（第二套） (`/api/monitor/data-sources`)

| 方法 | 路径 | 前端函数 | 后端处理器 | 状态 |
|------|------|----------|-----------|------|
| GET | `/health` | 未使用 | `data_source_api.get_health_status` | ⚠️ |
| GET | `/statistics` | 未使用 | `data_source_api.get_statistics` | ⚠️ |
| GET | `/recommendation` | 未使用 | `data_source_api.get_recommendation` | ⚠️ |
| GET | `/records` | 未使用 | `data_source_api.get_records` | ⚠️ |
| GET | `/metrics` | 未使用 | `data_source_api.get_metrics` | ⚠️ |
| POST | `/reset` | 未使用 | `data_source_api.reset_metrics` | ⚠️ |
| WS | `/ws` | 未使用 | `data_source_api.websocket_endpoint` | ⚠️ |

### 4. 数据源能力 (`/api/datasource/capabilities`)

| 方法 | 路径 | 前端函数 | 后端处理器 | 状态 |
|------|------|----------|-----------|------|
| GET | `/matrix` | `fetchDataSourceCapabilities()` | `data_source_capability_api.get_capability_matrix` | ✅ |
| GET | `/{source}` | `fetchSourceCapabilities()` | `data_source_capability_api.get_source_capabilities` | ✅ |
| GET | `/compare` | `compareDataSources()` | `data_source_capability_api.compare_sources` | ✅ |
| GET | `/recommend` | `recommendDataSource()` | `data_source_capability_api.recommend_source` | ✅ |
| GET | `/check` | `checkFeatureAvailability()` | `data_source_capability_api.check_feature` | ✅ |
| POST | `/batch-check` | `batchCheckFeatures()` | **缺失** | ❌ |
| GET | `/categories` | `fetchCapabilityCategories()` | **缺失** | ❌ |

## 🛠️ 修复方案

### 方案1：添加缺失的后端端点（推荐）

在 `datasource_manager.py` 中添加缺失的端点：

```python
@router.get("/monitor")
async def get_data_source_monitor():
    """获取数据源监控信息，桥接到实际的监控服务"""
    from deepsearch.webui.api.endpoints.data.data_source_monitor_api import get_health_status, get_statistics

    # 获取健康状态
    health = await get_health_status()

    # 获取统计信息
    stats = await get_statistics(time_window=3600)

    # 转换为前端期望的格式
    return format_monitor_response(health, stats)

@router.post("/switch")
async def switch_data_source(request: SwitchRequest):
    """切换主数据源"""
    # 实现数据源切换逻辑
    pass

@router.post("/cache/refresh")
async def refresh_cache(request: RefreshRequest):
    """刷新数据源缓存"""
    # 实现缓存刷新逻辑
    pass
```

### 方案2：修改前端API调用（备选）

修改 `dataSource.ts` 中的API路径：

```typescript
// 原路径
getDataSourceMonitor: () =>
  request.get<DataSourceMonitor>('/data-sources/monitor'),

// 改为实际存在的后端路径
getDataSourceMonitor: () =>
  request.get<DataSourceMonitor>('/monitor/datasource/health'),
```

### 方案3：统一API规范（长期）

1. **移除冗余API**：合并两套监控API（`/api/monitor/datasource` 和 `/api/monitor/data-sources`）
2. **统一命名规范**：采用 RESTful 风格，如 `/api/datasources/{id}/monitor`
3. **更新文档**：维护API文档的实时性

## 📊 API使用统计

### 数据源相关API使用情况

| 模块 | 总端点数 | 前端使用 | 使用率 |
|------|----------|----------|--------|
| 数据源管理 | 11 | 8 | 72.7% |
| 数据源监控(1) | 11 | 0 | 0% |
| 数据源监控(2) | 7 | 0 | 0% |
| 数据源能力 | 7 | 5 | 71.4% |
| **总计** | **36** | **13** | **36.1%** |

### 问题分析

1. **监控API完全未使用**：18个监控相关端点，前端完全没有使用
2. **功能重复**：两套监控API功能重复，需要合并
3. **关键功能缺失**：`/data-sources/monitor` 是前端核心依赖，但后端未实现

## 📝 待办事项

- [ ] 实现 `/api/data-sources/monitor` 端点
- [ ] 实现 `/api/data-sources/switch` 端点
- [ ] 实现 `/api/data-sources/cache/refresh` 端点
- [ ] 合并两套监控API
- [ ] 更新前端API调用，使用已实现的监控端点
- [ ] 清理未使用的API端点
- [ ] 更新API文档

## 🔄 版本记录

| 版本 | 日期 | 修改内容 |
|------|------|----------|
| 1.0 | 2025-09-17 | 初始版本，识别数据源监控API不匹配问题 |