# 星耀数智（AmazingData）API接口参考文档

## 版本信息
- SDK版本：1.0.9
- 文档版本：1.0.0
- 更新日期：2025-01-15
- 服务地址：120.86.124.106:8600

## 目录
1. [快速开始](#快速开始)
2. [认证接口](#认证接口)
3. [基础数据接口](#基础数据接口)
4. [市场数据接口](#市场数据接口)
5. [财务数据接口](#财务数据接口)
6. [股东数据接口](#股东数据接口)
7. [特色数据接口](#特色数据接口)
8. [订阅接口](#订阅接口)
9. [错误码](#错误码)

---

## 快速开始

### 安装SDK

```bash
# 安装AmazingData SDK
pip install installer/AmazingData-1.0.9-cp313-none-any.whl
```

### 基本使用流程

```python
import AmazingData as ad

# 步骤1：登录认证
ad.login(
    username='your_username',
    password='your_password',
    host='120.86.124.106',
    port=8600
)

# 步骤2：实例化数据类
base_data = ad.BaseData()
market_data = ad.MarketData()
info_data = ad.InfoData()

# 步骤3：调用接口获取数据
code_list = base_data.get_code_list(security_type='EXTRA_STOCK_A')
kline_data = market_data.get_kline_data(['000001'], period=ad.constant.Period.day.value)
```

---

## 认证接口

### ad.login

**功能描述**：登录星耀数智服务，所有数据接口调用前必须先登录。

**函数签名**：
```python
ad.login(username: str, password: str, host: str, port: int) -> int
```

**参数说明**：
| 参数 | 类型 | 必需 | 描述 | 示例 |
|------|------|------|------|------|
| username | str | 是 | 用户名 | 'user001' |
| password | str | 是 | 密码 | 'pass123' |
| host | str | 是 | 服务器地址 | '120.86.124.106' |
| port | int | 是 | 端口号 | 8600 |

**返回值**：
- `0` 或 `True`：登录成功
- 其他错误码：登录失败

**示例代码**：
```python
import AmazingData as ad

# 登录
result = ad.login(
    username='your_username',
    password='your_password',
    host='120.86.124.106',
    port=8600
)

if result == 0 or result is True:
    print("登录成功")
else:
    print(f"登录失败，错误码：{result}")
```

### ad.logout

**功能描述**：登出星耀数智服务。

**函数签名**：
```python
ad.logout() -> None
```

**示例代码**：
```python
# 使用完毕后登出
ad.logout()
```

---

## 基础数据接口

### BaseData.get_code_list

**功能描述**：获取指定类型的证券代码列表。

**函数签名**：
```python
BaseData.get_code_list(security_type: str) -> List[str]
```

**参数说明**：
| 参数 | 类型 | 必需 | 描述 | 可选值 |
|------|------|------|------|--------|
| security_type | str | 是 | 证券类型 | 'EXTRA_STOCK_A'(A股)<br>'EXTRA_ETF'(ETF)<br>'EXTRA_KZZ'(可转债)<br>'EXTRA_HKT'(港股通)<br>'EXTRA_INDEX'(指数)<br>'EXTRA_FUTURE'(期货)<br>'EXTRA_OPTION'(期权) |

**返回值**：
- `List[str]`：证券代码列表，如 ['000001', '000002', '600000']

**示例代码**：
```python
base_data = ad.BaseData()

# 获取所有A股代码
stock_list = base_data.get_code_list(security_type='EXTRA_STOCK_A')
print(f"A股数量：{len(stock_list)}")
print(f"前10个：{stock_list[:10]}")

# 获取所有ETF代码
etf_list = base_data.get_code_list(security_type='EXTRA_ETF')
print(f"ETF数量：{len(etf_list)}")
```

### BaseData.get_trading_calendar

**功能描述**：获取交易日历。

**函数签名**：
```python
BaseData.get_trading_calendar(start_date: str, end_date: str) -> List[str]
```

**参数说明**：
| 参数 | 类型 | 必需 | 描述 | 格式 |
|------|------|------|------|------|
| start_date | str | 是 | 开始日期 | 'YYYYMMDD' |
| end_date | str | 是 | 结束日期 | 'YYYYMMDD' |

**返回值**：
- `List[str]`：交易日期列表

**示例代码**：
```python
base_data = ad.BaseData()

# 获取2025年1月的交易日
trading_days = base_data.get_trading_calendar('20250101', '20250131')
print(f"2025年1月交易日：{trading_days}")
```

### BaseData.get_stock_info

**功能描述**：获取股票基本信息。

**函数签名**：
```python
BaseData.get_stock_info(code_list: List[str]) -> Dict[str, Dict]
```

**参数说明**：
| 参数 | 类型 | 必需 | 描述 | 示例 |
|------|------|------|------|------|
| code_list | List[str] | 是 | 股票代码列表 | ['000001', '600000'] |

**返回值**：
```python
{
    '000001': {
        'name': '平安银行',
        'market': 'SZ',
        'list_date': '19910403',
        'industry': '银行',
        'sector': '金融'
    }
}
```

---

## 市场数据接口

### MarketData.get_kline_data

**功能描述**：获取K线数据，支持多种周期和复权方式。

**函数签名**：
```python
MarketData.get_kline_data(
    code_list: List[str],
    period: int,
    start_date: str = '',
    end_date: str = '',
    count: int = 0,
    adjust: int = ad.constant.Adjust.none.value,
    fill_paused: bool = True
) -> Dict[str, List[Dict]]
```

**参数说明**：
| 参数 | 类型 | 必需 | 描述 | 可选值/示例 |
|------|------|------|------|-------------|
| code_list | List[str] | 是 | 股票代码列表 | ['000001'] |
| period | int | 是 | K线周期 | ad.constant.Period.day.value(日线)<br>ad.constant.Period.m1.value(1分钟)<br>ad.constant.Period.m5.value(5分钟)<br>ad.constant.Period.m15.value(15分钟)<br>ad.constant.Period.m30.value(30分钟)<br>ad.constant.Period.m60.value(60分钟)<br>ad.constant.Period.week.value(周线)<br>ad.constant.Period.month.value(月线) |
| start_date | str | 否 | 开始日期 | '20250101' 或 '2025-01-01 09:30:00' |
| end_date | str | 否 | 结束日期 | '20250115' 或 '2025-01-15 15:00:00' |
| count | int | 否 | 数据条数 | 100（获取最近100条） |
| adjust | int | 否 | 复权类型 | ad.constant.Adjust.none.value(不复权)<br>ad.constant.Adjust.forward.value(前复权)<br>ad.constant.Adjust.backward.value(后复权) |
| fill_paused | bool | 否 | 是否填充停牌数据 | True |

**返回值**：
```python
{
    '000001': [
        {
            'time': '2025-01-15 00:00:00',
            'open': 10.50,
            'high': 10.80,
            'low': 10.45,
            'close': 10.75,
            'volume': 1234567,
            'amount': 13456789.0,
            'turnover': 1.23,  # 换手率
            'change': 0.25,    # 涨跌额
            'change_rate': 2.38  # 涨跌幅
        }
    ]
}
```

**示例代码**：
```python
market_data = ad.MarketData()

# 获取日线数据（按日期范围）
daily_data = market_data.get_kline_data(
    code_list=['000001', '600000'],
    period=ad.constant.Period.day.value,
    start_date='20250101',
    end_date='20250115',
    adjust=ad.constant.Adjust.forward.value  # 前复权
)

# 获取最近100条5分钟K线
minute_data = market_data.get_kline_data(
    code_list=['000001'],
    period=ad.constant.Period.m5.value,
    count=100
)
```

### MarketData.get_snapshot

**功能描述**：获取股票实时快照行情。

**函数签名**：
```python
MarketData.get_snapshot(code_list: List[str]) -> Dict[str, Dict]
```

**参数说明**：
| 参数 | 类型 | 必需 | 描述 | 示例 |
|------|------|------|------|------|
| code_list | List[str] | 是 | 股票代码列表 | ['000001', '600000'] |

**返回值**：
```python
{
    '000001': {
        'name': '平安银行',
        'time': '2025-01-15 15:00:00',
        'last_price': 10.75,
        'open': 10.50,
        'high': 10.80,
        'low': 10.45,
        'prev_close': 10.50,
        'volume': 1234567,
        'amount': 13456789.0,
        'bid1': 10.74,
        'bid1_volume': 1000,
        'bid2': 10.73,
        'bid2_volume': 2000,
        'bid3': 10.72,
        'bid3_volume': 3000,
        'bid4': 10.71,
        'bid4_volume': 4000,
        'bid5': 10.70,
        'bid5_volume': 5000,
        'ask1': 10.75,
        'ask1_volume': 1000,
        'ask2': 10.76,
        'ask2_volume': 2000,
        'ask3': 10.77,
        'ask3_volume': 3000,
        'ask4': 10.78,
        'ask4_volume': 4000,
        'ask5': 10.79,
        'ask5_volume': 5000,
        'change': 0.25,
        'change_percent': 2.38,
        'turnover': 1.23,
        'amplitude': 3.33,
        'limit_up': 11.55,
        'limit_down': 9.45,
        'status': 'TRADING'  # TRADING(交易中), HALT(停牌), DELISTED(退市)
    }
}
```

**示例代码**：
```python
market_data = ad.MarketData()

# 获取实时行情
snapshot = market_data.get_snapshot(['000001', '600000', '000002'])

for code, data in snapshot.items():
    print(f"{code} {data['name']}: {data['last_price']} ({data['change_percent']}%)")
```

### MarketData.get_tick

**功能描述**：获取逐笔成交数据（需要Level2权限）。

**函数签名**：
```python
MarketData.get_tick(
    code: str,
    start_time: str = '',
    end_time: str = '',
    count: int = 0
) -> List[Dict]
```

**参数说明**：
| 参数 | 类型 | 必需 | 描述 | 示例 |
|------|------|------|------|------|
| code | str | 是 | 股票代码 | '000001' |
| start_time | str | 否 | 开始时间 | '2025-01-15 09:30:00' |
| end_time | str | 否 | 结束时间 | '2025-01-15 15:00:00' |
| count | int | 否 | 数据条数 | 1000 |

**返回值**：
```python
[
    {
        'time': '2025-01-15 09:30:01.123',
        'price': 10.75,
        'volume': 100,
        'amount': 1075.0,
        'direction': 'B',  # B(买入), S(卖出), N(中性)
        'order_type': 'LIMIT'  # LIMIT(限价), MARKET(市价)
    }
]
```

---

## 财务数据接口

### InfoData.get_balance_sheet

**功能描述**：获取资产负债表数据。

**函数签名**：
```python
InfoData.get_balance_sheet(
    code_list: List[str],
    report_date: str = ''
) -> Dict[str, List[Dict]]
```

**参数说明**：
| 参数 | 类型 | 必需 | 描述 | 示例 |
|------|------|------|------|------|
| code_list | List[str] | 是 | 股票代码列表 | ['000001'] |
| report_date | str | 否 | 报告期 | '2024Q3' 或 '20240930' |

**返回值**：
```python
{
    '000001': [
        {
            'report_date': '2024-09-30',
            'announce_date': '2024-10-25',
            'total_assets': 123456789.0,  # 总资产
            'total_liabilities': 98765432.0,  # 总负债
            'total_equity': 24691357.0,  # 所有者权益
            'current_assets': 45678901.0,  # 流动资产
            'non_current_assets': 77777888.0,  # 非流动资产
            'current_liabilities': 34567890.0,  # 流动负债
            'non_current_liabilities': 64197542.0  # 非流动负债
        }
    ]
}
```

### InfoData.get_income_statement

**功能描述**：获取利润表数据。

**函数签名**：
```python
InfoData.get_income_statement(
    code_list: List[str],
    report_date: str = ''
) -> Dict[str, List[Dict]]
```

**参数说明**：
| 参数 | 类型 | 必需 | 描述 | 示例 |
|------|------|------|------|------|
| code_list | List[str] | 是 | 股票代码列表 | ['000001'] |
| report_date | str | 否 | 报告期 | '2024Q3' |

**返回值**：
```python
{
    '000001': [
        {
            'report_date': '2024-09-30',
            'announce_date': '2024-10-25',
            'revenue': 12345678.0,  # 营业收入
            'operating_profit': 3456789.0,  # 营业利润
            'total_profit': 3567890.0,  # 利润总额
            'net_profit': 2345678.0,  # 净利润
            'eps': 0.35,  # 每股收益
            'gross_margin': 35.67,  # 毛利率
            'net_margin': 19.01  # 净利率
        }
    ]
}
```

### InfoData.get_cash_flow

**功能描述**：获取现金流量表数据。

**函数签名**：
```python
InfoData.get_cash_flow(
    code_list: List[str],
    report_date: str = ''
) -> Dict[str, List[Dict]]
```

**返回值**：
```python
{
    '000001': [
        {
            'report_date': '2024-09-30',
            'operating_cash_flow': 5678901.0,  # 经营活动现金流
            'investing_cash_flow': -2345678.0,  # 投资活动现金流
            'financing_cash_flow': -1234567.0,  # 筹资活动现金流
            'net_cash_flow': 2098656.0  # 现金净流量
        }
    ]
}
```

### InfoData.get_key_indicators

**功能描述**：获取主要财务指标。

**函数签名**：
```python
InfoData.get_key_indicators(
    code_list: List[str],
    report_date: str = ''
) -> Dict[str, List[Dict]]
```

**返回值**：
```python
{
    '000001': [
        {
            'report_date': '2024-09-30',
            'roa': 1.23,  # 总资产收益率
            'roe': 15.67,  # 净资产收益率
            'eps': 0.35,  # 每股收益
            'bps': 5.67,  # 每股净资产
            'gross_margin': 35.67,  # 毛利率
            'net_margin': 19.01,  # 净利率
            'debt_ratio': 65.43,  # 资产负债率
            'current_ratio': 1.32,  # 流动比率
            'quick_ratio': 1.15,  # 速动比率
            'inventory_turnover': 8.5,  # 存货周转率
            'receivable_turnover': 12.3  # 应收账款周转率
        }
    ]
}
```

---

## 股东数据接口

### InfoData.get_top10_holders

**功能描述**：获取十大股东信息。

**函数签名**：
```python
InfoData.get_top10_holders(
    code_list: List[str],
    report_date: str = ''
) -> Dict[str, List[Dict]]
```

**返回值**：
```python
{
    '000001': [
        {
            'holder_name': '中国平安保险(集团)股份有限公司',
            'hold_num': 9618540142,  # 持股数量
            'hold_ratio': 49.56,  # 持股比例(%)
            'change_num': 0,  # 变动数量
            'change_ratio': 0  # 变动比例(%)
        }
    ]
}
```

### InfoData.get_top10_tradable_holders

**功能描述**：获取十大流通股东信息。

**函数签名**：
```python
InfoData.get_top10_tradable_holders(
    code_list: List[str],
    report_date: str = ''
) -> Dict[str, List[Dict]]
```

### InfoData.get_holder_num

**功能描述**：获取股东户数信息。

**函数签名**：
```python
InfoData.get_holder_num(
    code_list: List[str],
    report_date: str = ''
) -> Dict[str, Dict]
```

**返回值**：
```python
{
    '000001': {
        'holder_num': 286543,  # 股东户数
        'avg_hold': 67890,  # 户均持股数
        'change_num': -5432,  # 股东户数变动
        'change_ratio': -1.86  # 变动比例(%)
    }
}
```

---

## 特色数据接口

### InfoData.get_dragon_tiger

**功能描述**：获取龙虎榜数据。

**函数签名**：
```python
InfoData.get_dragon_tiger(
    code: str,
    start_date: str = '',
    end_date: str = ''
) -> List[Dict]
```

**返回值**：
```python
[
    {
        'trade_date': '2025-01-15',
        'code': '000001',
        'name': '平安银行',
        'reason': '日涨幅偏离值达7%',
        'buy_amount': 123456789.0,  # 买入金额
        'sell_amount': 98765432.0,  # 卖出金额
        'net_amount': 24691357.0,  # 净买入
        'buy_list': [  # 买入席位
            {
                'rank': 1,
                'broker': '机构专用',
                'amount': 45678901.0
            }
        ],
        'sell_list': [  # 卖出席位
            {
                'rank': 1,
                'broker': '机构专用',
                'amount': 34567890.0
            }
        ]
    }
]
```

### InfoData.get_margin_trading

**功能描述**：获取融资融券数据。

**函数签名**：
```python
InfoData.get_margin_trading(
    code_list: List[str],
    start_date: str = '',
    end_date: str = ''
) -> Dict[str, List[Dict]]
```

**返回值**：
```python
{
    '000001': [
        {
            'trade_date': '2025-01-15',
            'fin_balance': 987654321.0,  # 融资余额
            'fin_buy': 12345678.0,  # 融资买入
            'fin_repay': 9876543.0,  # 融资偿还
            'sec_balance': 123456.0,  # 融券余额
            'sec_sell': 54321.0,  # 融券卖出
            'sec_repay': 43210.0,  # 融券偿还
            'fin_sec_ratio': 8000.5  # 融资融券比
        }
    ]
}
```

### InfoData.get_north_flow

**功能描述**：获取北向资金流向数据。

**函数签名**：
```python
InfoData.get_north_flow(
    start_date: str = '',
    end_date: str = ''
) -> List[Dict]
```

**返回值**：
```python
[
    {
        'trade_date': '2025-01-15',
        'sh_flow': 2345678901.0,  # 沪股通流入
        'sz_flow': 1234567890.0,  # 深股通流入
        'total_flow': 3580246791.0,  # 合计流入
        'sh_balance': 52000000000.0,  # 沪股通余额
        'sz_balance': 52000000000.0,  # 深股通余额
        'sh_hold': 987654321000.0,  # 沪股通持股市值
        'sz_hold': 654321098000.0  # 深股通持股市值
    }
]
```

---

## 订阅接口

### SubscribeData 订阅实时数据

**功能描述**：订阅实时推送数据，支持快照、K线、逐笔等多种数据类型。

**基本使用流程**：
```python
import AmazingData as ad

# 步骤1：登录
ad.login(username='username', password='password', host='host', port=port)

# 步骤2：获取股票列表
base_data = ad.BaseData()
code_list = base_data.get_code_list(security_type='EXTRA_STOCK_A')[:10]  # 订阅前10只

# 步骤3：实例化订阅类
sub_data = ad.SubscribeData()

# 步骤4：注册回调函数
@sub_data.register(code_list=code_list, period=ad.constant.Period.snapshot.value)
def on_snapshot(data, period):
    """快照数据回调"""
    print(f"收到快照: {data}")

@sub_data.register(code_list=code_list, period=ad.constant.Period.m1.value)
def on_kline(data, period):
    """K线数据回调"""
    print(f"收到K线: {data}")

# 步骤5：启动订阅
sub_data.run()  # 阻塞运行
```

### 订阅数据类型

| Period枚举值 | 说明 | 数据内容 |
|-------------|------|----------|
| ad.constant.Period.snapshot | 实时快照 | 最新价、买卖盘等 |
| ad.constant.Period.tick | 逐笔成交 | 成交明细 |
| ad.constant.Period.m1 | 1分钟K线 | OHLCV数据 |
| ad.constant.Period.m5 | 5分钟K线 | OHLCV数据 |
| ad.constant.Period.day | 日线 | 日K线数据 |

### 高级订阅示例

```python
import AmazingData as ad
from typing import Union

# 登录
ad.login(username='username', password='password', host='host', port=port)

# 准备订阅列表
base_data = ad.BaseData()
stock_list = ['000001', '000002', '600000']
etf_list = base_data.get_code_list(security_type='EXTRA_ETF')[:5]

# 创建订阅实例
sub_data = ad.SubscribeData()

# 订阅多种数据类型
@sub_data.register(code_list=stock_list, period=ad.constant.Period.snapshot.value)
def on_stock_snapshot(data: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):
    """股票快照回调"""
    if isinstance(data, ad.constant.Snapshot):
        print(f"[股票快照] {data.code}: {data.last_price} ({data.change_percent}%)")

@sub_data.register(code_list=etf_list, period=ad.constant.Period.snapshot.value)
def on_etf_snapshot(data, period):
    """ETF快照回调"""
    print(f"[ETF快照] {data.code}: {data.last_price}")

@sub_data.register(code_list=['000001'], period=ad.constant.Period.tick.value)
def on_tick(data: ad.constant.Tick, period):
    """逐笔成交回调"""
    print(f"[逐笔] {data.code} {data.time}: {data.price} x {data.volume}")

# 启动订阅（阻塞运行）
try:
    sub_data.run()
except KeyboardInterrupt:
    print("订阅已停止")
    sub_data.stop()
```

### 订阅管理

```python
# 停止订阅
sub_data.stop()

# 清理订阅
sub_data.clear()
```

---

## 错误码

### 通用错误码

| 错误码 | 说明 | 处理建议 |
|--------|------|----------|
| 0 | 成功 | - |
| -1 | 未知错误 | 检查日志 |
| -100 | 网络连接失败 | 检查网络和服务器地址 |
| -101 | 连接超时 | 检查网络延迟 |
| -200 | 认证失败 | 检查用户名密码 |
| -201 | 账户已过期 | 联系管理员 |
| -202 | IP未授权 | 添加IP白名单 |
| -300 | 参数错误 | 检查参数格式 |
| -301 | 股票代码无效 | 检查代码是否存在 |
| -302 | 日期格式错误 | 使用YYYYMMDD格式 |
| -400 | 数据不存在 | 检查查询条件 |
| -401 | 无权限访问 | 检查数据权限 |
| -500 | 服务器内部错误 | 稍后重试 |
| -501 | 服务维护中 | 等待维护完成 |

### 订阅错误码

| 错误码 | 说明 | 处理建议 |
|--------|------|----------|
| -600 | 订阅数量超限 | 减少订阅数量 |
| -601 | 订阅类型不支持 | 检查数据类型 |
| -602 | 订阅已存在 | 避免重复订阅 |

---

## 最佳实践

### 1. 错误处理

```python
import AmazingData as ad

try:
    # 登录
    result = ad.login(username='user', password='pass', host='host', port=port)
    if result != 0 and result is not True:
        raise Exception(f"登录失败: {result}")

    # 获取数据
    market_data = ad.MarketData()
    data = market_data.get_kline_data(['000001'], ad.constant.Period.day.value)

except Exception as e:
    print(f"错误: {e}")
finally:
    # 确保登出
    ad.logout()
```

### 2. 批量查询优化

```python
# 推荐：批量查询
codes = ['000001', '000002', '600000', '600036']
data = market_data.get_snapshot(codes)  # 一次查询

# 不推荐：循环单个查询
for code in codes:
    data = market_data.get_snapshot([code])  # 多次查询，效率低
```

### 3. 日期时间格式

```python
# 日期格式
# 日线使用：'YYYYMMDD'
daily_data = market_data.get_kline_data(
    ['000001'],
    ad.constant.Period.day.value,
    start_date='20250101',  # 正确
    end_date='20250115'
)

# 分钟线使用：'YYYY-MM-DD HH:MM:SS'
minute_data = market_data.get_kline_data(
    ['000001'],
    ad.constant.Period.m5.value,
    start_date='2025-01-15 09:30:00',  # 正确
    end_date='2025-01-15 15:00:00'
)
```

### 4. 内存管理

```python
# 大量数据查询时分批处理
import pandas as pd

all_codes = base_data.get_code_list('EXTRA_STOCK_A')
batch_size = 100
all_data = []

for i in range(0, len(all_codes), batch_size):
    batch = all_codes[i:i+batch_size]
    data = market_data.get_snapshot(batch)
    all_data.append(data)

# 合并结果
final_data = {}
for batch in all_data:
    final_data.update(batch)
```

### 5. 订阅数据处理

```python
import queue
import threading

# 创建数据队列
data_queue = queue.Queue()

# 订阅回调：快速入队
@sub_data.register(code_list=codes, period=ad.constant.Period.snapshot.value)
def on_data(data, period):
    data_queue.put((data, period))

# 处理线程：异步处理
def process_data():
    while True:
        try:
            data, period = data_queue.get(timeout=1)
            # 处理数据（存储、计算等）
            process(data)
        except queue.Empty:
            continue

# 启动处理线程
thread = threading.Thread(target=process_data)
thread.daemon = True
thread.start()

# 启动订阅
sub_data.run()
```

---

## 附录

### 常用常量定义

```python
# 周期常量
ad.constant.Period.tick      # 逐笔
ad.constant.Period.snapshot  # 快照
ad.constant.Period.m1        # 1分钟
ad.constant.Period.m5        # 5分钟
ad.constant.Period.m15       # 15分钟
ad.constant.Period.m30       # 30分钟
ad.constant.Period.m60       # 60分钟
ad.constant.Period.day       # 日线
ad.constant.Period.week      # 周线
ad.constant.Period.month     # 月线

# 复权类型
ad.constant.Adjust.none      # 不复权
ad.constant.Adjust.forward   # 前复权
ad.constant.Adjust.backward  # 后复权

# 证券类型
'EXTRA_STOCK_A'   # A股
'EXTRA_ETF'       # ETF
'EXTRA_KZZ'       # 可转债
'EXTRA_HKT'       # 港股通
'EXTRA_INDEX'     # 指数
'EXTRA_FUTURE'    # 期货
'EXTRA_OPTION'    # 期权
```

### 数据更新频率

| 数据类型 | 更新频率 | 延迟 |
|---------|---------|------|
| 实时快照 | 3秒 | <1秒 |
| 逐笔成交 | 实时推送 | <100ms |
| 分钟K线 | 1分钟 | <5秒 |
| 日K线 | 收盘后 | 30分钟内 |
| 财务数据 | 季度/年度 | 公告当日 |
| 股东数据 | 季度 | 公告当日 |
| 龙虎榜 | 每日 | 收盘后2小时 |
| 北向资金 | 每日 | 收盘后1小时 |

---

*文档版本：1.0.0*
*更新日期：2025-01-15*
*技术支持：中国银河证券*