# DataProxy 迁移指南

## 概述

UnifiedDataProxy (`core.domain.data_proxy.proxy`) 已废弃，请迁移到新的 DataAccessProxy (`core.infrastructure.providers.unified_proxy`)。

## 迁移原因

新的 DataAccessProxy 提供了更完善的功能：

| 功能 | UnifiedDataProxy (旧) | DataAccessProxy (新) |
|------|----------------------|---------------------|
| 初始化逻辑 | 不完整 (TODO) | 完整实现 |
| 熔断器 | 无 | 已集成 (5次失败熔断) |
| 监控 | 无 | 已集成 (延迟、成功率) |
| 重试机制 | 无 | 已集成 (最多3次) |
| 数据源路由 | 基础路由 | 智能路由 (按访问类型优先级) |

## 迁移步骤

### 1. 更新导入

**旧代码**:

```python
from core.domain.data_proxy import get_data_proxy

proxy = get_data_proxy()
```

**新代码**:

```python
from core.infrastructure.providers.unified_proxy import get_data_proxy

proxy = await get_data_proxy()  # 注意：新版本是异步的
```

### 2. 更新初始化

**旧代码**:

```python
proxy = UnifiedDataProxy(router=router)
await proxy.initialize()
```

**新代码**:

```python
proxy = await get_data_proxy()  # 自动初始化
```

### 3. 更新 API 调用

#### 获取实时行情

**旧代码**:

```python
quotes = await proxy.get_realtime_quotes(["000001", "000002"], source="auto")
```

**新代码**:

```python
# 单只股票
quote = await proxy.get_realtime_quote("000001", prefer_source=DataSourceType.QMT)

# 多只股票需要循环
quotes = []
for symbol in ["000001", "000002"]:
    quotes.append(await proxy.get_realtime_quote(symbol))
```

#### 获取K线数据

**旧代码**:

```python
df = await proxy.get_kline("000001", period="1d", limit=100, source="auto")
```

**新代码**:

```python
result = await proxy.get_historical_kline(
    "000001",
    period="daily",
    adjust="",
    prefer_source=DataSourceType.AKSHARE
)
df = result.get("data")  # 返回字典格式
```

#### 获取股票列表

**旧代码**:

```python
stocks = await proxy.get_stock_list(market="SH", board="主板", source="auto")
```

**新代码**:

```python
result = await proxy.get_stock_list(prefer_source=DataSourceType.AKSHARE)
stocks = result.legacy  # 使用旧格式
# 或
stocks = result.records  # 使用新的领域对象
```

## 新功能使用

### 熔断器控制

```python
# 检查数据源是否被熔断
is_open = proxy._is_circuit_open(DataSourceType.AKSHARE)

# 手动重置熔断器
proxy.reset_circuit_breaker(DataSourceType.AKSHARE)  # 重置单个数据源
proxy.reset_circuit_breaker()  # 重置所有数据源
```

### 监控统计

```python
# 获取监控数据
monitor = proxy.monitor
stats = monitor.get_statistics()  # 获取所有统计信息
```

## 完整示例

### 旧代码

```python
from core.domain.data_proxy import get_data_proxy

async def main():
    proxy = get_data_proxy()
    await proxy.initialize()

    # 获取K线
    df = await proxy.get_kline("000001", period="1d", limit=100)

    # 获取实时行情
    quotes = await proxy.get_realtime_quotes(["000001"])
```

### 新代码

```python
from core.infrastructure.providers.unified_proxy import get_data_proxy
from core.ports.data_sources import DataSourceType

async def main():
    proxy = await get_data_proxy()  # 自动初始化

    # 获取K线
    result = await proxy.get_historical_kline("000001", period="daily")
    df = result.get("data")

    # 获取实时行情
    quote = await proxy.get_realtime_quote("000001")
```

## 时间表

- **2026-01**: 添加 DeprecationWarning
- **2026-03**: 删除旧实现

## 需要帮助？

如果迁移遇到问题，请查看：

- 新实现源码: `packages/core/infrastructure/providers/unified_proxy.py`
- 使用示例: `packages/core/strategies/services/screening_service.py`
- API 文档: `apps/api/api/endpoints/data/data_source_monitor_api.py`
