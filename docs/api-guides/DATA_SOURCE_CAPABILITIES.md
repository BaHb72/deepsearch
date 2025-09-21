# DeepSearch 数据源能力详细文档

> 最后更新: 2025-08-17
> 
> 本文档详细描述 DeepSearch 系统中各数据源的能力矩阵、API 接口映射以及使用指南。

## 目录

- [数据源概览](#数据源概览)
- [能力矩阵详情](#能力矩阵详情)
- [已实现的数据接口](#已实现的数据接口)
- [数据源优先级](#数据源优先级)
- [API 使用示例](#api-使用示例)
- [数据格式兼容性](#数据格式兼容性)

## 数据源概览

DeepSearch 支持三个主要数据源，每个数据源有不同的特点和适用场景：

| 数据源 | 类型 | 优先级 | 特点 | 适用场景 |
|--------|------|--------|------|----------|
| **QMT** | 本地量化终端 | 1 (最高) | 全功能支持，实时性最强，数据最全 | 专业量化交易、高频策略、Level2 数据需求 |
| **MiniQMT** | 轻量级终端 | 2 | 支持大部分功能，资源占用少 | 个人量化、中低频策略、日常分析 |
| **AkShare** | 开源接口 | 3 | 基础功能，免费开源，易于部署 | 数据回测、历史分析、学习研究 |

## 能力矩阵详情

### 完整能力对比表

| 数据能力 | 说明 | QMT | MiniQMT | AkShare | AkShare API |
|----------|------|:---:|:-------:|:-------:|-------------|
| **市场数据** |
| 市场概览 (MARKET_OVERVIEW) | 大盘指数、市场总览 | ✅ | ✅ | ✅ | `stock_zh_index_spot_em` |
| 市场宽度 (MARKET_BREADTH) | 涨跌家数、涨跌分布 | ✅ | ✅ | ✅ | `stock_zh_a_spot_em` |
| 资金流向 (CAPITAL_FLOW) | 主力资金、北向资金 | ✅ | ❌ | ✅ | `stock_em_hsgt_north_net_flow_in` |
| 板块数据 (SECTOR_DATA) | 行业板块、概念板块 | ✅ | ✅ | ✅ | `stock_sector_spot` |
| 异动监控 (ANOMALY_DETECTION) | 异常波动、突发事件 | ✅ | ✅ | ❌ | - |
| **行情数据** |
| 实时行情 (REALTIME_QUOTES) | 最新价格、涨跌幅 | ✅ | ✅ | ✅ | `stock_zh_a_spot_em` |
| K线数据 (KLINE_DATA) | 日/周/月/年K线 | ✅ | ✅ | ✅ | `stock_zh_a_hist` |
| 逐笔数据 (TICK_DATA) | Tick级别成交 | ✅ | ❌ | ❌ | - |
| 分钟数据 (MINUTE_DATA) | 1/5/15/30/60分钟 | ✅ | ✅ | ✅ | `stock_zh_a_hist_min_em` |
| **深度数据** |
| 盘口数据 (ORDER_BOOK) | 五档/十档买卖盘 | ✅ | ✅ | ❌ | - |
| Level2数据 (LEVEL2_DATA) | 逐笔委托、队列 | ✅ | ❌ | ❌ | - |
| 成交明细 (TRANSACTION_DATA) | 逐笔成交明细 | ✅ | ❌ | ❌ | - |
| **特色数据** |
| 筹码分布 (CHIP_DISTRIBUTION) | 成本分布、获利盘 | ✅ | ✅ | ❌ | - |
| 龙虎榜 (DRAGON_TIGER) | 机构买卖、游资动向 | ✅ | ✅ | ✅ | `stock_lhb_detail_daily_sina` |
| 大宗交易 (BLOCK_TRADE) | 大宗交易明细 | ✅ | ❌ | ✅ | `stock_dzjy_sctj` |
| **基础信息** |
| 股票信息 (STOCK_INFO) | 股票代码、名称、基本信息 | ✅ | ✅ | ✅ | `stock_info_a_code_name` |
| 财务数据 (FINANCIAL_DATA) | 财报、业绩、财务指标 | ✅ | ✅ | ✅ | `stock_financial_report_sina` |
| 公告数据 (ANNOUNCEMENT) | 公司公告、重大事项 | ✅ | ❌ | ✅ | `stock_notice_report` |

### 数据源特性对比

#### QMT 独有功能
- ✅ Level2 逐笔数据
- ✅ 逐笔委托队列
- ✅ 实时成交明细
- ✅ 高精度 Tick 数据
- ✅ 完整筹码分布计算

#### MiniQMT 特色功能
- ✅ 筹码分布（简化版）
- ✅ 实时盘口数据
- ✅ 异动监控
- ✅ 龙虎榜数据
- ❌ 不支持 Level2

#### AkShare 基础功能
- ✅ 历史 K 线数据
- ✅ 基础实时行情
- ✅ 财务数据
- ✅ 北向资金流
- ❌ 不支持实时盘口

## 已实现的数据接口

### 1. DataProviderManager 统一接口

```python
# 核心方法
async def get_stock_daily()      # 获取日线数据（支持前复权/后复权/不复权）
async def get_stock_minute()     # 获取分钟数据（1/5/15/30/60分钟）  
async def get_realtime_quotes()  # 获取实时行情（批量获取）
async def get_data_with_capability()  # 根据能力自动选择最优数据源

# 数据源管理
register_provider()               # 注册新数据源
get_available_providers()         # 获取可用数据源列表
check_capability_support()        # 检查数据源能力支持
```

### 2. AkShare 数据接口实现状态

#### 已完全实现的接口

| 功能类别 | AkShare API | 实现方法 | 说明 | 状态 |
|----------|-------------|----------|------|------|
| **行情数据** |
| 实时行情 | `stock_zh_a_spot_em` / `stock_individual_info_em` | `get_realtime_quote()` | A股实时行情（支持个股快速查询） | ✅ 已实现 |
| 历史日线 | `stock_zh_a_hist` | `get_stock_hist()` | 支持日/周/月线，前复权/后复权/不复权 | ✅ 已实现 |
| 分钟K线 | `stock_zh_a_hist_min_em` | `get_stock_minute()` | 1/5/15/30/60分钟K线 | ✅ 已实现 |
| **基础信息** |
| 股票信息 | `stock_individual_info_em` | `fetch_stock_info()` | 个股详细信息（含行业、市值等） | ✅ 已实现 |
| 股票列表 | `stock_info_a_code_name` | `fetch_stock_list()` | A股完整代码列表 | ✅ 已实现 |

#### 已在能力矩阵中声明但未实现的接口

| 功能类别 | AkShare API | 计划方法 | 说明 | 状态 |
|----------|-------------|----------|------|------|
| **市场数据** |
| 市场概览 | `stock_zh_index_spot_em` | `get_market_overview()` | 大盘指数实时 | ⏳ 待实现 |
| 市场宽度 | `stock_zh_a_spot_em` | `get_market_breadth()` | 涨跌家数统计 | ⏳ 待实现 |
| 资金流向 | `stock_em_hsgt_north_net_flow_in` | `get_capital_flow()` | 北向资金流 | ⏳ 待实现 |
| 板块数据 | `stock_sector_spot` | `get_sector_data()` | 行业/概念板块 | ⏳ 待实现 |
| **特色数据** |
| 龙虎榜 | `stock_lhb_detail_daily_sina` | `get_dragon_tiger()` | 每日龙虎榜 | ⏳ 待实现 |
| 大宗交易 | `stock_dzjy_sctj` | `get_block_trades()` | 大宗交易统计 | ⏳ 待实现 |
| **财务数据** |
| 财务报表 | `stock_financial_report_sina` | `get_financial_data()` | 财报数据 | ⏳ 待实现 |
| 公司公告 | `stock_notice_report` | `get_announcements()` | 公告信息 | ⏳ 待实现 |

### 3. QMT 数据接口实现状态

> 📖 详细实现方案请参考：[QMT API 实现指南](./QMT_API_IMPLEMENTATION.md)

#### 已实现功能

| 功能类别 | 接口方法 | 实现状态 | 说明 |
|----------|----------|----------|------|
| **WebSocket 实时推送** |
| 订阅管理 | `subscribe()` / `unsubscribe()` | ✅ 已实现 | 支持批量订阅/取消订阅 |
| 实时行情推送 | WebSocket `/ws/qmt` | ✅ 已实现 | 推送实时行情数据 |
| 盘口数据推送 | WebSocket 消息 | ✅ 已实现 | 五档买卖盘实时推送 |
| **HTTP API** |
| 连接状态 | `GET /api/qmt/status` | ✅ 已实现 | 获取QMT连接状态 |
| 订阅管理 | `POST /api/qmt/subscribe` | ✅ 已实现 | 批量订阅/取消订阅 |
| **核心组件** |
| QMT网关 | `QMTGatewayComponent` | ✅ 已实现 | 系统组件，管理QMT连接 |
| 动态脚本 | `qmt_dynamic.py` | ✅ 已实现 | QMT终端内数据采集脚本 |

#### 待实现功能（基于官方API）

| 功能类别 | QMT原生API | 计划方法 | 优先级 | 说明 |
|----------|------------|----------|--------|------|
| **历史数据** |
| K线数据下载 | `download_history_data()` | `get_kline_data()` | 🔴 高 | 支持多周期、复权 |
| **实时数据** |
| 全推Tick | `get_full_tick()` | `get_realtime_tick()` | 🔴 高 | 获取最新tick数据 |
| 增强订阅 | `subscribe_quote()` | `subscribe_enhanced()` | 🔴 高 | 支持回调函数 |
| **市场数据** |
| 龙虎榜 | `get_longhubang()` | `get_dragon_tiger()` | 🟡 中 | 龙虎榜数据 |
| 北向资金 | `get_north_finance_change()` | `get_north_flow()` | 🟡 中 | 北向资金流 |
| 换手率 | `get_turnover_rate()` | `get_turnover()` | 🟡 中 | 换手率数据 |
| **成交分析** |
| 内外盘 | `get_bvol()` / `get_svol()` | `get_buy_sell_vol()` | 🟢 低 | 内外盘成交量 |
| **ETF数据** |
| ETF信息 | `get_etf_info()` | `get_etf_info()` | 🟢 低 | ETF申赎清单 |
| ETF净值 | `get_etf_iopv()` | `get_etf_iopv()` | 🟢 低 | ETF参考净值 |

### 4. MiniQMT 数据接口实现状态

| 功能类别 | 接口方法 | 实现状态 | 说明 |
|----------|----------|----------|------|
| **基础架构** |
| 数据提供者 | `MiniQMTProvider` | ✅ 框架已实现 | 继承自DataProvider基类 |
| Socket连接 | `_connect()` | ✅ 已实现 | TCP连接到MiniQMT终端 |
| 心跳机制 | `_heartbeat_loop()` | ✅ 已实现 | 30秒心跳保持连接 |
| 数据接收 | `_receive_loop()` | ✅ 已实现 | 异步接收数据 |
| **API端点** |
| 连接状态 | `GET /api/miniqmt/status` | ✅ 已实现 | 获取连接状态 |
| 测试连接 | `POST /api/miniqmt/test` | ✅ 已实现 | 测试终端连接 |
| **数据接口** |
| 实时行情 | 待实现 | ⏳ 待完善 | 需要完善数据解析逻辑 |
| K线数据 | 待实现 | ⏳ 待完善 | 需要实现请求和响应处理 |
| 盘口数据 | 待实现 | ⏳ 待完善 | 需要实现五档盘口获取 |

## 数据源优先级

系统自动选择数据源的优先级顺序：

```python
PROVIDER_PRIORITY = {
    "qmt": 1,      # 最高优先级 - 本地实时数据
    "miniqmt": 2,  # 次优先级 - 本地量化终端
    "akshare": 3,  # 第三优先级 - 可通过代理访问
}
```

### 自动故障转移机制

1. **健康检查**: 每个数据源定期健康检查
2. **自动降级**: 主数据源失败自动切换备用
3. **智能路由**: 根据数据类型选择最佳源

## API 使用示例

### 1. 自动选择最佳数据源

```python
from deepsearch.data_providers.manager import DataProviderManager
from deepsearch.data_providers.capabilities import DataCapability

# 初始化管理器
manager = DataProviderManager()
await manager.initialize()

# 系统自动选择支持筹码分布的数据源（QMT > MiniQMT）
response = await manager.get_data_with_capability(
    DataCapability.CHIP_DISTRIBUTION,
    DataRequest(symbol="000001.SZ", period="1d")
)
```

### 2. 检查数据源能力

```python
# 检查哪些数据源支持 Level2 数据
support = manager.check_capability_support(DataCapability.LEVEL2_DATA)
print(support)
# 输出: {'qmt': True, 'miniqmt': False, 'akshare': False}

# 获取支持某能力的所有数据源
from deepsearch.data_providers.capabilities import get_capable_providers
providers = get_capable_providers(DataCapability.CAPITAL_FLOW)
print(providers)
# 输出: ['qmt', 'akshare']  # 按优先级排序
```

### 3. 指定数据源获取数据

```python
# 强制使用 AkShare
df = await manager.get_stock_daily(
    symbol="000001",
    start_date="2024-01-01",
    end_date="2024-12-31",
    source="akshare",  # 指定数据源
    adjust="qfq"  # 前复权
)

# 自动选择最佳源
df = await manager.get_stock_daily(
    symbol="000001",
    source="auto"  # 自动选择
)
```

### 4. 回测集成示例

```python
from deepsearch.backtest import BacktestEngine, DataBridge

# DataBridge 自动处理不同数据源的格式差异
bridge = DataBridge()
engine = BacktestEngine()

# 获取数据（自动选择最佳源）
df = await manager.get_stock_daily("000001", "2024-01-01", "2024-12-31")

# 自动转换为 Backtrader 格式
bt_data = bridge.convert_to_backtrader(df)
# 自动检测源类型、标准化字段、验证数据完整性

# 创建 Backtrader feed
bt_feed = bridge.create_backtrader_feed(bt_data)
```

## 数据格式兼容性

### DataBridge 自动格式转换

系统通过 `DataBridge` 实现不同数据源格式的无缝转换：

| 源格式 | 字段示例 | 自动转换为 | 说明 |
|--------|----------|------------|------|
| **AkShare 中文** | 日期,开盘,最高,最低,收盘,成交量 | date,open,high,low,close,volume | 自动识别中文字段 |
| **QMT 混合** | date,开盘,high,最低,close,vol | date,open,high,low,close,volume | 智能识别混合格式 |
| **标准英文** | date,open,high,low,close,volume | 保持不变 | 已标准化 |
| **时间戳格式** | ts,o,h,l,c,v | date,open,high,low,close,volume | 自动展开缩写 |

### 数据验证规则

DataBridge 自动执行以下验证和修复：

1. **价格逻辑检查**
   - high >= max(open, close, low)
   - low <= min(open, close, high)
   - 自动修正不合理值

2. **缺失值处理**
   - 使用前向填充 (ffill) 处理 NaN
   - 成交量缺失默认填充 0

3. **时间索引标准化**
   - 自动转换为 DatetimeIndex
   - 统一时区处理

4. **字段完整性**
   - 自动补充缺失的必要字段
   - 生成合理的默认值

## 性能建议

### 数据源选择策略

1. **实时交易**: 优先 QMT > MiniQMT
2. **历史回测**: AkShare 足够（成本低）
3. **深度分析**: 必须 QMT（Level2 数据）
4. **日常监控**: MiniQMT 最佳平衡

### 缓存优化

- 历史数据自动缓存 15 分钟
- 实时数据不缓存
- 筹码分布缓存 5 分钟

## 实施指南

### 如何添加新的AkShare接口

1. **在 `akshare_direct.py` 中添加新方法**：
```python
async def get_market_overview(self) -> Dict[str, Any]:
    """获取市场概览数据"""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        self._executor,
        self._fetch_market_overview_sync
    )
    return result

def _fetch_market_overview_sync(self) -> Dict[str, Any]:
    """同步获取市场概览"""
    df = ak.stock_zh_index_spot_em()
    # 数据处理逻辑
    return processed_data
```

2. **在 `DataProviderManager` 中添加统一接口**：
```python
async def get_market_overview(self, source: str = "auto") -> pd.DataFrame:
    """获取市场概览数据"""
    # 智能选择数据源
    if source == "auto":
        providers = get_capable_providers(DataCapability.MARKET_OVERVIEW)
        # 选择最优数据源
    # 调用具体实现
```

3. **更新能力矩阵**：
- 确保在 `capabilities.py` 中的 `AKSHARE_API_MAPPING` 已包含新接口

### 数据源优先级策略

当前系统采用分层架构：
1. **QMT** - 优先级1：本地量化终端，最全功能
2. **MiniQMT** - 优先级2：轻量终端，平衡功能
3. **AkShare** - 优先级3：开源接口，基础功能

## 当前开发重点

### 需要完善的功能

#### 1. AkShare 数据接口
- [ ] 实现市场概览接口 (`stock_zh_index_spot_em`)
- [ ] 实现板块数据接口 (`stock_sector_spot`)
- [ ] 实现北向资金流接口 (`stock_em_hsgt_north_net_flow_in`)
- [ ] 实现龙虎榜数据接口 (`stock_lhb_detail_daily_sina`)
- [ ] 实现大宗交易接口 (`stock_dzjy_sctj`)
- [ ] 实现财务数据接口 (`stock_financial_report_sina`)

#### 2. MiniQMT 数据接口
- [ ] 完善实时行情数据解析
- [ ] 实现K线数据请求和响应
- [ ] 实现五档盘口数据获取
- [ ] 完善订阅管理机制
- [ ] 实现筹码分布计算

#### 3. QMT 网关增强
- [ ] 增加Level2数据支持
- [ ] 实现逐笔成交数据推送
- [ ] 优化WebSocket推送性能
- [ ] 增加数据压缩和批量传输

### 计划支持的数据源

- [ ] 通达信数据接口
- [ ] 同花顺 iFinD
- [ ] Wind 终端
- [ ] Tushare Pro
- [ ] 东方财富 Choice

### 未来增加的能力

- [ ] 港美股数据 (GLOBAL_MARKET)
- [ ] ETF期权数据（50ETF、300ETF等）

## 相关文档

- [QMT API 实现指南](./QMT_API_IMPLEMENTATION.md) - QMT数据接口详细实现方案
- [数据提供者设计文档](./DATA_PROVIDER_DESIGN.md) - 数据源架构设计
- [回测系统集成指南](../deepsearch/backtest/README.md) - 回测系统使用说明
- [API 参考文档](./API_REFERENCE.md) - API接口参考

---

*本文档由 DeepSearch 团队维护，最后更新于 2025-08-17*