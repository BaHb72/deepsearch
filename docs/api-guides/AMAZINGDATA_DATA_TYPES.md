# 星耀数智（AmazingData）数据类型定义

## 概述

本文档详细说明了星耀数智API中使用的所有数据类型、枚举值和数据结构。

## 目录
1. [枚举类型](#枚举类型)
2. [数据结构](#数据结构)
3. [字段映射](#字段映射)
4. [工具函数](#工具函数)
5. [数据格式规范](#数据格式规范)

---

## 枚举类型

### Period - 数据周期

用于指定K线数据的时间周期或订阅数据类型。

```python
# 导入方式
import AmazingData as ad

# 使用常量
period = ad.constant.Period.day.value
```

| 枚举值 | 说明 | 使用场景 |
|--------|------|----------|
| `ad.constant.Period.tick` | 逐笔数据 | 订阅逐笔成交 |
| `ad.constant.Period.snapshot` | 快照数据 | 订阅实时行情 |
| `ad.constant.Period.m1` | 1分钟 | K线数据 |
| `ad.constant.Period.m5` | 5分钟 | K线数据 |
| `ad.constant.Period.m15` | 15分钟 | K线数据 |
| `ad.constant.Period.m30` | 30分钟 | K线数据 |
| `ad.constant.Period.m60` | 60分钟 | K线数据 |
| `ad.constant.Period.day` | 日线 | K线数据 |
| `ad.constant.Period.week` | 周线 | K线数据 |
| `ad.constant.Period.month` | 月线 | K线数据 |
| `ad.constant.Period.quarter` | 季线 | K线数据 |
| `ad.constant.Period.year` | 年线 | K线数据 |

### Adjust - 复权类型

用于指定K线数据的复权方式。

```python
# 使用示例
adjust = ad.constant.Adjust.forward.value
```

| 枚举值 | 说明 | 描述 |
|--------|------|------|
| `ad.constant.Adjust.none` | 不复权 | 原始价格 |
| `ad.constant.Adjust.forward` | 前复权 | 以当前价为基准向前复权 |
| `ad.constant.Adjust.backward` | 后复权 | 以上市价为基准向后复权 |

### SecurityType - 证券类型

用于指定证券的类型。

```python
# 使用示例
security_type = 'EXTRA_STOCK_A'
```

| 常量字符串 | 说明 | 示例代码 |
|------------|------|----------|
| `'EXTRA_STOCK_A'` | A股 | 000001, 600000 |
| `'EXTRA_ETF'` | ETF基金 | 510050, 159915 |
| `'EXTRA_KZZ'` | 可转债 | 113001, 128001 |
| `'EXTRA_HKT'` | 港股通 | 00700, 00005 |
| `'EXTRA_INDEX'` | 指数 | 000001, 399001 |
| `'EXTRA_FUTURE'` | 期货 | IF2501, IC2501 |
| `'EXTRA_OPTION'` | 期权 | 10004720 |

### Market - 市场代码

股票市场标识。

| 代码 | 说明 | 股票代码特征 |
|------|------|-------------|
| `'SH'` | 上海证券交易所 | 60开头、68开头（科创板） |
| `'SZ'` | 深圳证券交易所 | 00开头、30开头（创业板） |
| `'BJ'` | 北京证券交易所 | 8开头、4开头 |
| `'HK'` | 香港交易所 | 5位数字 |

### TradingStatus - 交易状态

股票的交易状态。

| 状态值 | 说明 | 描述 |
|--------|------|------|
| `'TRADING'` | 正常交易 | 可以买卖 |
| `'HALT'` | 停牌 | 暂停交易 |
| `'DELISTED'` | 退市 | 已退市 |
| `'SUSPENSION'` | 暂停上市 | 暂停上市状态 |

---

## 数据结构

### KlineData - K线数据

K线数据的标准格式。

```python
{
    'time': '2025-01-15 00:00:00',  # 时间
    'open': 10.50,                  # 开盘价
    'high': 10.80,                  # 最高价
    'low': 10.45,                   # 最低价
    'close': 10.75,                 # 收盘价
    'volume': 1234567,              # 成交量（股）
    'amount': 13456789.0,           # 成交额（元）
    'turnover': 1.23,               # 换手率（%）
    'change': 0.25,                 # 涨跌额
    'change_rate': 2.38,            # 涨跌幅（%）
    'adjust_factor': 1.0            # 复权因子
}
```

### SnapshotData - 快照数据

实时行情快照数据结构。

```python
{
    'code': '000001',               # 股票代码
    'name': '平安银行',              # 股票名称
    'time': '2025-01-15 15:00:00',  # 时间
    'last_price': 10.75,            # 最新价
    'open': 10.50,                  # 开盘价
    'high': 10.80,                  # 最高价
    'low': 10.45,                   # 最低价
    'prev_close': 10.50,            # 昨收价
    'volume': 1234567,              # 成交量
    'amount': 13456789.0,           # 成交额

    # 五档买卖盘
    'bid1': 10.74,                  # 买一价
    'bid1_volume': 1000,            # 买一量
    'bid2': 10.73,
    'bid2_volume': 2000,
    'bid3': 10.72,
    'bid3_volume': 3000,
    'bid4': 10.71,
    'bid4_volume': 4000,
    'bid5': 10.70,
    'bid5_volume': 5000,

    'ask1': 10.75,                  # 卖一价
    'ask1_volume': 1000,            # 卖一量
    'ask2': 10.76,
    'ask2_volume': 2000,
    'ask3': 10.77,
    'ask3_volume': 3000,
    'ask4': 10.78,
    'ask4_volume': 4000,
    'ask5': 10.79,
    'ask5_volume': 5000,

    # 涨跌信息
    'change': 0.25,                 # 涨跌额
    'change_percent': 2.38,         # 涨跌幅（%）
    'amplitude': 3.33,              # 振幅（%）
    'turnover': 1.23,               # 换手率（%）

    # 涨跌停价
    'limit_up': 11.55,              # 涨停价
    'limit_down': 9.45,             # 跌停价

    'status': 'TRADING'             # 交易状态
}
```

### TickData - 逐笔成交数据

Level2逐笔成交数据结构。

```python
{
    'code': '000001',                    # 股票代码
    'time': '2025-01-15 09:30:01.123',  # 成交时间（精确到毫秒）
    'price': 10.75,                      # 成交价
    'volume': 100,                       # 成交量
    'amount': 1075.0,                    # 成交额
    'direction': 'B',                    # 买卖方向：B(买)、S(卖)、N(中性)
    'order_type': 'LIMIT',               # 订单类型：LIMIT(限价)、MARKET(市价)
    'trade_id': '202501150930010001'     # 成交编号
}
```

### FinancialData - 财务数据基础结构

财务报表的通用数据结构。

```python
{
    'report_date': '2024-09-30',    # 报告期
    'announce_date': '2024-10-25',  # 公告日期
    'currency': 'CNY',              # 币种
    'accounting_standard': 'CAS',   # 会计准则
    # 具体指标根据报表类型而定
}
```

#### BalanceSheet - 资产负债表

```python
{
    'report_date': '2024-09-30',
    'announce_date': '2024-10-25',

    # 资产类
    'total_assets': 123456789.0,           # 总资产
    'current_assets': 45678901.0,          # 流动资产
    'non_current_assets': 77777888.0,      # 非流动资产
    'cash': 12345678.0,                    # 货币资金
    'accounts_receivable': 9876543.0,      # 应收账款
    'inventory': 5432109.0,                # 存货
    'fixed_assets': 34567890.0,            # 固定资产

    # 负债类
    'total_liabilities': 98765432.0,       # 总负债
    'current_liabilities': 34567890.0,     # 流动负债
    'non_current_liabilities': 64197542.0, # 非流动负债
    'short_term_loan': 12345678.0,         # 短期借款
    'long_term_loan': 45678901.0,          # 长期借款
    'accounts_payable': 8765432.0,         # 应付账款

    # 所有者权益
    'total_equity': 24691357.0,            # 所有者权益
    'paid_in_capital': 10000000.0,         # 实收资本
    'capital_reserve': 5000000.0,          # 资本公积
    'retained_earnings': 9691357.0         # 未分配利润
}
```

#### IncomeStatement - 利润表

```python
{
    'report_date': '2024-09-30',
    'announce_date': '2024-10-25',

    # 收入类
    'revenue': 12345678.0,                 # 营业收入
    'operating_revenue': 12000000.0,       # 主营业务收入
    'other_revenue': 345678.0,             # 其他业务收入

    # 成本费用类
    'operating_cost': 8000000.0,           # 营业成本
    'sales_expense': 500000.0,             # 销售费用
    'management_expense': 800000.0,        # 管理费用
    'financial_expense': 200000.0,         # 财务费用
    'rd_expense': 600000.0,                # 研发费用

    # 利润类
    'operating_profit': 3456789.0,         # 营业利润
    'total_profit': 3567890.0,             # 利润总额
    'net_profit': 2345678.0,               # 净利润
    'net_profit_after': 2145678.0,         # 扣非净利润

    # 每股指标
    'eps': 0.35,                           # 基本每股收益
    'diluted_eps': 0.34                    # 稀释每股收益
}
```

#### CashFlow - 现金流量表

```python
{
    'report_date': '2024-09-30',
    'announce_date': '2024-10-25',

    # 经营活动
    'operating_cash_flow': 5678901.0,      # 经营活动现金流净额
    'operating_cash_inflow': 12345678.0,   # 经营活动现金流入
    'operating_cash_outflow': 6666777.0,   # 经营活动现金流出

    # 投资活动
    'investing_cash_flow': -2345678.0,     # 投资活动现金流净额
    'investing_cash_inflow': 1234567.0,    # 投资活动现金流入
    'investing_cash_outflow': 3580245.0,   # 投资活动现金流出

    # 筹资活动
    'financing_cash_flow': -1234567.0,     # 筹资活动现金流净额
    'financing_cash_inflow': 5000000.0,    # 筹资活动现金流入
    'financing_cash_outflow': 6234567.0,   # 筹资活动现金流出

    # 汇总
    'net_cash_flow': 2098656.0,            # 现金净流量
    'begin_cash': 10000000.0,              # 期初现金
    'end_cash': 12098656.0                 # 期末现金
}
```

### KeyIndicators - 主要财务指标

```python
{
    'report_date': '2024-09-30',

    # 盈利能力
    'roe': 15.67,                  # 净资产收益率（%）
    'roa': 1.23,                   # 总资产收益率（%）
    'gross_margin': 35.67,         # 毛利率（%）
    'net_margin': 19.01,           # 净利率（%）
    'operating_margin': 28.01,     # 营业利润率（%）

    # 每股指标
    'eps': 0.35,                   # 每股收益
    'bps': 5.67,                   # 每股净资产
    'cfps': 0.45,                  # 每股现金流
    'dps': 0.10,                   # 每股股利

    # 偿债能力
    'current_ratio': 1.32,         # 流动比率
    'quick_ratio': 1.15,           # 速动比率
    'debt_ratio': 65.43,           # 资产负债率（%）
    'equity_ratio': 34.57,         # 产权比率（%）

    # 营运能力
    'inventory_turnover': 8.5,     # 存货周转率
    'receivable_turnover': 12.3,   # 应收账款周转率
    'asset_turnover': 0.85,        # 总资产周转率
    'fixed_asset_turnover': 3.2,   # 固定资产周转率

    # 成长能力
    'revenue_growth': 12.5,        # 营收增长率（%）
    'profit_growth': 15.8,         # 净利润增长率（%）
    'asset_growth': 10.2,          # 总资产增长率（%）
    'equity_growth': 8.5           # 净资产增长率（%）
}
```

### ShareholderData - 股东数据

```python
{
    'report_date': '2024-09-30',

    # 股东统计
    'holder_num': 286543,          # 股东总数
    'avg_hold': 67890,             # 户均持股数
    'holder_change': -5432,        # 股东数变动
    'holder_change_ratio': -1.86,  # 股东数变动比例（%）

    # 十大股东
    'top10_holders': [
        {
            'rank': 1,                              # 排名
            'holder_name': '中国平安保险(集团)',     # 股东名称
            'hold_num': 9618540142,                 # 持股数量
            'hold_ratio': 49.56,                    # 持股比例（%）
            'hold_change': 0,                       # 持股变动
            'holder_type': '企业法人',              # 股东类型
            'is_locked': False                      # 是否限售
        }
    ],

    # 十大流通股东
    'top10_tradable': [
        {
            'rank': 1,
            'holder_name': '香港中央结算公司',
            'hold_num': 1234567890,
            'hold_ratio': 6.35,
            'hold_change': 123456,
            'holder_type': '其他'
        }
    ],

    # 机构持股
    'institution_num': 156,                # 机构数量
    'institution_hold': 5432109876,        # 机构持股数
    'institution_ratio': 28.0              # 机构持股比例（%）
}
```

### DragonTigerData - 龙虎榜数据

```python
{
    'trade_date': '2025-01-15',
    'code': '000001',
    'name': '平安银行',

    # 上榜信息
    'reason': '日涨幅偏离值达7%',           # 上榜原因
    'close_price': 10.75,                   # 收盘价
    'change_percent': 10.02,                # 涨跌幅（%）

    # 成交统计
    'buy_amount': 123456789.0,              # 买入总额
    'sell_amount': 98765432.0,              # 卖出总额
    'net_amount': 24691357.0,               # 净买入额

    # 买入席位（前5）
    'buy_list': [
        {
            'rank': 1,                       # 排名
            'broker': '机构专用',             # 营业部名称
            'amount': 45678901.0,            # 买入金额
            'ratio': 37.0                   # 占总成交比例（%）
        }
    ],

    # 卖出席位（前5）
    'sell_list': [
        {
            'rank': 1,
            'broker': '机构专用',
            'amount': 34567890.0,
            'ratio': 35.0
        }
    ]
}
```

### MarginTradingData - 融资融券数据

```python
{
    'trade_date': '2025-01-15',
    'code': '000001',

    # 融资数据
    'fin_balance': 987654321.0,      # 融资余额
    'fin_buy': 12345678.0,           # 融资买入额
    'fin_repay': 9876543.0,          # 融资偿还额
    'fin_net': 2469135.0,            # 融资净买入

    # 融券数据
    'sec_balance': 123456.0,         # 融券余额（股）
    'sec_balance_amount': 1327704.0, # 融券余额（金额）
    'sec_sell': 54321.0,             # 融券卖出量
    'sec_repay': 43210.0,            # 融券偿还量
    'sec_net': 11111.0,              # 融券净卖出

    # 融资融券合计
    'total_balance': 988981925.0,    # 两融余额
    'fin_sec_ratio': 8000.5          # 融资融券比
}
```

### NorthFlowData - 北向资金数据

```python
{
    'trade_date': '2025-01-15',

    # 沪股通
    'sh_buy': 12345678901.0,         # 沪股通买入额
    'sh_sell': 10000000000.0,        # 沪股通卖出额
    'sh_flow': 2345678901.0,         # 沪股通净流入
    'sh_balance': 52000000000.0,     # 沪股通余额
    'sh_hold': 987654321000.0,       # 沪股通持股市值

    # 深股通
    'sz_buy': 9876543210.0,          # 深股通买入额
    'sz_sell': 8641975320.0,         # 深股通卖出额
    'sz_flow': 1234567890.0,         # 深股通净流入
    'sz_balance': 52000000000.0,     # 深股通余额
    'sz_hold': 654321098000.0,       # 深股通持股市值

    # 合计
    'total_buy': 22222222111.0,      # 总买入额
    'total_sell': 18641975320.0,     # 总卖出额
    'total_flow': 3580246791.0,      # 总净流入
    'total_hold': 1641975419000.0,   # 总持股市值

    # 累计
    'accumulated_flow': 876543210000.0  # 累计净流入
}
```

---

## 字段映射

### 系统字段与AmazingData字段对照表

为了保持系统内部的一致性，需要进行字段映射。

#### K线数据字段映射

| 系统字段 | AmazingData字段 | 说明 |
|---------|----------------|------|
| datetime | time | 时间 |
| open | open | 开盘价 |
| high | high | 最高价 |
| low | low | 最低价 |
| close | close | 收盘价 |
| volume | volume | 成交量 |
| amount | amount | 成交额 |
| turnover_rate | turnover | 换手率 |
| change | change | 涨跌额 |
| change_percent | change_rate | 涨跌幅 |

#### 快照数据字段映射

| 系统字段 | AmazingData字段 | 说明 |
|---------|----------------|------|
| symbol | code | 股票代码 |
| name | name | 股票名称 |
| last | last_price | 最新价 |
| prev_close | pre_close | 昨收价 |
| change_percent | change_percent | 涨跌幅 |

#### 财务数据字段映射

| 系统字段 | AmazingData字段 | 说明 |
|---------|----------------|------|
| roa | roa | 总资产收益率 |
| roe | roe | 净资产收益率 |
| eps | eps | 每股收益 |
| bvps | bps | 每股净资产 |
| gross_profit_margin | gross_margin | 毛利率 |
| net_profit_margin | net_margin | 净利率 |
| asset_liability_ratio | debt_ratio | 资产负债率 |

#### 融资融券字段映射

| 系统字段 | AmazingData字段 | 说明 |
|---------|----------------|------|
| margin_balance | fin_balance | 融资余额 |
| margin_buy | fin_buy | 融资买入 |
| margin_repay | fin_repay | 融资偿还 |
| short_balance | sec_balance | 融券余额 |
| short_sell | sec_sell | 融券卖出 |
| short_repay | sec_repay | 融券偿还 |
| margin_ratio | fin_sec_ratio | 融资融券比 |

#### 北向资金字段映射

| 系统字段 | AmazingData字段 | 说明 |
|---------|----------------|------|
| shanghai_flow | sh_flow | 沪股通流入 |
| shenzhen_flow | sz_flow | 深股通流入 |
| total_flow | total_flow | 总流入 |
| shanghai_balance | sh_balance | 沪股通余额 |
| shenzhen_balance | sz_balance | 深股通余额 |

---

## 工具函数

### 股票代码处理

```python
def parse_symbol(symbol: str) -> tuple:
    """
    解析股票代码，分离代码和市场

    Args:
        symbol: 股票代码，如 '000001' 或 '000001.SZ'

    Returns:
        (code, market) 元组

    Example:
        >>> parse_symbol('000001.SZ')
        ('000001', 'SZ')
        >>> parse_symbol('600000')
        ('600000', 'SH')
    """
    if '.' in symbol:
        code, market = symbol.split('.')
        return code, market
    else:
        # 根据代码判断市场
        if symbol.startswith('60') or symbol.startswith('68'):
            return symbol, 'SH'
        elif symbol.startswith('00') or symbol.startswith('30'):
            return symbol, 'SZ'
        elif symbol.startswith('8') or symbol.startswith('4'):
            return symbol, 'BJ'
        else:
            return symbol, 'SZ'  # 默认深圳

def format_symbol(code: str, market: str = None) -> str:
    """
    格式化股票代码

    Args:
        code: 股票代码
        market: 市场代码

    Returns:
        格式化的股票代码

    Example:
        >>> format_symbol('000001', 'SZ')
        '000001.SZ'
    """
    if market:
        return f"{code}.{market}"
    else:
        _, market = parse_symbol(code)
        return f"{code}.{market}"
```

### 时间格式转换

```python
def convert_period(period: str) -> str:
    """
    转换周期格式

    Args:
        period: 系统周期格式

    Returns:
        AmazingData周期格式

    Example:
        >>> convert_period('1d')
        'day'
    """
    period_map = {
        '1m': 'm1',
        '5m': 'm5',
        '15m': 'm15',
        '30m': 'm30',
        '60m': 'm60',
        '1d': 'day',
        '1w': 'week',
        '1M': 'month'
    }
    return period_map.get(period, period)

def convert_adjust(adjust: str) -> str:
    """
    转换复权类型

    Args:
        adjust: 系统复权类型

    Returns:
        AmazingData复权类型

    Example:
        >>> convert_adjust('qfq')
        'forward'
    """
    adjust_map = {
        'none': 'none',
        'qfq': 'forward',
        'hfq': 'backward'
    }
    return adjust_map.get(adjust, adjust)
```

---

## 数据格式规范

### 日期时间格式

| 数据类型 | 格式 | 示例 | 说明 |
|---------|------|------|------|
| 日期（日线） | YYYYMMDD | 20250115 | 8位数字 |
| 日期（带分隔符） | YYYY-MM-DD | 2025-01-15 | ISO格式 |
| 时间（分钟） | YYYY-MM-DD HH:MM:SS | 2025-01-15 14:30:00 | 精确到秒 |
| 时间（逐笔） | YYYY-MM-DD HH:MM:SS.fff | 2025-01-15 14:30:00.123 | 精确到毫秒 |
| 报告期 | YYYYQN | 2024Q3 | 季度报告 |
| 报告期（年报） | YYYY | 2024 | 年度报告 |

### 数值格式

| 数据类型 | 单位 | 精度 | 示例 |
|---------|------|------|------|
| 价格 | 元 | 2位小数 | 10.75 |
| 成交量 | 股 | 整数 | 1234567 |
| 成交额 | 元 | 2位小数 | 13456789.00 |
| 百分比 | % | 2位小数 | 12.34 |
| 财务金额 | 元 | 2位小数 | 123456789.00 |
| 市值 | 元 | 0位小数 | 987654321000 |

### 股票代码格式

| 市场 | 代码长度 | 示例 | 说明 |
|------|---------|------|------|
| A股 | 6位 | 000001, 600000 | 纯数字 |
| ETF | 6位 | 510050, 159915 | 纯数字 |
| 可转债 | 6位 | 113001, 128001 | 纯数字 |
| 港股 | 5位 | 00700, 00005 | 纯数字，前面补0 |
| 指数 | 6位 | 000001, 399001 | 纯数字 |

### 布尔值

| 值 | 说明 |
|----|------|
| True/1 | 是、真、启用 |
| False/0 | 否、假、禁用 |

### 空值处理

| 数据类型 | 空值表示 | 说明 |
|---------|---------|------|
| 数值 | None/null | 数据缺失 |
| 字符串 | '' (空字符串) | 无内容 |
| 列表 | [] | 空列表 |
| 字典 | {} | 空字典 |

---

## 使用示例

### 数据类型转换示例

```python
import AmazingData as ad
from datetime import datetime

# 1. 周期转换
system_period = '1d'
ad_period = ad.constant.Period.day.value

# 2. 复权类型转换
system_adjust = 'qfq'
ad_adjust = ad.constant.Adjust.forward.value

# 3. 日期格式转换
date_str = '2025-01-15'
date_fmt = datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y%m%d')
# 结果：'20250115'

# 4. 股票代码处理
symbol = '000001.SZ'
code, market = symbol.split('.')
# code='000001', market='SZ'
```

### 数据结构使用示例

```python
# 处理K线数据
kline_data = market_data.get_kline_data(['000001'], ad.constant.Period.day.value)
for item in kline_data['000001']:
    print(f"日期: {item['time']}")
    print(f"开盘: {item['open']}, 收盘: {item['close']}")
    print(f"成交量: {item['volume'] / 10000:.2f}万股")

# 处理快照数据
snapshot = market_data.get_snapshot(['000001'])
data = snapshot['000001']
print(f"{data['name']} ({data['code']})")
print(f"最新: {data['last_price']} ({data['change_percent']:+.2f}%)")
print(f"买一: {data['bid1']} x {data['bid1_volume']}")
print(f"卖一: {data['ask1']} x {data['ask1_volume']}")

# 处理财务数据
indicators = info_data.get_key_indicators(['000001'])
for item in indicators['000001']:
    print(f"报告期: {item['report_date']}")
    print(f"ROE: {item['roe']:.2f}%")
    print(f"EPS: {item['eps']:.2f}元")
```

---

*文档版本：1.0.0*
*更新日期：2025-01-15*