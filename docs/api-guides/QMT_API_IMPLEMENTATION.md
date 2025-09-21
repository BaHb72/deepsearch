# QMT API 接口实现指南

> 最后更新: 2025-08-17
> 
> 本文档基于QMT官方API文档，详细规划DeepSearch系统中QMT数据源的实现方案。

## 目录

- [核心API概览](#核心api概览)
- [已实现接口](#已实现接口)
- [待实现接口](#待实现接口)
- [实现方案设计](#实现方案设计)
- [代码示例](#代码示例)

## 核心API概览

### QMT提供的数据能力

QMT（迅投QMT量化交易终端）提供了完整的量化数据接口，涵盖以下核心功能：

| 功能分类 | API接口 | 说明 |
|---------|---------|------|
| **历史数据** | `download_history_data()` | 下载指定周期的历史行情数据 |
| **实时行情** | `get_full_tick()` | 获取最新的全推tick数据 |
| **订阅管理** | `subscribe_quote()` / `unsubscribe_quote()` | 订阅/取消订阅行情 |
| **全推订阅** | `subscribe_whole_quote()` | 订阅全市场推送数据 |
| **成交分析** | `get_bvol()` / `get_svol()` | 获取内外盘成交量 |
| **市场指标** | `get_turnover_rate()` | 获取换手率数据 |
| **龙虎榜** | `get_longhubang()` | 获取龙虎榜数据 |
| **北向资金** | `get_north_finance_change()` | 获取北向资金流数据 |
| **港股通** | `get_hkt_details()` / `get_hkt_statistics()` | 港股通持股数据 |
| **ETF数据** | `get_etf_info()` / `get_etf_iopv()` | ETF申赎清单和净值 |

## 已实现接口

### 当前DeepSearch中已实现的QMT功能

```python
# deepsearch/datafeed/qmt/scripts/qmt_dynamic.py
class QMTDataCollector:
    def subscribe_stocks(self, symbols: List[str])  # ✅ 已实现
    def unsubscribe_stocks(self, symbols: List[str])  # ✅ 已实现
    def get_snapshot(self, symbol: str)  # ✅ 已实现（基础版）
```

### WebSocket推送机制

```python
# deepsearch/webui/api/qmt.py
@router.websocket("/ws/qmt")  # ✅ 已实现
@router.post("/subscribe")  # ✅ 已实现
@router.post("/unsubscribe")  # ✅ 已实现
@router.get("/subscribed")  # ✅ 已实现
```

## 待实现接口

### 高优先级（核心功能）

#### 1. 历史数据下载
```python
async def download_history_data(
    self,
    stock_code: str,
    period: str,  # '1d', '60m', '30m', '15m', '5m', '1m'
    start_time: str,
    end_time: str,
    dividend_type: str = 'none'  # 'none', 'front', 'back'
) -> pd.DataFrame:
    """
    下载历史K线数据
    
    QMT原生API: download_history_data()
    """
    pass
```

#### 2. 全推Tick数据
```python
async def get_full_tick(
    self,
    stock_codes: List[str]
) -> Dict[str, Dict]:
    """
    获取最新的全推tick数据
    
    QMT原生API: ContextInfo.get_full_tick()
    返回数据包括：
    - lastPrice: 最新价
    - askPrice/bidPrice: 五档买卖价
    - askVol/bidVol: 五档买卖量
    - volume: 成交量
    - amount: 成交额
    """
    pass
```

#### 3. 实时行情订阅（增强版）
```python
async def subscribe_quote_enhanced(
    self,
    stock_code: str,
    period: str = 'tick',
    dividend_type: str = 'none',
    callback: Callable = None
) -> int:
    """
    增强版行情订阅，支持回调
    
    QMT原生API: ContextInfo.subscribe_quote()
    """
    pass
```

### 中优先级（特色数据）

#### 4. 龙虎榜数据
```python
async def get_longhubang(
    self,
    stock_list: List[str],
    start_date: str,
    end_date: str
) -> pd.DataFrame:
    """
    获取龙虎榜数据
    
    QMT原生API: ContextInfo.get_longhubang()
    """
    pass
```

#### 5. 北向资金流
```python
async def get_north_finance_change(
    self,
    period: str = '1d'  # '1d', '1w', '1m'
) -> pd.DataFrame:
    """
    获取北向资金变化数据
    
    QMT原生API: ContextInfo.get_north_finance_change()
    """
    pass
```

#### 6. 换手率数据
```python
async def get_turnover_rate(
    self,
    stock_list: List[str],
    start_time: str,
    end_time: str
) -> pd.DataFrame:
    """
    获取换手率数据
    
    QMT原生API: ContextInfo.get_turnover_rate()
    """
    pass
```

### 低优先级（扩展功能）

#### 7. 内外盘成交量
```python
async def get_buy_sell_volume(
    self,
    stock_code: str
) -> Dict[str, int]:
    """
    获取内外盘成交量
    
    QMT原生API: 
    - ContextInfo.get_bvol() - 外盘量
    - ContextInfo.get_svol() - 内盘量
    """
    pass
```

#### 8. ETF数据
```python
async def get_etf_info(
    self,
    etf_code: str
) -> Dict:
    """
    获取ETF申赎清单
    
    QMT原生API: get_etf_info()
    """
    pass

async def get_etf_iopv(
    self,
    etf_code: str
) -> float:
    """
    获取ETF参考净值
    
    QMT原生API: get_etf_iopv()
    """
    pass
```

## 实现方案设计

### 架构设计

```
┌─────────────────────────────────────────┐
│         QMT Terminal (迅投终端)          │
│  ┌────────────────────────────────────┐  │
│  │    qmt_dynamic.py (动态脚本)       │  │
│  │  - 运行在QMT Python环境中          │  │
│  │  - 调用QMT原生API                  │  │
│  │  - 通过ZMQ推送数据                 │  │
│  └────────────────────────────────────┘  │
└─────────────────────────────────────────┘
                    ↓ ZMQ
┌─────────────────────────────────────────┐
│      QMTGatewayComponent (网关组件)      │
│  - 接收ZMQ数据                          │
│  - 数据格式转换                         │
│  - 管理订阅状态                         │
│  - WebSocket推送                        │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│        DataProviderManager              │
│  - 统一数据接口                         │
│  - 智能路由                             │
│  - 故障转移                             │
└─────────────────────────────────────────┘
```

### 数据流设计

1. **历史数据流程**
   - 客户端请求 → DataProviderManager → QMTGateway
   - QMTGateway → ZMQ请求 → qmt_dynamic.py
   - qmt_dynamic调用download_history_data
   - 数据返回 → 格式转换 → 客户端

2. **实时数据流程**
   - 订阅请求 → QMTGateway → qmt_dynamic.py
   - qmt_dynamic调用subscribe_quote
   - 实时数据推送 → ZMQ → QMTGateway
   - WebSocket推送 → 前端

## 代码示例

### 1. 在qmt_dynamic.py中实现核心功能

```python
# deepsearch/datafeed/qmt/scripts/qmt_dynamic.py

import xtquant.xtdata as xtdata
from xtquant import xtconstant

class QMTDataCollector:
    """QMT数据采集器 - 运行在QMT终端内"""
    
    def __init__(self):
        self.context = None  # QMT上下文
        
    def download_history_data(self, params):
        """下载历史数据"""
        stock_code = params['stock_code']
        period = params['period']
        start_time = params['start_time']
        end_time = params['end_time']
        
        # 调用QMT原生API
        data = xtdata.download_history_data(
            stock_code, period, start_time, end_time
        )
        
        # 获取下载的数据
        df = xtdata.get_market_data(
            field_list=['open', 'high', 'low', 'close', 'volume'],
            stock_list=[stock_code],
            period=period,
            start_time=start_time,
            end_time=end_time
        )
        
        # 转换为标准格式
        return self._format_kline_data(df)
    
    def get_full_tick(self, stock_codes):
        """获取全推tick数据"""
        tick_data = {}
        
        for code in stock_codes:
            # 获取最新tick
            tick = xtdata.get_full_tick([code])
            if tick and code in tick:
                tick_data[code] = {
                    'lastPrice': tick[code]['lastPrice'],
                    'askPrice': tick[code]['askPrice'],  # 五档卖价
                    'bidPrice': tick[code]['bidPrice'],  # 五档买价
                    'askVol': tick[code]['askVol'],      # 五档卖量
                    'bidVol': tick[code]['bidVol'],      # 五档买量
                    'volume': tick[code]['volume'],
                    'amount': tick[code]['amount'],
                    'timestamp': tick[code]['timestamp']
                }
        
        return tick_data
    
    def subscribe_quote_callback(self, data):
        """行情推送回调"""
        # 通过ZMQ推送数据
        self.zmq_push({
            'type': 'quote_update',
            'data': data
        })
    
    def get_longhubang(self, params):
        """获取龙虎榜数据"""
        stock_list = params['stock_list']
        start_date = params['start_date']
        end_date = params['end_date']
        
        # 调用QMT API
        df = self.context.get_longhubang(
            stock_list, start_date, end_date
        )
        
        return df.to_dict('records')
    
    def get_north_finance(self, period='1d'):
        """获取北向资金数据"""
        # 调用QMT API
        df = self.context.get_north_finance_change(period)
        
        return {
            'period': period,
            'data': df.to_dict('records')
        }
```

### 2. 在QMTGateway中处理请求

```python
# deepsearch/datafeed/qmt/gateway.py

class QMTGateway:
    """QMT网关 - 管理与QMT终端的通信"""
    
    async def download_history_data(
        self,
        stock_code: str,
        period: str,
        start_time: str,
        end_time: str
    ) -> pd.DataFrame:
        """请求历史数据"""
        
        # 发送请求到QMT
        request = {
            'action': 'download_history_data',
            'params': {
                'stock_code': stock_code,
                'period': period,
                'start_time': start_time,
                'end_time': end_time
            }
        }
        
        # 通过ZMQ发送请求
        response = await self._send_request(request)
        
        # 转换为DataFrame
        if response['success']:
            return pd.DataFrame(response['data'])
        else:
            raise Exception(f"获取历史数据失败: {response['error']}")
    
    async def get_full_tick(self, stock_codes: List[str]) -> Dict:
        """获取全推tick数据"""
        
        request = {
            'action': 'get_full_tick',
            'params': {
                'stock_codes': stock_codes
            }
        }
        
        response = await self._send_request(request)
        return response['data']
    
    async def get_longhubang(
        self,
        stock_list: List[str],
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """获取龙虎榜数据"""
        
        request = {
            'action': 'get_longhubang',
            'params': {
                'stock_list': stock_list,
                'start_date': start_date,
                'end_date': end_date
            }
        }
        
        response = await self._send_request(request)
        return pd.DataFrame(response['data'])
```

### 3. 在DataProvider中暴露统一接口

```python
# deepsearch/data_providers/qmt_provider.py

class QMTProvider(DataProvider):
    """QMT数据提供者"""
    
    def __init__(self):
        super().__init__()
        self.gateway = None
    
    async def initialize(self):
        """初始化QMT连接"""
        from deepsearch.datafeed.qmt.gateway import QMTGateway
        self.gateway = QMTGateway()
        await self.gateway.connect()
    
    async def get_kline_data(
        self,
        symbol: str,
        period: str,
        start_date: str,
        end_date: str,
        adjust: str = 'none'
    ) -> pd.DataFrame:
        """获取K线数据 - 实现DataProvider接口"""
        
        # 转换周期格式
        period_map = {
            '1m': '1m',
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '60m': '60m',
            '1d': '1d',
            '1w': '1w',
            '1M': '1m'
        }
        
        qmt_period = period_map.get(period, '1d')
        
        # 调用网关获取数据
        df = await self.gateway.download_history_data(
            stock_code=symbol,
            period=qmt_period,
            start_time=start_date,
            end_time=end_date
        )
        
        # 处理复权
        if adjust == 'front':
            df = self._adjust_price(df, 'front')
        elif adjust == 'back':
            df = self._adjust_price(df, 'back')
        
        return df
    
    async def get_realtime_tick(
        self,
        symbols: List[str]
    ) -> Dict[str, Dict]:
        """获取实时tick数据"""
        return await self.gateway.get_full_tick(symbols)
    
    async def get_special_data(
        self,
        data_type: str,
        **kwargs
    ) -> Any:
        """获取特殊数据"""
        
        if data_type == 'longhubang':
            return await self.gateway.get_longhubang(**kwargs)
        elif data_type == 'north_finance':
            return await self.gateway.get_north_finance(**kwargs)
        elif data_type == 'turnover_rate':
            return await self.gateway.get_turnover_rate(**kwargs)
        else:
            raise ValueError(f"不支持的数据类型: {data_type}")
```

## 实施计划

### 第一阶段：核心功能（1-2周）
1. ✅ 实现历史数据下载接口
2. ✅ 实现全推tick数据获取
3. ✅ 增强订阅管理功能
4. ✅ 完善数据格式转换

### 第二阶段：特色数据（1周）
1. ⏳ 实现龙虎榜数据接口
2. ⏳ 实现北向资金数据接口
3. ⏳ 实现换手率数据接口
4. ⏳ 实现内外盘成交量接口

### 第三阶段：扩展功能（1周）
1. ⏳ 实现ETF数据接口
2. ⏳ 实现港股通数据接口
3. ⏳ 性能优化和缓存机制
4. ⏳ 完善错误处理和重试机制

## 测试计划

### 单元测试
```python
# tests/test_qmt_provider.py

async def test_download_history_data():
    """测试历史数据下载"""
    provider = QMTProvider()
    await provider.initialize()
    
    df = await provider.get_kline_data(
        symbol='000001.SZ',
        period='1d',
        start_date='2024-01-01',
        end_date='2024-01-31'
    )
    
    assert not df.empty
    assert 'open' in df.columns
    assert 'close' in df.columns

async def test_get_full_tick():
    """测试全推tick数据"""
    provider = QMTProvider()
    await provider.initialize()
    
    ticks = await provider.get_realtime_tick(['000001.SZ', '600000.SH'])
    
    assert '000001.SZ' in ticks
    assert 'lastPrice' in ticks['000001.SZ']
```

## 注意事项

1. **QMT环境要求**
   - 需要安装QMT客户端
   - 需要有效的QMT账号
   - Python脚本需要在QMT环境中运行

2. **性能优化**
   - 批量请求优于单个请求
   - 合理使用缓存减少API调用
   - 使用订阅模式而非轮询

3. **错误处理**
   - QMT连接断开时的重连机制
   - API调用失败的重试策略
   - 数据异常的校验和清洗

4. **合规要求**
   - 遵守交易所数据使用规范
   - 注意数据延迟和准确性
   - 合理控制请求频率

---

*本文档由 DeepSearch 团队维护，最后更新于 2025-08-17*