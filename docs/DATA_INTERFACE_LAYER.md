# 数据接口层设计文档

## 概述

本文档描述了DeepSearch系统的数据接口层设计，该层提供了统一的数据访问抽象，支持多种数据源（如星耀数智、AkShare、QMT等）的接入和管理。

## 架构设计

### 分层结构

```
数据接口层
├── 接口定义层 (interfaces/data/)
│   ├── base.py          # 基础抽象接口
│   ├── models.py        # 数据模型定义
│   └── cache.py         # 缓存机制
├── 实现层 (implementations/)
│   ├── amazingdata_impl.py  # 星耀数智实现
│   ├── akshare_impl.py      # AkShare实现
│   └── qmt_impl.py          # QMT实现
└── 管理层 (managers/)
    ├── data_manager.py       # 数据管理器
    └── router.py            # 路由选择器
```

### 核心组件

#### 1. 接口抽象 (`base.py`)

定义了所有数据源必须实现的标准接口：

- **IDataProvider**: 基础数据提供者接口
- **IBasicDataProvider**: 基础数据接口（代码列表、交易日历等）
- **IMarketDataProvider**: 市场数据接口（K线、实时行情等）
- **IFinancialDataProvider**: 财务数据接口（财报、指标等）
- **IShareholderDataProvider**: 股东数据接口
- **ISpecialDataProvider**: 特色数据接口（龙虎榜、北向资金等）
- **ISubscriptionProvider**: 订阅数据接口
- **ICompleteDataProvider**: 完整数据提供者接口（继承所有接口）

#### 2. 数据模型 (`models.py`)

定义了统一的数据结构：

- **StockInfo**: 股票基本信息
- **KlineData**: K线数据
- **SnapshotData**: 实时快照数据
- **TickData**: 逐笔成交数据
- **OrderBookData**: 盘口数据
- **FinancialReport**: 财务报表基类
- **BalanceSheet**: 资产负债表
- **IncomeStatement**: 利润表
- **CashFlow**: 现金流量表
- **KeyIndicators**: 主要财务指标
- **ShareholderData**: 股东数据
- **DragonTigerData**: 龙虎榜数据
- **MarginTradingData**: 融资融券数据
- **NorthFlowData**: 北向资金数据

#### 3. 缓存机制 (`cache.py`)

多级缓存系统：

- **MemoryCache**: 内存缓存（LRU算法）
- **RedisCache**: Redis缓存
- **DataCache**: 多级缓存管理器
- **CacheDecorator**: 缓存装饰器

## 使用指南

### 1. 基本使用

```python
from deepsearch.interfaces.data.amazingdata_impl import (
    AmazingDataProvider,
    AmazingDataConfig
)
from deepsearch.interfaces.data.base import SecurityType, PeriodType
import asyncio

async def main():
    # 创建配置
    config = AmazingDataConfig(
        username="your_username",
        password="your_password",
        host="120.86.124.106",
        port=8600,
        cache_enabled=True,
        cache_ttl=300
    )

    # 创建数据提供者
    provider = AmazingDataProvider(config)

    # 初始化
    await provider.initialize()

    # 获取股票列表
    stock_list = await provider.get_code_list(SecurityType.STOCK_A)
    print(f"A股数量: {len(stock_list)}")

    # 获取K线数据
    kline_df = await provider.get_kline(
        symbol='000001',
        period=PeriodType.DAILY,
        start_date='20250101',
        end_date='20250115'
    )
    print(kline_df.head())

    # 获取实时行情
    snapshot = await provider.get_snapshot(['000001', '600000'])
    for symbol, data in snapshot.items():
        print(f"{symbol}: {data['last_price']} ({data['change_percent']}%)")

    # 断开连接
    await provider.disconnect()

asyncio.run(main())
```

### 2. 使用缓存

```python
from deepsearch.interfaces.data.cache import DataCache, CacheDecorator

# 创建缓存
cache = DataCache(
    ttl=300,  # 5分钟
    memory_size=1000,
    redis_config={
        'host': 'localhost',
        'port': 6379,
        'db': 0
    }
)

# 使用缓存装饰器
@CacheDecorator(cache, ttl=60)('stock_kline')
async def get_stock_kline(symbol: str, period: str):
    # 这里执行实际的数据获取
    return await provider.get_kline(symbol, period)

# 第一次调用会执行函数
data1 = await get_stock_kline('000001', '1d')

# 第二次调用从缓存获取
data2 = await get_stock_kline('000001', '1d')
```

### 3. 错误处理

```python
from deepsearch.interfaces.data.base import (
    DataProviderError,
    AuthenticationError,
    DataNotFoundError,
    RateLimitError,
    NetworkError
)

async def safe_get_data():
    try:
        # 尝试获取数据
        data = await provider.get_kline('000001')
        return data

    except AuthenticationError as e:
        print(f"认证失败: {e.message}")
        # 重新登录
        await provider.connect()

    except RateLimitError as e:
        print(f"触发限流: {e.message}")
        # 等待后重试
        await asyncio.sleep(e.details.get('retry_after', 60))

    except NetworkError as e:
        print(f"网络错误: {e.message}")
        # 切换数据源或重试

    except DataNotFoundError as e:
        print(f"数据不存在: {e.message}")
        return None

    except DataProviderError as e:
        print(f"数据错误: {e.message}")
        raise
```

### 4. 订阅实时数据

```python
from deepsearch.interfaces.data.base import PeriodType

# 定义回调函数
async def on_snapshot_update(data):
    print(f"收到快照: {data}")

async def on_tick_update(data):
    print(f"收到逐笔: {data}")

# 订阅快照
await provider.subscribe(
    symbols=['000001', '600000'],
    data_type=PeriodType.SNAPSHOT,
    callback=on_snapshot_update
)

# 订阅逐笔
await provider.subscribe(
    symbols=['000001'],
    data_type=PeriodType.TICK,
    callback=on_tick_update
)

# 查看当前订阅
subscriptions = await provider.get_subscriptions()
print(f"当前订阅: {subscriptions}")

# 取消订阅
await provider.unsubscribe(['000001'], PeriodType.TICK)
```

### 5. 批量操作

```python
# 批量获取多个股票的K线
async def batch_get_klines(symbols: List[str], period: str):
    tasks = []
    for symbol in symbols:
        task = provider.get_kline(symbol, period)
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    data = {}
    for symbol, result in zip(symbols, results):
        if isinstance(result, Exception):
            print(f"获取{symbol}失败: {result}")
        else:
            data[symbol] = result

    return data

# 使用
symbols = ['000001', '000002', '600000', '600036']
klines = await batch_get_klines(symbols, '1d')
```

## 配置说明

### AmazingData配置

```python
config = AmazingDataConfig(
    # 认证信息
    username="your_username",
    password="your_password",
    host="120.86.124.106",
    port=8600,

    # 基础配置
    enabled=True,
    priority=1,  # 优先级（数字越小优先级越高）

    # 缓存配置
    cache_enabled=True,
    cache_ttl=300,  # 缓存过期时间（秒）

    # 连接配置
    timeout=30,  # 请求超时（秒）
    max_retries=3,  # 最大重试次数
    heartbeat_interval=60,  # 心跳间隔（秒）
    auto_reconnect=True,  # 自动重连
    reconnect_interval=10,  # 重连间隔（秒）

    # 本地存储配置
    local_path='D://AmazingData_local_data//',
    use_local=True  # 使用本地缓存
)
```

### 缓存配置

```python
cache_config = {
    # 内存缓存
    'memory_size': 1000,  # 最大缓存条目数
    'memory_ttl': 300,  # 默认过期时间

    # Redis缓存
    'redis_config': {
        'host': 'localhost',
        'port': 6379,
        'db': 0,
        'password': None,
        'key_prefix': 'deepsearch'
    }
}
```

## 性能优化

### 1. 使用缓存

- 对频繁访问的数据启用缓存
- 合理设置缓存过期时间
- 使用多级缓存（内存+Redis）

### 2. 批量请求

- 尽量使用批量接口而非循环单个请求
- 使用异步并发获取多个数据

### 3. 连接池

- 复用连接，避免频繁建立连接
- 合理设置连接池大小

### 4. 数据压缩

- 对大数据量使用压缩传输
- 缓存中存储压缩后的数据

## 扩展开发

### 添加新数据源

1. 继承相应的接口：

```python
from deepsearch.interfaces.data.base import ICompleteDataProvider

class NewDataProvider(ICompleteDataProvider):
    """新数据源实现"""

    async def initialize(self) -> None:
        # 初始化逻辑
        pass

    async def get_kline(self, symbol: str, **kwargs) -> pd.DataFrame:
        # 实现K线获取
        pass

    # 实现其他必需的接口方法
```

2. 注册到数据管理器：

```python
from deepsearch.managers.data_manager import DataManager

manager = DataManager()
manager.register_provider('new_source', NewDataProvider(config))
```

### 自定义数据模型

```python
from dataclasses import dataclass
from deepsearch.interfaces.data.models import FinancialReport

@dataclass
class CustomReport(FinancialReport):
    """自定义报表"""
    custom_field1: float = 0
    custom_field2: str = ""

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            'custom_field1': self.custom_field1,
            'custom_field2': self.custom_field2
        })
        return base
```

## 监控和调试

### 获取统计信息

```python
# 获取数据源统计
stats = await provider.get_statistics()
print(f"查询次数: {stats['statistics']['queries']}")
print(f"错误次数: {stats['statistics']['query_errors']}")
print(f"缓存命中率: {stats['statistics']['cache_hits'] / stats['statistics']['queries']}")

# 获取缓存统计
cache_stats = cache.get_stats()
print(f"内存缓存: {cache_stats['memory']}")
print(f"Redis缓存: {cache_stats.get('redis', {})}")
```

### 健康检查

```python
# 检查数据源健康状态
health = await provider.health_check()
if health['status'] == 'healthy':
    print("数据源正常")
else:
    print(f"数据源异常: {health['error']}")

# 检查连接状态
is_connected = await provider.is_connected()
print(f"连接状态: {'已连接' if is_connected else '未连接'}")
```

### 日志配置

```python
from loguru import logger

# 设置日志级别
logger.add("data_interface.log", level="DEBUG")

# 在代码中使用
logger.debug("获取K线数据", symbol=symbol, period=period)
logger.info("数据源初始化成功")
logger.error("数据获取失败", error=str(e))
```

## 最佳实践

1. **始终使用异步操作**：所有接口都是异步的，确保使用`await`
2. **合理设置超时**：避免长时间等待
3. **实现重试机制**：处理临时网络问题
4. **使用连接池**：提高并发性能
5. **监控性能指标**：及时发现问题
6. **定期清理缓存**：避免内存泄漏
7. **记录详细日志**：便于问题排查
8. **处理所有异常**：确保系统稳定性

## 故障排查

### 常见问题

1. **连接失败**
   - 检查网络连接
   - 验证认证信息
   - 确认服务器地址和端口

2. **数据为空**
   - 检查股票代码格式
   - 确认日期范围
   - 验证数据权限

3. **缓存未生效**
   - 检查缓存配置
   - 确认Redis连接
   - 查看缓存键是否正确

4. **性能问题**
   - 使用批量接口
   - 启用缓存
   - 检查网络延迟

---

*文档版本：1.0.0*
*更新日期：2025-01-15*