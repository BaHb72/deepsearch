# Backtrader + KLineChart 集成设计方案

## 目标

1. **Backtrader 作为数据生成引擎**：抛弃 `plot()`，纯粹用于回测计算和数据生成
2. **KLineChart 作为金融图表UI**：专业的K线图展示，支持技术指标、画线工具
3. **统一数据接口**：设计后端 Datafeed API 供 KLineChart 消费

---

## KLineChart 技术调研

### 库信息

| 项目 | 说明 |
|------|------|
| **名称** | KLineChart / KLineChart Pro |
| **GitHub** | <https://github.com/klinecharts/KLineChart> |
| **文档** | <https://pro.klinecharts.com/> |
| **特点** | 轻量(40kb gzip)、零依赖、支持移动端、TypeScript |
| **License** | Apache-2.0 |

### 安装

```bash
npm install klinecharts @klinecharts/pro
```

---

## Datafeed 接口规范

KLineChart Pro 通过 `Datafeed` 接口获取数据。我们需要实现以下接口：

### TypeScript 接口定义

```typescript
interface Datafeed {
  /**
   * 搜索标的
   * @param search 搜索关键词
   * @returns 标的信息列表
   */
  searchSymbols(search?: string): Promise<SymbolInfo[]>;

  /**
   * 获取历史K线数据
   * @param symbol 标的信息
   * @param period 周期
   * @param from 开始时间戳(毫秒)
   * @param to 结束时间戳(毫秒)
   * @returns K线数据数组
   */
  getHistoryKLineData(
    symbol: SymbolInfo,
    period: Period,
    from: number,
    to: number
  ): Promise<KLineData[]>;

  /**
   * 订阅实时数据
   * @param symbol 标的信息
   * @param period 周期
   * @param callback 数据回调
   */
  subscribe(
    symbol: SymbolInfo,
    period: Period,
    callback: DatafeedSubscribeCallback
  ): void;

  /**
   * 取消订阅
   */
  unsubscribe(symbol: SymbolInfo, period: Period): void;
}
```

### 核心数据结构

```typescript
// K线数据
interface KLineData {
  timestamp: number;    // Unix时间戳(毫秒)
  open: number;         // 开盘价
  high: number;         // 最高价
  low: number;          // 最低价
  close: number;        // 收盘价
  volume?: number;      // 成交量
  turnover?: number;    // 成交额
  [key: string]: any;   // 自定义指标字段
}

// 标的信息
interface SymbolInfo {
  ticker: string;           // 股票代码 (如 "000001.SZ")
  name?: string;            // 名称
  shortName?: string;       // 简称
  exchange?: string;        // 交易所
  market?: string;          // 市场
  pricePrecision?: number;  // 价格精度
  volumePrecision?: number; // 成交量精度
  priceCurrency?: string;   // 货币
  type?: string;            // 类型
  logo?: string;            // Logo URL
}

// 周期
interface Period {
  multiplier: number;  // 数值 (如 1, 5, 15)
  timespan: string;    // 单位 ("minute", "hour", "day", "week", "month")
  text: string;        // 显示文本 ("1m", "5m", "1d")
}

// 订阅回调
type DatafeedSubscribeCallback = (data: KLineData) => void;
```

---

## 后端 API 设计

### 端点规划

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/kline/symbols/search` | GET | 搜索标的 |
| `/api/kline/history` | GET | 获取历史K线 |
| `/api/kline/realtime/ws` | WebSocket | 实时推送 |

### API 详情

#### 1. 搜索标的

```http
GET /api/kline/symbols/search?q={keyword}&market={market}&limit={limit}
```

**响应：**

```json
{
  "success": true,
  "data": [
    {
      "ticker": "000001.SZ",
      "name": "平安银行",
      "shortName": "平安银行",
      "exchange": "SZSE",
      "market": "stocks",
      "pricePrecision": 2,
      "volumePrecision": 0,
      "priceCurrency": "CNY",
      "type": "stock"
    }
  ]
}
```

#### 2. 获取历史K线

```http
GET /api/kline/history?symbol={ticker}&period={period}&from={timestamp}&to={timestamp}
```

**参数：**

- `symbol`: 股票代码 (如 `000001.SZ`)
- `period`: 周期代码 (如 `1m`, `5m`, `15m`, `1h`, `1d`, `1w`, `1M`)
- `from`: 开始时间戳(毫秒)
- `to`: 结束时间戳(毫秒)

**响应：**

```json
{
  "success": true,
  "data": [
    {
      "timestamp": 1703721600000,
      "open": 10.50,
      "high": 10.68,
      "low": 10.45,
      "close": 10.62,
      "volume": 12345678,
      "turnover": 130567890.50
    }
  ]
}
```

#### 3. WebSocket 实时推送

```javascript
// 连接
const ws = new WebSocket('ws://localhost:8000/api/kline/realtime/ws');

// 订阅
ws.send(JSON.stringify({
  action: 'subscribe',
  symbol: '000001.SZ',
  period: '1m'
}));

// 接收数据
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // data: { type: 'kline', data: KLineData }
};

// 取消订阅
ws.send(JSON.stringify({
  action: 'unsubscribe',
  symbol: '000001.SZ',
  period: '1m'
}));
```

---

## Backtrader 集成架构

### 设计理念

```
┌──────────────────────────────────────────────────────────────────┐
│                     Backtrader 数据生成引擎                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│   │  Strategy   │    │  Analyzer   │    │ DataExport  │         │
│   │  (策略逻辑) │───▶│  (绩效分析) │───▶│  (数据导出) │         │
│   └─────────────┘    └─────────────┘    └─────────────┘         │
│                                                │                 │
└────────────────────────────────────────────────┼─────────────────┘
                                                 │
                                                 ▼
                          ┌──────────────────────────────────┐
                          │         JSON 数据输出             │
                          │  - equity_curve: 资金曲线         │
                          │  - trades: 交易记录               │
                          │  - signals: 买卖信号              │
                          │  - indicators: 指标数据           │
                          │  - metrics: 绩效指标              │
                          └───────────────┬──────────────────┘
                                          │
                          ┌───────────────┼───────────────┐
                          ▼               ▼               ▼
                    ┌──────────┐   ┌──────────┐   ┌──────────┐
                    │ REST API │   │ WebSocket │   │ Database │
                    │ /backtest │   │ (实时)   │   │ (持久化) │
                    └──────────┘   └──────────┘   └──────────┘
                          │               │               │
                          └───────────────┼───────────────┘
                                          ▼
                          ┌──────────────────────────────────┐
                          │        KLineChart 前端           │
                          │  - K线图 + 指标叠加              │
                          │  - 交易标记 (买卖点)             │
                          │  - 资金曲线图                    │
                          │  - 绩效面板                      │
                          └──────────────────────────────────┘
```

### Backtrader 输出适配器

```python
class BacktestResultExporter:
    """Backtrader 回测结果导出器"""

    def __init__(self, cerebro: bt.Cerebro):
        self.cerebro = cerebro

    def export_for_klinechart(self) -> dict:
        """导出为 KLineChart 可用的格式"""
        return {
            "klines": self._export_klines(),
            "trades": self._export_trades(),
            "signals": self._export_signals(),
            "indicators": self._export_indicators(),
            "equity_curve": self._export_equity_curve(),
            "metrics": self._export_metrics(),
        }

    def _export_klines(self) -> List[dict]:
        """导出K线数据"""
        return [
            {
                "timestamp": int(dt.timestamp() * 1000),
                "open": bar.open[0],
                "high": bar.high[0],
                "low": bar.low[0],
                "close": bar.close[0],
                "volume": bar.volume[0],
            }
            for dt, bar in self._iter_bars()
        ]

    def _export_trades(self) -> List[dict]:
        """导出交易记录（用于在图表上标记买卖点）"""
        return [
            {
                "timestamp": int(trade.dtopen.timestamp() * 1000),
                "type": "buy" if trade.size > 0 else "sell",
                "price": trade.price,
                "size": abs(trade.size),
                "pnl": trade.pnl,
            }
            for trade in self._get_trades()
        ]

    def _export_signals(self) -> List[dict]:
        """导出策略发出的信号"""
        # 从策略中提取信号记录
        pass

    def _export_indicators(self) -> Dict[str, List]:
        """导出技术指标数据

        返回格式:
        {
            "MA5": [10.5, 10.6, 10.7, ...],
            "MA20": [10.2, 10.3, 10.4, ...],
            "MACD": [0.1, 0.2, -0.1, ...],
        }
        """
        pass

    def _export_equity_curve(self) -> List[dict]:
        """导出资金曲线"""
        return [
            {
                "timestamp": int(dt.timestamp() * 1000),
                "value": value,
            }
            for dt, value in self._get_equity_values()
        ]

    def _export_metrics(self) -> dict:
        """导出绩效指标"""
        return {
            "total_return": 0.0,
            "annual_return": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "total_trades": 0,
        }
```

---

## 前端 Datafeed 实现

### DeepSearch Datafeed 类

```typescript
// src/api/klineDatafeed.ts

import type {
  Datafeed,
  SymbolInfo,
  Period,
  KLineData,
  DatafeedSubscribeCallback
} from '@klinecharts/pro';
import { request } from './request';

/**
 * DeepSearch KLineChart Datafeed 实现
 */
export class DeepSearchDatafeed implements Datafeed {
  private wsConnection: WebSocket | null = null;
  private subscriptions: Map<string, DatafeedSubscribeCallback> = new Map();

  /**
   * 搜索标的
   */
  async searchSymbols(search?: string): Promise<SymbolInfo[]> {
    const response = await request.get('/api/kline/symbols/search', {
      params: { q: search, limit: 50 }
    });
    return response.data;
  }

  /**
   * 获取历史K线数据
   */
  async getHistoryKLineData(
    symbol: SymbolInfo,
    period: Period,
    from: number,
    to: number
  ): Promise<KLineData[]> {
    const periodCode = `${period.multiplier}${period.timespan.charAt(0)}`;

    const response = await request.get('/api/kline/history', {
      params: {
        symbol: symbol.ticker,
        period: periodCode,
        from,
        to,
      }
    });

    return response.data;
  }

  /**
   * 订阅实时数据
   */
  subscribe(
    symbol: SymbolInfo,
    period: Period,
    callback: DatafeedSubscribeCallback
  ): void {
    const key = `${symbol.ticker}_${period.multiplier}${period.timespan}`;
    this.subscriptions.set(key, callback);

    this._ensureWebSocket();

    this.wsConnection?.send(JSON.stringify({
      action: 'subscribe',
      symbol: symbol.ticker,
      period: `${period.multiplier}${period.timespan.charAt(0)}`,
    }));
  }

  /**
   * 取消订阅
   */
  unsubscribe(symbol: SymbolInfo, period: Period): void {
    const key = `${symbol.ticker}_${period.multiplier}${period.timespan}`;
    this.subscriptions.delete(key);

    this.wsConnection?.send(JSON.stringify({
      action: 'unsubscribe',
      symbol: symbol.ticker,
      period: `${period.multiplier}${period.timespan.charAt(0)}`,
    }));
  }

  private _ensureWebSocket(): void {
    if (this.wsConnection?.readyState === WebSocket.OPEN) {
      return;
    }

    const wsUrl = `ws://${window.location.host}/api/kline/realtime/ws`;
    this.wsConnection = new WebSocket(wsUrl);

    this.wsConnection.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.type === 'kline') {
        const key = `${message.symbol}_${message.period}`;
        const callback = this.subscriptions.get(key);
        if (callback) {
          callback(message.data);
        }
      }
    };
  }
}
```

### 使用示例

```typescript
// src/pages/StrategyCenter/components/KLineChartPanel.tsx

import { useEffect, useRef } from 'react';
import { KLineChartPro } from '@klinecharts/pro';
import '@klinecharts/pro/dist/klinecharts-pro.css';
import { DeepSearchDatafeed } from '@/api/klineDatafeed';

export const KLineChartPanel: React.FC<{ symbol: string }> = ({ symbol }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<KLineChartPro | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // 创建图表实例
    chartRef.current = new KLineChartPro({
      container: containerRef.current,

      // 标的信息
      symbol: {
        ticker: symbol,
        shortName: symbol,
        exchange: 'SSE',
        market: 'stocks',
        pricePrecision: 2,
        volumePrecision: 0,
        priceCurrency: 'CNY',
      },

      // 初始周期
      period: {
        multiplier: 1,
        timespan: 'day',
        text: '日K',
      },

      // 可选周期列表
      periods: [
        { multiplier: 1, timespan: 'minute', text: '1分' },
        { multiplier: 5, timespan: 'minute', text: '5分' },
        { multiplier: 15, timespan: 'minute', text: '15分' },
        { multiplier: 60, timespan: 'minute', text: '60分' },
        { multiplier: 1, timespan: 'day', text: '日K' },
        { multiplier: 1, timespan: 'week', text: '周K' },
        { multiplier: 1, timespan: 'month', text: '月K' },
      ],

      // 默认指标
      mainIndicators: ['MA'],
      subIndicators: ['VOL', 'MACD'],

      // 使用 DeepSearch Datafeed
      datafeed: new DeepSearchDatafeed(),

      // 主题
      theme: 'dark',

      // 中文
      locale: 'zh-CN',
    });

    return () => {
      // 清理
      chartRef.current = null;
    };
  }, [symbol]);

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: '600px' }}
    />
  );
};
```

---

## 回测结果可视化

### 在 KLineChart 上叠加回测数据

```typescript
// 叠加交易标记
function overlayBacktestTrades(
  chart: KLineChartPro,
  trades: BacktestTrade[]
) {
  trades.forEach(trade => {
    // 使用 KLineChart 的画线功能标记买卖点
    chart.createOverlay({
      name: 'simpleTag',
      points: [{ timestamp: trade.timestamp, value: trade.price }],
      styles: {
        color: trade.type === 'buy' ? '#00ff00' : '#ff0000',
      },
    });
  });
}

// 叠加指标
function overlayIndicators(
  chart: KLineChartPro,
  indicators: Record<string, number[]>
) {
  // 指标作为自定义数据叠加到K线上
  Object.entries(indicators).forEach(([name, values]) => {
    chart.createIndicator({
      name,
      shortName: name,
      figures: [{ key: name, type: 'line' }],
      calc: () => values.map((v, i) => ({ [name]: v })),
    });
  });
}
```

---

## 实施阶段

| 阶段 | 内容 | 预计时间 |
|------|------|----------|
| Phase 1 | 后端 Kline API 设计与实现 | 2-3天 |
| Phase 2 | Backtrader 输出适配器 | 1-2天 |
| Phase 3 | 前端 Datafeed 实现 | 1-2天 |
| Phase 4 | KLineChart 组件封装 | 1-2天 |
| Phase 5 | WebSocket 实时推送 | 1天 |
| Phase 6 | 回测结果叠加与可视化 | 2天 |
| Phase 7 | 测试与优化 | 1-2天 |

**总计：约 9-14 天**

---

## 数据源竞速选优方案 (Racing Strategy)

> [!IMPORTANT]
> 设计目标：**自动选择最优数据源**，实现 AmazingData 和 MiniQMT 之间的智能切换

### 数据源特性对比

| 特性 | MiniQMT (xtdata) | AmazingData |
|------|------------------|-------------|
| **实时推送** | ✅ Tick级推送 (subscribe_quote) | ⚠️ 轮询模拟 (3s间隔) |
| **推送延迟** | ~50-200ms | ~3000ms+ |
| **历史数据** | ✅ 完整 | ✅ 完整 |
| **需要客户端** | ✅ 需要MiniQMT运行 | ❌ 独立SDK |
| **稳定性** | 依赖本地进程 | 云端服务 |
| **分钟数据** | ✅ 1m/5m/15m/60m | ✅ 1m/5m/15m/30m/60m |
| **Tick数据** | ✅ 原生支持 | ⚠️ 部分支持 |

### 竞速选优架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    DataSourceRacer (竞速调度器)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                   RaceConfig (竞速配置)                  │  │
│   │  - 优先级: [miniqmt, amazingdata]                       │  │
│   │  - 超时: 3000ms                                         │  │
│   │  - 策略: first_success / fastest / quality_score       │  │
│   └─────────────────────────────────────────────────────────┘  │
│                              │                                  │
│          ┌───────────────────┼───────────────────┐             │
│          ▼                   ▼                   ▼             │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     │
│   │ MiniQMT     │     │ AmazingData │     │ Database    │     │
│   │ Provider    │     │ Provider    │     │ Cache       │     │
│   │ (优先)       │     │ (备用)       │     │ (兜底)       │     │
│   └─────────────┘     └─────────────┘     └─────────────┘     │
│          │                   │                   │             │
│          └───────────────────┼───────────────────┘             │
│                              ▼                                  │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                  结果聚合 & 健康监控                      │  │
│   │  - 响应时间追踪                                          │  │
│   │  - 成功率统计                                            │  │
│   │  - 自动降级/恢复                                         │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 竞速选优实现

```python
# deepsearch/infrastructure/providers/racing/data_source_racer.py

import asyncio
from typing import List, Optional, Dict, Any
from enum import Enum

class RaceStrategy(Enum):
    FIRST_SUCCESS = "first_success"    # 第一个成功的
    FASTEST = "fastest"                 # 最快的
    QUALITY_SCORE = "quality_score"     # 质量评分最高的

class DataSourceHealth:
    """数据源健康状态"""
    def __init__(self):
        self.success_count = 0
        self.fail_count = 0
        self.total_latency_ms = 0
        self.last_success_time = None
        self.is_available = True

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        return self.success_count / total if total > 0 else 0.0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.success_count if self.success_count > 0 else float('inf')


class DataSourceRacer:
    """数据源竞速调度器"""

    def __init__(
        self,
        providers: List[DataProvider],
        strategy: RaceStrategy = RaceStrategy.FIRST_SUCCESS,
        timeout_ms: int = 3000,
    ):
        self.providers = providers
        self.strategy = strategy
        self.timeout_ms = timeout_ms
        self.health_map: Dict[str, DataSourceHealth] = {
            p.name: DataSourceHealth() for p in providers
        }

    async def race_query(
        self,
        method: str,
        *args,
        **kwargs
    ) -> Optional[Any]:
        """
        竞速查询 - 并发调用所有数据源，根据策略选择结果
        """
        tasks = []
        for provider in self._get_available_providers():
            task = asyncio.create_task(
                self._timed_call(provider, method, *args, **kwargs)
            )
            tasks.append((provider.name, task))

        # 根据策略处理结果
        if self.strategy == RaceStrategy.FIRST_SUCCESS:
            return await self._race_first_success(tasks)
        elif self.strategy == RaceStrategy.FASTEST:
            return await self._race_fastest(tasks)
        else:
            return await self._race_quality_score(tasks)

    async def _race_first_success(self, tasks):
        """返回第一个成功的结果"""
        done, pending = await asyncio.wait(
            [t for _, t in tasks],
            timeout=self.timeout_ms / 1000,
            return_when=asyncio.FIRST_COMPLETED
        )

        for task in done:
            result = task.result()
            if result is not None:
                # 取消其他任务
                for p in pending:
                    p.cancel()
                return result

        return None

    async def _timed_call(self, provider, method: str, *args, **kwargs):
        """带计时的调用"""
        import time
        start = time.time()
        try:
            func = getattr(provider, method)
            result = await func(*args, **kwargs)
            latency = (time.time() - start) * 1000
            self._record_success(provider.name, latency)
            return result
        except Exception as e:
            self._record_failure(provider.name)
            return None

    def _get_available_providers(self):
        """获取可用的数据源，按健康度排序"""
        available = [p for p in self.providers if self.health_map[p.name].is_available]
        # 按成功率和延迟排序
        return sorted(available, key=lambda p: (
            -self.health_map[p.name].success_rate,
            self.health_map[p.name].avg_latency_ms
        ))

    def _record_success(self, name: str, latency_ms: float):
        h = self.health_map[name]
        h.success_count += 1
        h.total_latency_ms += latency_ms
        h.last_success_time = datetime.now()
        h.is_available = True

    def _record_failure(self, name: str):
        h = self.health_map[name]
        h.fail_count += 1
        # 连续失败3次则标记为不可用
        if h.fail_count >= 3 and h.success_rate < 0.3:
            h.is_available = False
```

### 配置示例

```yaml
# config/data_sources.yaml
data_sources:
  racing:
    enabled: true
    strategy: first_success  # first_success / fastest / quality_score
    timeout_ms: 3000

  providers:
    - name: miniqmt
      priority: 1            # 最高优先级
      health_check_interval: 30s
      capabilities:
        - realtime_tick
        - history_kline
        - minute_data

    - name: amazingdata
      priority: 2
      fallback: true         # 作为备用数据源
      capabilities:
        - history_kline
        - minute_data
        - fundamental

    - name: database_cache
      priority: 3
      fallback: true
      ttl: 5m               # 缓存有效期
```

---

## 实时推送方案详解

### MiniQMT vs AmazingData 实时能力对比

#### MiniQMT (xtdata.subscribe_quote)

```python
# 原生支持 tick 级推送
def on_tick(data):
    # data: {'lastPrice': 10.5, 'volume': 1000, 'time': ...}
    pass

xtdata.subscribe_quote(
    stock_code='000001.SZ',
    period='tick',          # tick / 1m / 5m ...
    callback=on_tick
)
```

- **推送频率**：~50-200ms (取决于行情活跃度)
- **数据内容**：tick级别，含五档盘口
- **依赖**：需要MiniQMT客户端运行

#### AmazingData (轮询模拟)

```python
# 通过定时轮询模拟订阅
async def subscribe_quote(codes, callback, interval=3):
    while True:
        data = await self.get_realtime_quote(codes)
        callback(data)
        await asyncio.sleep(interval)
```

- **推送频率**：~3000ms (可配置，但受限于API调用频率)
- **数据内容**：snapshot快照
- **依赖**：网络连接

### 前端推送架构

```
┌─────────────────────────────────────────────────────────────────┐
│                       后端 WebSocket 网关                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │               SubscriptionManager                        │  │
│   │     管理前端订阅，聚合多用户相同symbol的订阅              │  │
│   └──────────────────────┬──────────────────────────────────┘  │
│                          │                                      │
│          ┌───────────────┼───────────────┐                     │
│          ▼               ▼               ▼                     │
│   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐             │
│   │ MiniQMT     │ │ AmazingData │ │ Fallback    │             │
│   │ Tick推送    │ │ 轮询推送     │ │ (无实时)    │             │
│   │ ~100ms      │ │ ~3000ms     │ │             │             │
│   └─────────────┘ └─────────────┘ └─────────────┘             │
│          │               │                                      │
│          └───────────────┼───────────────                      │
│                          ▼                                      │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                  K线聚合器                               │  │
│   │    将tick数据聚合为1m/5m/15m K线，推送给前端             │  │
│   └─────────────────────────────────────────────────────────┘  │
│                          │                                      │
└──────────────────────────┼──────────────────────────────────────┘
                           ▼
                    WebSocket 推送
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                       前端 KLineChart                            │
│   - 接收K线更新                                                  │
│   - 更新当前Bar或追加新Bar                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 指标计算架构

> [!IMPORTANT]
> **原则**：回测/策略场景用 **Backtrader** 计算，KLineChart 仅做 **展示层**

### 职责划分

| 场景 | 指标计算位置 | 原因 |
|------|-------------|------|
| **回测** | Backtrader | 策略逻辑一体化，确保一致性 |
| **实盘策略** | 后端 Python | 与回测逻辑复用 |
| **纯看盘** | 前端 KLineChart | 轻量、响应快 |
| **历史回放** | 后端预计算 | 数据已存在，前端直接展示 |

### Backtrader 指标计算集成

```python
# deepsearch/strategies/indicators/backtrader_bridge.py

import backtrader as bt

class IndicatorExporter:
    """从 Backtrader 策略中导出指标数据"""

    def __init__(self, strategy: bt.Strategy):
        self.strategy = strategy

    def export_all_indicators(self) -> Dict[str, List[float]]:
        """导出所有指标数据用于前端展示"""
        result = {}

        for indicator in self.strategy.getindicators():
            name = indicator.__class__.__name__
            # 导出指标的每个line
            for line_name, line in zip(indicator.lines._getlines(), indicator.lines):
                key = f"{name}_{line_name}" if len(indicator.lines) > 1 else name
                result[key] = list(line.array)

        return result

    def get_indicator_config(self) -> List[Dict]:
        """获取指标配置用于 KLineChart 渲染"""
        configs = []
        for indicator in self.strategy.getindicators():
            config = {
                'name': indicator.__class__.__name__,
                'params': {},
                'lines': [],
            }
            # 提取参数
            for param in indicator.params._getkeys():
                config['params'][param] = getattr(indicator.params, param)
            # 提取线条
            for line_name in indicator.lines._getlines():
                config['lines'].append(line_name)
            configs.append(config)
        return configs
```

### 前端图表渲染

```typescript
// 后端计算的指标数据叠加到 KLineChart
interface BacktestIndicators {
  [indicatorName: string]: number[];  // 与K线一一对应的值
}

function applyBacktestIndicators(
  chart: KLineChartPro,
  klines: KLineData[],
  indicators: BacktestIndicators
) {
  // 将后端指标数据合并到K线数据中
  const enrichedKlines = klines.map((kline, i) => {
    const enriched = { ...kline };
    for (const [name, values] of Object.entries(indicators)) {
      enriched[name] = values[i];
    }
    return enriched;
  });

  // 更新图表数据
  chart.updateData(enrichedKlines);

  // 注册自定义指标（仅渲染，不计算）
  for (const name of Object.keys(indicators)) {
    chart.createIndicator({
      name,
      figures: [{ key: name, type: 'line' }],
      calc: (kLineData) => kLineData.map(d => ({ [name]: d[name] })),
    });
  }
}
```

### 设计优势

1. **一致性**：回测和实盘使用相同的指标计算逻辑
2. **可维护性**：指标逻辑集中在后端，易于更新
3. **灵活性**：前端可随时更换图表库，不影响指标计算
4. **性能**：后端批量计算，前端仅渲染

---

## 参考资料

- [KLineChart 官方文档](https://klinecharts.com/)
- [KLineChart Pro 文档](https://pro.klinecharts.com/)
- [KLineChart GitHub](https://github.com/klinecharts/KLineChart)
- [Backtrader 官方文档](https://www.backtrader.com/docu/)
