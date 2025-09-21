# AmazingData API 使用指南

## 目录
1. [快速开始](#快速开始)
2. [配置说明](#配置说明)
3. [基础使用](#基础使用)
4. [高级功能](#高级功能)
5. [错误处理](#错误处理)
6. [最佳实践](#最佳实践)
7. [故障排查](#故障排查)

---

## 快速开始

### 安装依赖

```bash
# 安装 AmazingData SDK
uv pip install installer/AmazingData-1.0.4-cp313-none-any.whl
```

### 基本配置

在 `settings.dev.yaml` 或 `settings.prod.yaml` 中配置：

```yaml
amazingdata:
  enabled: true
  priority: 1  # 最高优先级
  connection:
    username: "your_username"  # 直接配置，不使用环境变量
    password: "your_password"
    host: "120.86.124.106"
    port: 8600
```

### 快速示例

```python
from deepsearch.data_providers.enhanced_manager import get_data_manager

async def quick_example():
    # 获取管理器（自动使用 AmazingData）
    manager = await get_data_manager()
    
    # 获取日线数据
    df = await manager.get_stock_daily(
        symbol='000001',
        start_date='2025-01-01',
        end_date='2025-01-20',
        source='auto'  # 自动选择最佳数据源
    )
    
    print(f"获取到 {len(df)} 条数据")
```

---

## 配置说明

### 完整配置选项

```yaml
amazingdata:
  # 基础配置
  enabled: true                # 是否启用
  priority: 1                  # 优先级（1最高）
  
  # 连接配置
  connection:
    username: "your_username"   # 用户名
    password: "your_password"   # 密码（支持 encrypted: 前缀）
    host: "120.86.124.106"      # 服务器地址
    port: 8600                  # 端口
    timeout: 10                 # 连接超时（秒）
    max_retries: 3              # 最大重试次数
    heartbeat_interval: 30      # 心跳间隔（秒）
    auto_reconnect: true        # 自动重连
  
  # 缓存配置
  cache:
    enabled: true               # 启用缓存
    ttl: 300                    # 缓存过期时间（秒）
    max_size: 10000             # 最大缓存条目数
    clear_on_disconnect: false  # 断连时清除缓存
  
  # 订阅配置
  subscription:
    enabled: true               # 启用订阅
    batch_size: 100             # 批量订阅大小
    heartbeat_interval: 30      # 订阅心跳间隔
    max_symbols: 500            # 最大订阅股票数
    auto_resubscribe: true      # 断线后自动重订阅
  
  # 数据质量配置
  data_quality:
    check_enabled: true         # 启用数据质量检查
    min_completeness: 0.95      # 最小完整性要求
    alert_on_error: true        # 错误时告警
    validate_timestamps: true   # 验证时间戳
  
  # 性能配置
  performance:
    batch_requests: true        # 启用批量请求
    max_concurrent_requests: 10 # 最大并发请求数
    request_queue_size: 1000    # 请求队列大小
    use_connection_pool: true   # 使用连接池
    pool_size: 5                # 连接池大小
```

### 密码加密

支持加密存储敏感信息：

```yaml
connection:
  password: "encrypted:AES256$..."  # 加密后的密码
```

---

## 基础使用

### 1. 直接使用 AmazingDataProvider

```python
from deepsearch.data_providers.amazingdata import AmazingDataProvider, AmazingDataConfig

# 创建配置
config = AmazingDataConfig(
    username="your_username",
    password="your_password",
    host="120.86.124.106",
    port=8600
)

# 创建提供者
provider = AmazingDataProvider(config)
await provider.initialize()

# 使用各种接口
kline_df = await provider.get_kline('000001', period='1d')
quotes = await provider.get_realtime_quote(['000001', '600000'])
```

### 2. 通过管理器使用（推荐）

```python
from deepsearch.data_providers.enhanced_manager import get_data_manager

manager = await get_data_manager()

# 自动选择最佳数据源
df = await manager.get_stock_daily(
    symbol='000001',
    source='auto'  # 自动选择（优先 AmazingData）
)

# 强制使用 AmazingData
df = await manager.get_stock_daily(
    symbol='000001',
    source='amazingdata'
)
```

---

## 高级功能

### 1. 市场数据接口

#### K线数据
```python
# 获取日线
daily_df = await provider.get_kline(
    symbol='000001',
    period='1d',
    start_date='2025-01-01',
    end_date='2025-01-20',
    adjust='qfq'  # 前复权
)

# 获取分钟线
minute_df = await provider.get_kline(
    symbol='000001',
    period='5m',
    count=100  # 最近100条
)
```

#### 实时行情
```python
# 批量获取实时行情
quotes = await provider.get_realtime_quote(
    symbols=['000001', '600000', '000002']
)

for symbol, quote in quotes.items():
    print(f"{symbol}: {quote['last']} ({quote['change_percent']}%)")
```

### 2. 财务数据接口

#### 财务报表
```python
# 资产负债表
balance_sheet = await provider.get_financial_data(
    symbol='000001',
    report_type='balance_sheet',
    report_date='2024Q3'
)

# 利润表
income = await provider.get_financial_data(
    symbol='000001',
    report_type='income_statement'
)

# 现金流量表
cash_flow = await provider.get_financial_data(
    symbol='000001',
    report_type='cash_flow'
)
```

#### 主要财务指标
```python
indicators = await provider.get_key_indicators(
    symbol='000001',
    report_date='2024Q3'
)

print(f"ROE: {indicators['roe'].iloc[0]}%")
print(f"ROA: {indicators['roa'].iloc[0]}%")
print(f"EPS: {indicators['eps'].iloc[0]}")
```

### 3. 特殊数据接口

#### 股东信息
```python
shareholder_info = await provider.get_shareholder_info(
    symbol='000001',
    report_date='2024Q3'
)

print(f"股东户数: {shareholder_info['holder_num']}")
print(f"户均持股: {shareholder_info['avg_holding']}")

# 十大股东
for holder in shareholder_info['top10_holders']:
    print(f"{holder['name']}: {holder['ratio']}%")
```

#### 龙虎榜数据
```python
dragon_tiger = await provider.get_dragon_tiger(
    symbol='000001',
    start_date='2025-01-01',
    end_date='2025-01-20'
)

for record in dragon_tiger:
    print(f"{record['trade_date']}: {record['reason']}")
    print(f"买入金额: {record['buy_amount']}")
    print(f"卖出金额: {record['sell_amount']}")
```

#### 融资融券
```python
margin_df = await provider.get_margin_trading(
    symbol='000001',
    start_date='2025-01-01',
    end_date='2025-01-20'
)

print(f"融资余额: {margin_df['margin_balance'].iloc[-1]}")
print(f"融券余额: {margin_df['short_balance'].iloc[-1]}")
```

#### 北向资金
```python
north_flow = await provider.get_north_flow(
    start_date='2025-01-01',
    end_date='2025-01-20'
)

print(f"沪股通流入: {north_flow['shanghai_flow'].iloc[-1]}")
print(f"深股通流入: {north_flow['shenzhen_flow'].iloc[-1]}")
print(f"总流入: {north_flow['total_flow'].iloc[-1]}")
```

### 4. 实时订阅

```python
# 定义回调函数
def on_quote_update(data):
    print(f"收到行情更新: {data}")

# 订阅实时行情
success = await provider.subscribe_quote(
    symbols=['000001', '600000'],
    callback=on_quote_update,
    data_type='snapshot'  # 快照数据
)

# 订阅K线推送
success = await provider.subscribe_quote(
    symbols=['000001'],
    callback=on_kline_update,
    data_type='kline'
)

# 取消订阅
await provider.unsubscribe_quote(['000001'])
```

---

## 错误处理

### 使用自定义异常

```python
from deepsearch.data_providers.amazingdata_exceptions import (
    AmazingDataException,
    AmazingDataConnectionError,
    AmazingDataQueryError,
    AmazingDataRateLimitError,
    ErrorHandler
)

try:
    df = await provider.get_kline('000001')
except AmazingDataConnectionError as e:
    print(f"连接错误: {e.error_code.name}")
    if ErrorHandler.is_retryable(e):
        retry_delay = ErrorHandler.get_retry_delay(e)
        print(f"将在 {retry_delay} 秒后重试")
except AmazingDataQueryError as e:
    print(f"查询错误: {e.message}")
    print(f"详细信息: {e.details}")
except AmazingDataRateLimitError as e:
    print(f"限流错误，请 {e.details.get('retry_after', 60)} 秒后重试")
```

### 自动故障转移

使用管理器时会自动进行故障转移：

```python
# 即使 AmazingData 失败，也会自动降级到 QMT 或 AkShare
df = await manager.get_stock_daily(
    symbol='000001',
    source='auto'  # 自动故障转移
)
```

---

## 最佳实践

### 1. 使用连接池

```python
# 在配置中启用连接池
performance:
  use_connection_pool: true
  pool_size: 5
```

### 2. 批量请求

```python
# 批量获取多个股票的数据
symbols = ['000001', '000002', '600000', '600036']
quotes = await provider.get_realtime_quote(symbols)
```

### 3. 使用缓存

```python
# 通过管理器使用缓存
df = await manager.get_stock_daily(
    symbol='000001',
    use_cache=True  # 启用缓存
)
```

### 4. 异步并发

```python
import asyncio

async def fetch_multiple():
    tasks = [
        provider.get_kline('000001'),
        provider.get_kline('600000'),
        provider.get_financial_data('000002')
    ]
    results = await asyncio.gather(*tasks)
    return results
```

### 5. 资源管理

```python
# 使用上下文管理器
async with get_data_manager() as manager:
    df = await manager.get_stock_daily('000001')
    # 自动清理资源
```

---

## 故障排查

### 常见问题

#### 1. 连接失败

**症状**: `AmazingDataConnectionError: 连接失败`

**解决方案**:
- 检查网络连接
- 确认服务器地址和端口正确
- 检查防火墙设置
- 验证用户名密码

#### 2. 登录失败

**症状**: `AmazingDataAuthenticationError: 认证失败`

**解决方案**:
- 确认用户名密码正确
- 检查账户是否过期
- 确认 IP 白名单

#### 3. 数据为空

**症状**: 返回空 DataFrame

**解决方案**:
- 检查股票代码格式
- 确认日期范围有效
- 验证数据权限

#### 4. 订阅失败

**症状**: `AmazingDataSubscriptionError: 订阅失败`

**解决方案**:
- 检查订阅数量限制
- 确认订阅类型支持
- 验证实时数据权限

### 调试技巧

#### 启用详细日志

```python
from loguru import logger

# 设置日志级别
logger.add("amazingdata.log", level="DEBUG")
```

#### 查看连接状态

```python
# 检查连接
is_connected = provider.is_connected()
print(f"连接状态: {is_connected}")

# 获取统计信息
stats = provider.get_statistics()
print(f"查询次数: {stats['amazingdata_stats']['queries']}")
print(f"错误次数: {stats['amazingdata_stats']['query_errors']}")
```

#### 测试连接

```python
# 简单的连接测试
async def test_connection():
    try:
        # 尝试获取交易日历（轻量级查询）
        result = await provider._login()
        return result
    except Exception as e:
        print(f"连接测试失败: {e}")
        return False
```

### 性能优化

#### 1. 减少网络往返

```python
# 批量查询而不是循环单个查询
# 好的做法
quotes = await provider.get_realtime_quote(['000001', '600000', '000002'])

# 避免的做法
for symbol in symbols:
    quote = await provider.get_realtime_quote([symbol])
```

#### 2. 使用适当的缓存策略

```python
# 对于不常变化的数据使用较长缓存
financial_data = await manager.get_stock_daily(
    symbol='000001',
    use_cache=True  # 5分钟缓存
)

# 对于实时数据使用短缓存或不缓存
quotes = await manager.get_realtime_quotes(
    symbols=['000001'],
    use_cache=False  # 不缓存
)
```

#### 3. 并发控制

```python
# 限制并发请求数
performance:
  max_concurrent_requests: 10  # 避免过多并发
```

---

## 附录

### 数据字段映射

| AmazingData 字段 | 系统标准字段 | 说明 |
|-----------------|-------------|------|
| last_price | last | 最新价 |
| prev_close | close | 昨收价 |
| change_rate | change_percent | 涨跌幅 |
| fin_balance | margin_balance | 融资余额 |
| sec_balance | short_balance | 融券余额 |

### 周期参数对照

| 参数值 | 说明 |
|-------|------|
| 1m | 1分钟 |
| 5m | 5分钟 |
| 15m | 15分钟 |
| 30m | 30分钟 |
| 60m | 60分钟 |
| 1d | 日线 |
| 1w | 周线 |
| 1M | 月线 |

### 复权类型

| 参数值 | 说明 |
|-------|------|
| none | 不复权 |
| qfq | 前复权 |
| hfq | 后复权 |

---

*更新日期: 2025-01-20*
*版本: v1.0*