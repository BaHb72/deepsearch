# QMT (迅投) API 参考文档

## 概述

本文档总结了QMT (迅投) 量化交易终端的Python API使用方法，特别是行情数据获取相关的接口。

## 1. 基础导入

```python
from xtquant import xtdata
```

## 2. 订阅行情

### 2.1 订阅单个股票行情

```python
subscribe_quote(
    stock_code,        # 股票代码，如 '600000.SH'
    period='1d',       # 周期，默认日线
    start_time='',     # 开始时间
    end_time='',       # 结束时间
    count=0,           # 数据条数
    callback=None      # 回调函数
)
```

**周期参数 (period) 可选值：**

- `'tick'` - Tick数据（逐笔）
- `'1m'` - 1分钟
- `'5m'` - 5分钟
- `'15m'` - 15分钟
- `'30m'` - 30分钟
- `'1h'` - 1小时
- `'1d'` - 日线
- `'1w'` - 周线
- `'1mon'` - 月线
- `'1q'` - 季线
- `'1hy'` - 半年线
- `'1y'` - 年线

### 2.2 订阅全推行情

```python
subscribe_whole_quote(code_list, callback=None)
```

**参数说明：**

- `code_list`: 可以是市场代码列表（如 `['SH', 'SZ']`）或具体股票代码列表
- `callback`: 数据推送回调函数

### 2.3 回调函数格式

```python
def on_data_callback(datas):
    """
    datas: 字典格式 {stock_code: data_array}
    """
    for stock_code in datas:
        data = datas[stock_code]
        # 处理数据
        print(f"股票: {stock_code}")
        print(f"最新价: {data[-1]['lastPrice']}")
```

### 2.4 取消订阅

```python
# 订阅时获取序列号
seq = subscribe_quote('600000.SH')

# 取消订阅
unsubscribe_quote(seq)
```

## 3. 获取行情数据

### 3.1 获取市场数据

```python
get_market_data(
    field_list=[],     # 字段列表
    stock_list=[],     # 股票列表
    period='1d',       # 周期
    start_time='',     # 开始时间
    end_time='',       # 结束时间
    count=-1,          # 数据条数
    dividend_type='none',  # 除权类型
    fill_data=True     # 是否填充停牌数据
)
```

### 3.2 获取扩展市场数据

```python
get_market_data_ex(
    field_list=[],     # 字段列表
    stock_list=[],     # 股票列表
    period='1d',       # 周期
    start_time='',     # 开始时间
    end_time='',       # 结束时间
    count=-1,          # 数据条数
    dividend_type='none',  # 除权类型
    fill_data=True     # 是否填充停牌数据
)
```

**注意：** `get_market_data_ex` 支持更复杂的数据类型，如ETF、期货等。

### 3.3 获取全推Tick数据

```python
# 获取全市场tick数据
tick_data = get_full_tick(['SH', 'SZ'])

# 获取特定股票tick数据
tick_data = get_full_tick(['600000.SH', '000001.SZ'])
```

### 3.4 获取最新K线数据

```python
get_full_kline(
    field_list=[],     # 字段列表
    stock_list=[],     # 股票列表
    period='1m',       # K线周期
    start_time='',     # 开始时间
    end_time='',       # 结束时间
    count=1,           # 获取数量
    dividend_type='none',  # 除权类型
    fill_data=True     # 是否填充数据
)
```

## 4. 行情数据字段

### 4.1 基础行情字段

- `time` - 时间戳
- `open` - 开盘价
- `high` - 最高价
- `low` - 最低价
- `close` / `lastPrice` - 收盘价/最新价
- `volume` - 成交量
- `amount` - 成交额
- `preClose` - 昨收价

### 4.2 盘口数据字段（Level1 五档）

```python
# 买盘
'bidPrice1', 'bidPrice2', 'bidPrice3', 'bidPrice4', 'bidPrice5'
'bidVol1', 'bidVol2', 'bidVol3', 'bidVol4', 'bidVol5'

# 卖盘
'askPrice1', 'askPrice2', 'askPrice3', 'askPrice4', 'askPrice5'
'askVol1', 'askVol2', 'askVol3', 'askVol4', 'askVol5'
```

### 4.3 Level2 十档行情

```python
# 买盘（1-10档）
'bidPrice1' ... 'bidPrice10'
'bidVol1' ... 'bidVol10'

# 卖盘（1-10档）
'askPrice1' ... 'askPrice10'
'askVol1' ... 'askVol10'
```

## 5. 实际使用示例

### 5.1 获取实时Tick数据

```python
def get_realtime_tick(symbol):
    """获取实时tick数据"""
    tick_data = xtdata.get_market_data_ex(
        stock_list=[symbol],
        period='tick',
        count=1
    )
    
    if tick_data and symbol in tick_data:
        latest_tick = tick_data[symbol].iloc[-1]
        return {
            'symbol': symbol,
            'lastPrice': latest_tick['lastPrice'],
            'volume': latest_tick['volume'],
            'amount': latest_tick['amount'],
            'time': latest_tick['time']
        }
    return None
```

### 5.2 获取五档盘口数据

```python
def get_orderbook(symbol):
    """获取五档盘口数据"""
    fields = []
    for i in range(1, 6):
        fields.extend([
            f'bidPrice{i}', f'bidVol{i}',
            f'askPrice{i}', f'askVol{i}'
        ])
    
    data = xtdata.get_market_data_ex(
        field_list=fields,
        stock_list=[symbol],
        period='tick',
        count=1
    )
    
    if data and symbol in data:
        latest = data[symbol].iloc[-1]
        return {
            'symbol': symbol,
            'bid_prices': [latest.get(f'bidPrice{i}', 0) for i in range(1, 6)],
            'bid_volumes': [latest.get(f'bidVol{i}', 0) for i in range(1, 6)],
            'ask_prices': [latest.get(f'askPrice{i}', 0) for i in range(1, 6)],
            'ask_volumes': [latest.get(f'askVol{i}', 0) for i in range(1, 6)]
        }
    return None
```

### 5.3 订阅实时推送

```python
class RealTimeQuoteHandler:
    def __init__(self):
        self.latest_data = {}
    
    def on_quote_update(self, datas):
        """处理实时推送数据"""
        for stock_code in datas:
            self.latest_data[stock_code] = datas[stock_code]
            # 处理数据，如发送到服务器
            self.process_quote(stock_code, datas[stock_code])
    
    def process_quote(self, stock_code, quote_data):
        """处理单个股票的行情数据"""
        if len(quote_data) > 0:
            latest = quote_data[-1]
            print(f"{stock_code}: 最新价={latest['lastPrice']}, "
                  f"成交量={latest['volume']}")
    
    def subscribe_stocks(self, stock_list):
        """订阅多个股票"""
        for stock in stock_list:
            xtdata.subscribe_quote(
                stock_code=stock,
                period='tick',
                callback=self.on_quote_update
            )

# 使用示例
handler = RealTimeQuoteHandler()
handler.subscribe_stocks(['600000.SH', '000001.SZ'])

# 保持程序运行以接收推送
xtdata.run()
```

### 5.4 获取逐笔成交数据

```python
def get_tick_trades(symbol):
    """获取逐笔成交数据"""
    trades = xtdata.get_market_data(
        stock_list=[symbol],
        period='l2transaction',  # Level2逐笔成交
        count=100  # 获取最近100笔
    )
    
    if trades and symbol in trades:
        return trades[symbol]
    return None
```

## 6. 注意事项

1. **连接管理**：使用QMT API前需要确保QMT客户端已登录
2. **数据权限**：Level2数据需要相应的数据权限
3. **性能优化**：
    - 批量订阅优于单个订阅
    - 使用回调函数处理实时数据比轮询更高效
    - 合理设置数据获取的count参数避免获取过多历史数据
4. **错误处理**：
   ```python
   try:
       data = xtdata.get_market_data_ex(...)
   except Exception as e:
       print(f"获取数据失败: {e}")
   ```

## 7. 调试技巧

1. **检查连接状态**

```python
# 测试是否能获取数据
test_data = xtdata.get_market_data(
    stock_list=['000001.SZ'],
    period='1d',
    count=1
)
if test_data:
    print("连接正常")
else:
    print("连接异常")
```

2. **打印数据结构**

```python
# 查看返回数据的结构
import pandas as pd
data = xtdata.get_market_data_ex(...)
if data:
    for stock, df in data.items():
        print(f"股票: {stock}")
        print(f"字段: {df.columns.tolist()}")
        print(f"数据示例:\n{df.head()}")
```

## 8. 常见问题

**Q: 为什么收不到实时推送？**
A: 检查：

- 是否正确设置了callback函数
- 是否调用了`xtdata.run()`保持程序运行
- QMT客户端是否已登录并有相应权限

**Q: get_market_data和get_market_data_ex的区别？**
A:

- `get_market_data`: 基础行情数据获取
- `get_market_data_ex`: 扩展功能，支持更多数据类型和字段

**Q: 如何获取Level2数据？**
A: 需要Level2数据权限，使用period='l2quote'或'l2transaction'

## 更新日志

- 2024-08-16: 初始版本，基于QMT API文档整理